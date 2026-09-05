/**
 * memory-atmem: auditable memory plugin for OpenClaw.
 *
 * A thin shell over the atmem engine (Python, spawned as an MCP child
 * process over stdio). The plugin adds automatic memory ergonomics —
 * auto-recall injection, auto-capture, agent-callable search — while every
 * policy decision (quarantine, supersession, deletion, receipts, audit
 * chain) stays server-side in the engine, where a prompt-injected agent
 * cannot reach it.
 *
 * Hooks:
 * - before_prompt_build → memory_recall_block (bounded, audited injection)
 * - agent_end           → memory_capture for the user turn + assistant digest
 * - before_message_write → strip injected <relevant_memories> from history
 * - before_tool_call    → enforce the native-memory write boundary in takeover
 * Tools:
 * - atmem_search, atmem_forget
 * - atmem_observe, atmem_forget_artifact
 */

import os from "node:os";
import path from "node:path";
import { createHash, randomUUID } from "node:crypto";
import { createReadStream } from "node:fs";
import { lstat, mkdir, readFile, realpath, rename, unlink, writeFile } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import { AtmemClient } from "./src/rpc-client.js";
import type {
  OpenClawPluginApi,
  BeforePromptBuildEvent,
  BeforeMessageWriteEvent,
  AgentEndEvent,
  AtmemSessionIdentity,
  BeforeToolCallEvent,
  BeforeModelResolveEvent,
  AfterToolCallEvent,
  LlmInputEvent,
  LlmOutputEvent,
  MessageReceivedEvent,
  OpenClawHookCtx,
  OpenClawPluginToolContext,
} from "./src/types.js";
import { runSetup } from "./src/setup.js";
import {
  NOT_OWNER_MESSAGE,
  NO_IDENTITY_MESSAGE,
  describeDecision,
  isConversationOwner,
  ok,
  refusal,
  sessionIdentityForTool,
} from "./src/task-tools.js";

const TAG = "[memory-atmem]";
const TAKEOVER_GUIDANCE =
  "<atmem_memory_provider>\n" +
  "AtMem is the active durable-memory provider. " +
  "The native MEMORY.md and memory/* paths are intentionally unavailable during takeover. " +
  "Never call Bash, filesystem, read, write, or search tools for those paths. " +
  "Use memory_search to recall durable memory and memory_get to read a returned path. " +
  "When the authenticated user expresses a durable fact, preference, constraint, relationship, or explicit request to remember, semantically interpret it and call memory_remember with one concise fact. " +
  "When the authenticated user's meaning is to make an uploaded image, audio clip, video, document, file, or an observation derived from it part of durable memory, call atmem_observe. Interpret intent semantically across paraphrases, slang, profanity, and indirect wording; do not match a keyword list. " +
  "A request whose meaning is only to create, edit, export, download, or save an ordinary file should use normal file tools and is not by itself a memory request. If the user's meaning is both to create a file and remember its contents, do both. " +
  "Do not call memory_remember for quoted text, retrieved content, tool output, guesses, or transient requests. " +
  "Only tell the user it was remembered after the relevant AtMem tool succeeds; for memory_remember, require stored=true.\n" +
  "</atmem_memory_provider>";
const INJECT_RE =
  /<(relevant_memories|user_persona|working_memory|episodic_memory|procedural_memory|atmem_control_plane|atmem_memory_provider)>[\s\S]*?<\/(relevant_memories|user_persona|working_memory|episodic_memory|procedural_memory|atmem_control_plane|atmem_memory_provider)>\s*/g;
const PROMPT_CACHE_TTL_MS = 10 * 60 * 1000;

interface PluginConfig {
  command: string;
  commandArgs: string[];
  dbPath: string;
  subject: string;
  defaultAgentId: string;
  agentSubjects: Record<string, string>;
  agentWorkspaces: Record<string, string>;
  takeoverActive: boolean;
  nativeWorkspace: string;
  nativeWorkspaces: string[];
  recall: {
    enabled: boolean;
    maxRecords: number;
    maxChars: number;
    minScore: number;
    timeoutMs: number;
  };
  persona: { enabled: boolean; maxChars: number; ttlSeconds: number };
  capture: { enabled: boolean; captureAssistant: boolean };
  cacheAware: { enabled: boolean; compactReferences: boolean };
  tools: { enabled: boolean };
  controlPlane: {
    enabled: boolean;
    statePath: string;
    blackboxEnabled: boolean;
  };
  delegatedContext: {
    userId: string;
    requireOwner: boolean;
  };
}

function parseConfig(raw: Record<string, unknown> | undefined): PluginConfig {
  const cfg = (raw ?? {}) as Record<string, any>;
  const dbPath = expandHome(String(cfg.dbPath ?? "~/.atmem/memories.db"));
  const subject = String(cfg.subject ?? "default");
  const stringMap = (value: unknown): Record<string, string> =>
    value && typeof value === "object" && !Array.isArray(value)
      ? Object.fromEntries(Object.entries(value as Record<string, unknown>)
          .filter(([, item]) => typeof item === "string" && item.trim())
          .map(([key, item]) => [key, String(item)]))
      : {};
  const agentSubjects = stringMap(cfg.agentSubjects);
  const agentWorkspaces = Object.fromEntries(
    Object.entries(stringMap(cfg.agentWorkspaces)).map(([key, value]) => [key, expandHome(value)]),
  );
  const nativeWorkspace = expandHome(String(cfg.nativeWorkspace ?? ""));
  const nativeWorkspaces = [...new Set([
    ...(Array.isArray(cfg.nativeWorkspaces) ? cfg.nativeWorkspaces.map((item: unknown) => expandHome(String(item))) : []),
    ...Object.values(agentWorkspaces),
    nativeWorkspace,
  ].filter(Boolean))];
  const controlPlane = {
    enabled: cfg.controlPlane?.enabled === true,
    statePath: expandHome(
      String(cfg.controlPlane?.statePath ?? "~/.atmem/control-plane.json"),
    ),
    blackboxEnabled:
      cfg.controlPlane?.enabled === true || cfg.controlPlane?.blackboxEnabled === true,
  };
  const delegatedContext = {
    userId: String(cfg.delegatedContext?.userId ?? "").trim(),
    requireOwner: cfg.delegatedContext?.requireOwner !== false,
  };
  return {
    command: String(cfg.command ?? "atmem"),
    commandArgs: controlPlane.enabled
      ? ["control", "mcp", "--state", controlPlane.statePath]
      : Array.isArray(cfg.commandArgs)
        ? cfg.commandArgs.map(String)
        : ["mcp", "--db", dbPath, "--subject", subject],
    dbPath,
    subject,
    defaultAgentId: String(cfg.defaultAgentId ?? "main"),
    agentSubjects,
    agentWorkspaces,
    takeoverActive: cfg.takeoverActive === true,
    nativeWorkspace,
    nativeWorkspaces,
    recall: {
      enabled: cfg.recall?.enabled !== false,
      maxRecords: Number(cfg.recall?.maxRecords ?? 3),
      maxChars: Number(cfg.recall?.maxChars ?? 1200),
      minScore: Number(cfg.recall?.minScore ?? 0.3),
      timeoutMs: Number(cfg.recall?.timeoutMs ?? 4000),
    },
    persona: {
      enabled: cfg.persona?.enabled !== false,
      maxChars: Number(cfg.persona?.maxChars ?? 600),
      ttlSeconds: Number(cfg.persona?.ttlSeconds ?? 300),
    },
    capture: {
      enabled: cfg.capture?.enabled !== false,
      captureAssistant: cfg.capture?.captureAssistant !== false,
    },
    cacheAware: {
      enabled: cfg.cacheAware?.enabled === true,
      compactReferences: cfg.cacheAware?.compactReferences !== false,
    },
    tools: { enabled: cfg.tools?.enabled !== false },
    controlPlane,
    delegatedContext,
  };
}

const FILE_TOOL_HINTS = [
  "bash", "shell", "exec", "write", "edit", "patch", "file", "filesystem",
  "read", "delete", "move", "copy", "search",
];

function isFileLikeTool(toolName: string): boolean {
  const normalized = toolName.toLowerCase();
  return FILE_TOOL_HINTS.some((hint) => normalized.includes(hint));
}

function isProtectedNativePath(candidate: string, workspace: string): boolean {
  if (!candidate || !workspace) return false;
  const root = path.resolve(workspace);
  const resolved = path.isAbsolute(candidate)
    ? path.resolve(candidate)
    : path.resolve(root, candidate);
  const memoryFile = path.join(root, "MEMORY.md");
  const memoryDir = path.join(root, "memory");
  return (
    resolved === memoryFile ||
    resolved === memoryDir ||
    resolved.startsWith(memoryDir + path.sep)
  );
}

function collectStrings(value: unknown, output: string[] = []): string[] {
  if (typeof value === "string") output.push(value);
  else if (Array.isArray(value)) {
    for (const item of value) collectStrings(item, output);
  } else if (value && typeof value === "object") {
    for (const item of Object.values(value as Record<string, unknown>)) {
      collectStrings(item, output);
    }
  }
  return output;
}

function commandMentionsNativeMemory(command: string, workspace: string): boolean {
  const normalizedWorkspace = path.resolve(workspace);
  if (command.includes(path.join(normalizedWorkspace, "MEMORY.md"))) return true;
  if (command.includes(path.join(normalizedWorkspace, "memory"))) return true;
  // OpenClaw's agent tools normally execute relative paths from its workspace.
  // Match path tokens, not prose such as "tell me about memory".
  return /(?:^|[\s'"`=;|&:(])(?:\.\/)?MEMORY\.md(?=$|[\s'"`;|&:)])/i.test(command) ||
    /(?:^|[\s'"`=;|&:(])(?:\.\/)?memory(?:\/[^\s'"`;|&)]*)?(?=$|[\s'"`;|&:)])/i.test(command);
}

function touchesNativeMemory(event: BeforeToolCallEvent, workspace: string): boolean {
  if (!workspace) return false;
  if ((event.derivedPaths ?? []).some((candidate) =>
    isProtectedNativePath(candidate, workspace))) return true;
  if (!isFileLikeTool(event.toolName)) return false;

  const params = event.params ?? {};
  const cwdValue = typeof params.cwd === "string" ? params.cwd : workspace;
  const cwd = path.isAbsolute(cwdValue)
    ? path.resolve(cwdValue)
    : path.resolve(workspace, cwdValue);
  const workspaceRoot = path.resolve(workspace);
  const runsInWorkspace = cwd === workspaceRoot || cwd.startsWith(workspaceRoot + path.sep);
  for (const value of collectStrings(params)) {
    if (path.isAbsolute(value) && isProtectedNativePath(value, workspace)) return true;
    if (runsInWorkspace && isProtectedNativePath(value, workspace)) return true;
    if (runsInWorkspace && commandMentionsNativeMemory(value, workspace)) return true;
  }
  return false;
}

function expandHome(filePath: string): string {
  return filePath.startsWith("~")
    ? path.join(os.homedir(), filePath.slice(1))
    : filePath;
}

/** Extract plain text from an OpenClaw message content shape. */
function messageText(content: unknown): string {
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .map((part) =>
        part && typeof part === "object" && (part as any).type === "text"
          ? String((part as any).text ?? "")
          : "",
      )
      .join("");
  }
  return "";
}

type InboundAttachmentEvidence = {
  mediaSha256: string;
  hostReference: string;
  modality: "image" | "audio" | "video" | "document";
  mimeType: string;
  bytes: number;
  capturedAt: number;
};

type DurableAttachmentBinding = {
  format: "atmem-openclaw-attachment-binding-v1";
  keySha256: string;
  items: InboundAttachmentEvidence[];
  updatedAt: number;
};

function attachmentBindingPath(root: string, key: string): string {
  return path.join(root, `${createHash("sha256").update(key).digest("hex")}.json`);
}

function validAttachmentEvidence(value: unknown): value is InboundAttachmentEvidence {
  if (!value || typeof value !== "object") return false;
  const row = value as Record<string, unknown>;
  return (
    typeof row.mediaSha256 === "string" && /^[a-f0-9]{64}$/.test(row.mediaSha256) &&
    typeof row.hostReference === "string" && row.hostReference.length > 0 &&
    ["image", "audio", "video", "document"].includes(String(row.modality)) &&
    typeof row.mimeType === "string" &&
    typeof row.bytes === "number" && Number.isSafeInteger(row.bytes) && row.bytes >= 0 &&
    typeof row.capturedAt === "number" && Number.isFinite(row.capturedAt)
  );
}

async function writeAttachmentBinding(
  root: string,
  key: string,
  items: InboundAttachmentEvidence[],
): Promise<void> {
  await mkdir(root, { recursive: true, mode: 0o700 });
  const target = attachmentBindingPath(root, key);
  const temporary = `${target}.${process.pid}.${randomUUID()}.tmp`;
  const payload: DurableAttachmentBinding = {
    format: "atmem-openclaw-attachment-binding-v1",
    keySha256: createHash("sha256").update(key).digest("hex"),
    items,
    updatedAt: Date.now(),
  };
  await writeFile(temporary, JSON.stringify(payload), { encoding: "utf8", mode: 0o600 });
  try {
    await rename(temporary, target);
  } catch (error) {
    await unlink(temporary).catch(() => undefined);
    throw error;
  }
}

async function readAttachmentBinding(
  root: string,
  key: string,
): Promise<{ items: InboundAttachmentEvidence[]; ts: number } | null> {
  try {
    const decoded = JSON.parse(await readFile(attachmentBindingPath(root, key), "utf8")) as
      Partial<DurableAttachmentBinding>;
    if (
      decoded.format !== "atmem-openclaw-attachment-binding-v1" ||
      decoded.keySha256 !== createHash("sha256").update(key).digest("hex") ||
      typeof decoded.updatedAt !== "number" ||
      Date.now() - decoded.updatedAt > PROMPT_CACHE_TTL_MS ||
      !Array.isArray(decoded.items) ||
      !decoded.items.every(validAttachmentEvidence)
    ) return null;
    return { items: decoded.items, ts: decoded.updatedAt };
  } catch {
    return null;
  }
}

function modalityFromMime(mimeType: string): InboundAttachmentEvidence["modality"] | null {
  const mime = mimeType.toLowerCase();
  if (mime.startsWith("image/")) return "image";
  if (mime.startsWith("audio/")) return "audio";
  if (mime.startsWith("video/")) return "video";
  if (mime === "application/pdf" || mime.startsWith("text/") || mime.includes("document")) {
    return "document";
  }
  return null;
}

function withinPath(candidate: string, root: string): boolean {
  return candidate === root || candidate.startsWith(root + path.sep);
}

async function hashInboundAttachment(
  filePath: string,
  mimeType: string,
): Promise<InboundAttachmentEvidence> {
  const mediaRoot = await realpath(
    process.env.ATMEM_OPENCLAW_MEDIA_ROOT
      ? expandHome(process.env.ATMEM_OPENCLAW_MEDIA_ROOT)
      : path.join(os.homedir(), ".openclaw", "media"),
  );
  const resolved = await realpath(expandHome(filePath));
  if (!withinPath(resolved, mediaRoot)) {
    throw new Error("OpenClaw attachment path is outside the managed media directory");
  }
  const before = await lstat(resolved);
  if (!before.isFile() || before.size > 512 * 1024 * 1024) {
    throw new Error("OpenClaw attachment is not a bounded regular file");
  }
  const hash = createHash("sha256");
  for await (const chunk of createReadStream(resolved)) hash.update(chunk as Buffer);
  const after = await lstat(resolved);
  if (before.size !== after.size || before.mtimeMs !== after.mtimeMs) {
    throw new Error("OpenClaw attachment changed while its digest was computed");
  }
  const mediaSha256 = hash.digest("hex");
  const modality = modalityFromMime(mimeType);
  if (!modality) throw new Error(`unsupported attachment MIME type: ${mimeType || "unknown"}`);
  return {
    mediaSha256,
    hostReference: `openclaw-media://sha256/${mediaSha256}`,
    modality,
    mimeType,
    bytes: before.size,
    capturedAt: Date.now(),
  };
}


function recordIdFromPath(value: string): string | null {
  const prefix = "atmem://record/";
  if (!value.startsWith(prefix)) return null;
  const recordId = value.slice(prefix.length).trim();
  return recordId || null;
}

function register(api: OpenClawPluginApi): void {
  const cfg = parseConfig(api.pluginConfig);
  const attachmentBindingRoot = path.join(
    path.dirname(cfg.controlPlane.enabled ? cfg.controlPlane.statePath : cfg.dbPath),
    "openclaw-attachment-bindings",
  );
  const client = new AtmemClient({
    command: cfg.command,
    args: cfg.commandArgs,
    log: (message) => api.logger.debug?.(`${TAG} ${message}`),
    logError: (message) => api.logger.warn(`${TAG} ${message}`),
  });
  const blackboxClient = cfg.controlPlane.enabled
    ? client
    : new AtmemClient({
        command: cfg.command,
        args: ["control", "mcp", "--state", cfg.controlPlane.statePath],
        log: (message) => api.logger.debug?.(`${TAG} ${message}`),
        logError: (message) => api.logger.warn(`${TAG} ${message}`),
      });
  // Let long-lived hosts close the stdio child during lifecycle shutdown.
  // The client's bounded idle shutdown also covers one-shot local runners.
  api.registerService?.({
    id: "memory-atmem-mcp",
    start: () => client.connect(),
    stop: () => client.close(),
  });
  if (blackboxClient !== client && cfg.controlPlane.blackboxEnabled) {
    api.registerService?.({
      id: "memory-atmem-blackbox",
      start: () => blackboxClient.connect(),
      stop: () => blackboxClient.close(),
    });
  }

  // Per-turn recall state. Semantic admission uses a short-lived SQLite handoff
  // because OpenClaw may run prompt hooks and agent tools in separate runtimes.
  const pendingPrompts = new Map<
    string,
    {
      text: string;
      ts: number;
      manifestSha256?: string;
      exposureId?: string;
      injectedRecordIds?: string[];
      retrievalId?: string;
      contextEventId?: string;
      contextReceiptId?: string;
      assistantVisibleTextSha256?: string;
      modelOutputBundleSha256?: string;
      delegatedContext?: string;
      delegatedContextSha256?: string;
      delegatedAuthority?: string;
      delegatedResultSha256?: string;
      taskDeliveryId?: string;
      taskContextSha256?: string;
      /** The task AtMem actually resolved, which may come from a binding. */
      taskId?: string;
    }
  >();
  const observedTurnInputs = new Map<
    string,
    { promptSha256: string; observedAt: number; pending: Promise<void> }
  >();
  const inboundAttachments = new Map<
    string,
    { items: InboundAttachmentEvidence[]; ts: number }
  >();
  const inboundAttachmentGeneration = new Map<string, number>();
  let nextAttachmentGeneration = 0;
  const agentIdFor = (ctx: OpenClawHookCtx): string => {
    if (ctx.agentId?.trim()) return ctx.agentId.trim();
    const session = ctx.sessionKey ?? ctx.sessionId ?? "";
    const match = /^agent:([^:]+)(?::|$)/.exec(session);
    return match?.[1] ?? cfg.defaultAgentId;
  };
  const subjectFor = (ctx: OpenClawHookCtx): string => {
    const agentId = agentIdFor(ctx);
    if (Object.keys(cfg.agentSubjects).length) {
      const mapped = cfg.agentSubjects[agentId];
      if (!mapped) throw new Error(`unmapped OpenClaw persistent agent: ${agentId}`);
      return mapped;
    }
    return cfg.subject;
  };
  /**
   * The identity AtMem resolves a governed task through.
   *
   * `sessionId` is the generation: OpenClaw changes it when a conversation is
   * reset, which is what stops a recycled `sessionKey` from inheriting an
   * earlier task binding. Both fields are optional upstream, so returning
   * `undefined` is an ordinary outcome and callers must withhold rather than
   * send a partial identity.
   */
  const sessionIdentityFor = (
    ctx: OpenClawHookCtx,
  ): AtmemSessionIdentity | undefined => {
    const sessionKey = ctx.sessionKey ?? ctx.sessionId;
    const sessionEpoch = ctx.sessionId;
    if (!sessionKey || !sessionEpoch) return undefined;
    return {
      host_type: "openclaw",
      session_key: sessionKey,
      session_epoch: sessionEpoch,
    };
  };

  const workspaceIdFor = (ctx: OpenClawHookCtx): string | undefined => {
    const workspace = cfg.agentWorkspaces[agentIdFor(ctx)];
    return workspace ? `ws_${digestText(workspace).slice(0, 16)}` : undefined;
  };
  const delegatedUserIdFor = (ctx: OpenClawHookCtx): string | undefined => {
    if (!cfg.delegatedContext.userId) return undefined;
    if (cfg.delegatedContext.requireOwner && ctx.senderIsOwner !== true) return undefined;
    return cfg.delegatedContext.userId;
  };
  const scopedKey = (value: string, ctx: OpenClawHookCtx): string =>
    `${agentIdFor(ctx)}:${value}`;
  const contextIds = (ctx: OpenClawHookCtx): string[] =>
    [...new Set([ctx.runId, ctx.sessionKey, ctx.sessionId].filter(
      (value): value is string => Boolean(value),
    ).map((value) => scopedKey(value, ctx)))];
  const callFor = (
    ctx: OpenClawHookCtx,
    name: string,
    args: Record<string, unknown>,
    timeoutMs = cfg.recall.timeoutMs,
  ): Promise<unknown> => {
    const scoped = cfg.controlPlane.enabled && !Object.keys(cfg.agentSubjects).length
      ? args
      : { ...args, subject_id: subjectFor(ctx) };
    return client.callTool(name, scoped, timeoutMs);
  };

  const digestText = (value: string): string =>
    createHash("sha256").update(value, "utf8").digest("hex");
  const stableValue = (value: unknown): unknown => {
    if (Array.isArray(value)) return value.map(stableValue);
    if (value && typeof value === "object") {
      return Object.fromEntries(
        Object.entries(value as Record<string, unknown>)
          .sort(([left], [right]) => left.localeCompare(right))
          .map(([key, item]) => [key, stableValue(item)]),
      );
    }
    return value;
  };
  const digestJson = (value: unknown): string => {
    try {
      return digestText(JSON.stringify(stableValue(value)));
    } catch {
      return digestText(String(value));
    }
  };
  const flightRunId = (
    eventRunId: string | undefined,
    ctx: OpenClawHookCtx,
  ): string => eventRunId ?? ctx.runId ?? ctx.sessionKey ?? ctx.sessionId ?? "unidentified-run";
  const canonicalToolName = (value: string): string => {
    const normalized = value.trim();
    return normalized.startsWith("openclaw") && normalized.length > "openclaw".length
      ? normalized.slice("openclaw".length)
      : normalized;
  };
  const recordBlackbox = async (
    eventType: string,
    eventRunId: string | undefined,
    ctx: OpenClawHookCtx,
    payload: Record<string, unknown>,
    toolCallId?: string,
    correlation: {
      turnId?: string;
      retrievalId?: string;
      contextEventId?: string;
      contextReceiptId?: string;
      outcomeId?: string;
    } = {},
  ): Promise<void> => {
    if (!cfg.controlPlane.blackboxEnabled) return;
    try {
      await blackboxClient.callTool(
        "control_record_blackbox_event",
        {
          event_type: eventType,
          run_id: flightRunId(eventRunId, ctx),
          agent_id: agentIdFor(ctx),
          workspace_id: workspaceIdFor(ctx),
          subject_id: Object.keys(cfg.agentSubjects).length ? subjectFor(ctx) : undefined,
          session_id: ctx.sessionId ?? ctx.sessionKey,
          tool_call_id: toolCallId,
          turn_id: correlation.turnId ?? flightRunId(eventRunId, ctx),
          retrieval_id: correlation.retrievalId,
          context_event_id: correlation.contextEventId,
          context_receipt_id: correlation.contextReceiptId,
          outcome_id: correlation.outcomeId,
          payload,
        },
        cfg.recall.timeoutMs,
      );
    } catch (error) {
      api.logger.warn(
        `${TAG} blackbox event ${eventType} was not recorded: ${
          error instanceof Error ? error.message : String(error)
        }`,
      );
    }
  };

  const resolveInboundAttachmentSet = async (
    ctx: OpenClawHookCtx,
  ): Promise<{ items: InboundAttachmentEvidence[]; ts: number } | null> => {
    // A run id identifies one exact user turn. When OpenClaw supplies it, do
    // not fall back to a session binding that could belong to the prior turn.
    const ids = ctx.runId ? [ctx.runId] : contextIds(ctx);
    for (let attempt = 0; attempt < 20; attempt += 1) {
      const memory = ids.map((key) => inboundAttachments.get(key)).find(
        (value) => value && value.items.length > 0,
      );
      if (memory) return memory;
      for (const key of ids) {
        const durable = await readAttachmentBinding(attachmentBindingRoot, key);
        if (durable?.items.length) return durable;
      }
      if (attempt < 19) await new Promise((resolve) => setTimeout(resolve, 100));
    }
    return null;
  };

  const stageInbound = async (
    text: string,
    ctx: OpenClawHookCtx,
  ) => {
    const ids = contextIds(ctx);
    if (!ids.length) return;
    await callFor(ctx, "memory_stage_user_message", {
      message: text.trim(),
      source_aliases: ids,
      run_id: ctx.runId,
      ttl_seconds: 600,
    }, cfg.recall.timeoutMs);
  };

  const turnInputKey = (ctx: OpenClawHookCtx): string =>
    scopedKey(flightRunId(undefined, ctx), ctx);

  const observeTurnInput = async (
    prompt: string,
    ctx: OpenClawHookCtx,
    sourceHook: "before_model_resolve" | "before_prompt_build",
    imagesCount?: number,
  ): Promise<void> => {
    if (!prompt.trim()) return;
    const key = turnInputKey(ctx);
    const promptSha256 = digestText(prompt);
    const existing = observedTurnInputs.get(key);
    if (existing) {
      if (existing.promptSha256 !== promptSha256) {
        api.logger.warn(
          `${TAG} ${sourceHook} exposed different prompt bytes for an already observed turn; ` +
          "the first authenticated turn input remains authoritative",
        );
      }
      await existing.pending;
      return;
    }

    const pending = (async () => {
      await recordBlackbox("turn.input", undefined, ctx, {
        prompt_sha256: promptSha256,
        prompt_chars: prompt.length,
        images_count: imagesCount,
      });
      try {
        await stageInbound(prompt, ctx);
      } catch (error) {
        api.logger.warn(
          `${TAG} semantic source handoff unavailable; memory writes will fail closed: ${
            error instanceof Error ? error.message : String(error)
          }`,
        );
      }
    })();
    observedTurnInputs.set(key, {
      promptSha256,
      observedAt: Date.now(),
      pending,
    });
    await pending;
  };

  const bindInboundAttachments = async (
    keys: string[],
    paths: string[],
    types: string[],
  ): Promise<void> => {
    const generation = ++nextAttachmentGeneration;
    for (const key of keys) {
      inboundAttachments.delete(key);
      inboundAttachmentGeneration.set(key, generation);
    }
    await Promise.all(keys.map((key) =>
      writeAttachmentBinding(attachmentBindingRoot, key, []),
    ));
    if (!paths.length) return;
    const items = await Promise.all(
      paths.map((filePath, index) =>
        hashInboundAttachment(filePath, types[index] ?? types[0] ?? "application/octet-stream"),
      ),
    );
    for (const key of keys) {
      if (inboundAttachmentGeneration.get(key) === generation) {
        inboundAttachments.set(key, { items, ts: Date.now() });
      }
    }
    await Promise.all(keys.map((key) =>
      inboundAttachmentGeneration.get(key) === generation
        ? writeAttachmentBinding(attachmentBindingRoot, key, items)
        : Promise.resolve(),
    ));
    api.logger.info(`${TAG} bound ${items.length} inbound attachment digest(s) to the turn`);
  };

  const writtenMessageAttachmentFields = (
    message: BeforeMessageWriteEvent["message"],
  ): { paths: string[]; types: string[] } => {
    const rawPaths = message.MediaPaths ?? message.mediaPaths;
    const rawPath = message.MediaPath ?? message.mediaPath;
    const paths = Array.isArray(rawPaths)
      ? rawPaths.filter((value): value is string => typeof value === "string")
      : typeof rawPath === "string"
        ? [rawPath]
        : [];
    const rawTypes = message.MediaTypes ?? message.mediaTypes;
    const rawType = message.MediaType ?? message.mediaType;
    const types = Array.isArray(rawTypes)
      ? rawTypes.filter((value): value is string => typeof value === "string")
      : typeof rawType === "string"
        ? [rawType]
        : [];
    return { paths, types };
  };

  const writtenMessageBindingKeys = (
    message: BeforeMessageWriteEvent["message"],
    ctx: OpenClawHookCtx,
  ): string[] => {
    const idempotencyKey = typeof message.idempotencyKey === "string"
      ? message.idempotencyKey.trim()
      : "";
    const turnId = idempotencyKey.endsWith(":user")
      ? idempotencyKey.slice(0, -":user".length)
      : idempotencyKey;
    return [...new Set([
      turnId,
      idempotencyKey,
      ...contextIds(ctx),
    ].filter((value): value is string => Boolean(value)))];
  };

  api.on("message_received", async (event: MessageReceivedEvent, ctx) => {
    const metadata = event.metadata ?? {};
    const paths = Array.isArray(metadata.mediaPaths)
      ? metadata.mediaPaths.filter((value): value is string => typeof value === "string")
      : typeof metadata.mediaPath === "string"
        ? [metadata.mediaPath]
        : [];
    const types = Array.isArray(metadata.mediaTypes)
      ? metadata.mediaTypes.filter((value): value is string => typeof value === "string")
      : typeof metadata.mediaType === "string"
        ? [metadata.mediaType]
        : [];
    const keys = [...new Set([
      event.sessionKey,
      event.runId,
      ...contextIds(ctx),
    ].filter((value): value is string => Boolean(value)))];
    try {
      await bindInboundAttachments(keys, paths, types);
    } catch (error) {
      api.logger.warn(
        `${TAG} inbound attachment provenance unavailable: ${
          error instanceof Error ? error.message : String(error)
        }`,
      );
    }
  });

  // OpenClaw documents this as the current prompt before model selection. It
  // is a typed per-turn input surface, not a rendered transcript or history.
  api.on("before_model_resolve", async (event: BeforeModelResolveEvent, ctx) => {
    await observeTurnInput(
      event.prompt,
      ctx,
      "before_model_resolve",
      Array.isArray(event.attachments) ? event.attachments.length : 0,
    );
  });

  api.on("llm_input", async (event: LlmInputEvent, ctx) => {
    const sessionKey = scopedKey(
      ctx.sessionKey ?? ctx.sessionId ?? event.sessionId ?? "default-session",
      ctx,
    );
    const pending = pendingPrompts.get(sessionKey);
    if (pending?.delegatedContext !== undefined) {
      const exact = pending.delegatedContext;
      const promptOccurrences = exact ? event.prompt.split(exact).length - 1 : 0;
      const systemOccurrences = exact
        ? (event.systemPrompt ?? "").split(exact).length - 1
        : 0;
      const occurrences = promptOccurrences + systemOccurrences;
      const deliveredLocation = promptOccurrences === 1
        ? "prompt"
        : systemOccurrences === 1
          ? "systemPrompt"
          : "none";
      const delivered = occurrences === 1 && digestText(exact) === pending.delegatedContextSha256;
      await recordBlackbox(
        "context.injected",
        event.runId,
        ctx,
        {
          disposition: delivered ? "injected" : "recall_failed",
          provider: pending.delegatedAuthority,
          result_sha256: pending.delegatedResultSha256,
          context_sha256: pending.delegatedContextSha256,
          context_chars: exact.length,
          context_byte_length: Buffer.byteLength(exact, "utf8"),
          context_location: deliveredLocation,
          success: delivered,
          reason: delivered ? undefined : `expected one exact delegated segment; observed ${occurrences}`,
        },
        undefined,
        { contextReceiptId: pending.contextReceiptId },
      );
      if (delivered && pending.exposureId) {
        await callFor(
          ctx,
          "control_exposure_shown",
          { exposure_id: pending.exposureId },
          cfg.recall.timeoutMs,
        );
      }
      pendingPrompts.set(sessionKey, { ...pending, delegatedContext: undefined });
    }
    await recordBlackbox("model.input", event.runId, ctx, {
      provider: event.provider,
      model: event.model,
      prompt_sha256: digestText(event.prompt ?? ""),
      prompt_chars: (event.prompt ?? "").length,
      system_sha256: digestText(event.systemPrompt ?? ""),
      system_chars: (event.systemPrompt ?? "").length,
      history_sha256: digestJson(event.historyMessages ?? []),
      history_count: Array.isArray(event.historyMessages) ? event.historyMessages.length : 0,
      images_count: event.imagesCount ?? 0,
      tools_count: Array.isArray(event.tools) ? event.tools.length : 0,
    });
  });

  api.on("llm_output", async (event: LlmOutputEvent, ctx) => {
    const responses = Array.isArray(event.assistantTexts) ? event.assistantTexts : [];
    const visibleText = responses.map(String).join("");
    const assistantVisibleTextSha256 = digestText(visibleText);
    const modelOutputBundleSha256 = digestJson(responses);
    const sessionKey = scopedKey(
      ctx.sessionKey ?? ctx.sessionId ?? event.sessionId ?? "default-session",
      ctx,
    );
    const pending = pendingPrompts.get(sessionKey);
    if (pending) {
      pendingPrompts.set(sessionKey, {
        ...pending,
        assistantVisibleTextSha256,
        modelOutputBundleSha256,
      });
    }
    await recordBlackbox("model.output", event.runId, ctx, {
      provider: event.provider,
      model: event.model,
      resolved_ref: event.resolvedRef,
      harness_id: event.harnessId,
      response_sha256: assistantVisibleTextSha256,
      assistant_visible_text_sha256: assistantVisibleTextSha256,
      model_output_bundle_sha256: modelOutputBundleSha256,
      response_digest_profile: "atmem-assistant-visible-text-utf8-v1",
      response_chars: visibleText.length,
      response_count: responses.length,
      usage: event.usage ?? {},
      reasoning_effort: event.reasoningEffort,
      fast_mode: event.fastMode,
    });
  });

  api.registerCli?.(
    ({ program }) => {
      const root = program
        .command("atmem")
        .description("Configure and inspect AtMem for OpenClaw");
      root
        .command("dashboard")
        .description("Open the authenticated AtMem dashboard in your browser")
        .action(() => {
          const runDashboard = (action: "open" | "start") =>
            spawnSync(
              cfg.command,
              ["dashboard", "daemon", action],
              { stdio: "inherit", env: process.env },
            );
          let result = runDashboard("open");
          if (result.error) throw result.error;
          if (result.status !== 0) {
            const started = runDashboard("start");
            if (started.error) throw started.error;
            if (started.status !== 0) {
              throw new Error(
                "AtMem dashboard could not be started; run `atmem dashboard daemon status` for details",
              );
            }
            result = runDashboard("open");
            if (result.error) throw result.error;
          }
          if (result.status !== 0) {
            throw new Error(
              "AtMem dashboard could not be opened; run `atmem dashboard daemon status` for the protected URL",
            );
          }
        });
      root
        .command("setup")
        .description("Apply safe single-user defaults and enable automatic memory hooks")
        .option("--single-user", "Acknowledge this plugin instance has one memory subject")
        .option("--subject <id>", "Stable single-user memory subject", "you")
        .option("--command <path>", "AtMem executable", cfg.command)
        .option("--db-path <path>", "AtMem SQLite database", cfg.dbPath)
        .option("--no-restart", "Do not restart the OpenClaw gateway")
        .action(async (options) => {
          await runSetup({
            subject: String(options.subject),
            command: String(options.command),
            dbPath: String(options.dbPath),
            restart: options.restart !== false,
          });
        });
    },
    { commands: ["atmem"] },
  );

  // L3 persona cache: rebuilt on TTL expiry and invalidated when capture
  // writes new memory, so the snapshot never lags a correction.
  const personaCaches = new Map<string, {
    block: string;
    recordIds: string[];
    contextEventId?: string;
    ts: number;
  }>();

  const sweep = () => {
    const now = Date.now();
    for (const [key, value] of pendingPrompts) {
      if (now - value.ts > PROMPT_CACHE_TTL_MS) pendingPrompts.delete(key);
    }
    for (const [key, value] of observedTurnInputs) {
      if (now - value.observedAt > PROMPT_CACHE_TTL_MS) observedTurnInputs.delete(key);
    }
    for (const [key, value] of inboundAttachments) {
      if (now - value.ts > PROMPT_CACHE_TTL_MS) inboundAttachments.delete(key);
    }
  };

  async function personaBlock(sessionKey: string, ctx: OpenClawHookCtx): Promise<{
    block: string;
    recordIds: string[];
    contextEventId?: string;
  }> {
    if (!cfg.persona.enabled) return { block: "", recordIds: [] };
    const now = Date.now();
    const subject = subjectFor(ctx);
    const personaCache = personaCaches.get(subject);
    if (personaCache && now - personaCache.ts < cfg.persona.ttlSeconds * 1000) {
      return personaCache;
    }
    const result = (await callFor(
      ctx,
      "memory_persona",
      {
        session_id: sessionKey,
        max_chars: cfg.persona.maxChars,
        reference_mode: cfg.cacheAware.enabled && cfg.cacheAware.compactReferences
          ? "compact"
          : "full",
      },
      cfg.recall.timeoutMs,
    )) as { block?: string; record_ids?: string[]; context_event_id?: string };
    const refreshed = {
      block: result?.block ?? "",
      recordIds: result?.record_ids ?? [],
      contextEventId: result?.context_event_id,
      ts: now,
    };
    personaCaches.set(subject, refreshed);
    return refreshed;
  }

  // ---- auto-recall: persona + bounded, audited recall injection ---------
  api.on("before_prompt_build", async (event: BeforePromptBuildEvent, ctx) => {
    const userText = event.prompt;
    if (!userText) return;
    await observeTurnInput(userText, ctx, "before_prompt_build");
    const sessionKey = scopedKey(ctx.sessionKey ?? ctx.sessionId ?? "default-session", ctx);
    const takeoverGuidance = cfg.takeoverActive ? TAKEOVER_GUIDANCE : "";
    pendingPrompts.set(sessionKey, { text: userText, ts: Date.now() });
    sweep();

    if (cfg.controlPlane.enabled) {
      try {
        const prepared = (await callFor(
          ctx,
          "control_prepare",
          {
            query: userText,
            session_id: sessionKey,
            host_run_id: ctx.runId,
            turn_id: ctx.runId,
            agent_id: agentIdFor(ctx),
            user_id: delegatedUserIdFor(ctx),
            workspace_id: workspaceIdFor(ctx),
          },
          cfg.recall.timeoutMs,
        )) as {
          inject?: boolean;
          context?: string;
          exposure_id?: string;
          mode?: string;
          candidate_ids?: string[];
          preview_context?: string;
          manifest_sha256?: string;
          turn_id?: string;
          context_receipt_id?: string;
          context_sha256?: string;
          authority?: string;
          decision?: string;
          result_sha256?: string;
          native_fallback?: boolean;
          receipt?: { id?: string; sha256?: string };
          provider?: { id?: string; version?: string; instance_id?: string };
        };
        // Task identity resolves through the manager, not from ctx.taskId
        // alone: OpenClaw supplies no task identity of its own, so without a
        // registered binding this branch could never run. Presenting the
        // session identity on every lookup keeps binding and resolution from
        // disagreeing about which conversation they mean.
        const taskIdentity = sessionIdentityFor(ctx);
        const taskPrepared = (ctx.taskId || taskIdentity)
          ? (await callFor(
              ctx,
              "control_prepare_task_context",
              {
                ...(ctx.taskId ? { task_id: ctx.taskId } : {}),
                ...(taskIdentity ?? {}),
                session_id: sessionKey,
                host_run_id: ctx.runId,
                agent_id: agentIdFor(ctx),
                workspace_id: workspaceIdFor(ctx),
              },
              cfg.recall.timeoutMs,
            )) as {
              disposition?: string;
              context?: string;
              context_sha256?: string;
              delivery_id?: string;
              /** Which task AtMem resolved; a binding may name one the host did not. */
              task_id?: string;
              revision?: number;
              reason_codes?: string[];
            }
          : undefined;
        if (
          taskPrepared?.disposition === "injected" &&
          (!taskPrepared.context || !taskPrepared.context_sha256 ||
            `sha256:${digestText(taskPrepared.context)}` !== taskPrepared.context_sha256)
        ) {
          throw new Error("governed task context failed exact handoff digest validation");
        }
        pendingPrompts.set(sessionKey, {
          text: userText,
          ts: Date.now(),
          exposureId: prepared.exposure_id,
          contextReceiptId: prepared.context_receipt_id,
          delegatedContext:
            prepared.authority === "delegated" && prepared.inject
              ? prepared.context ?? ""
              : undefined,
          delegatedContextSha256:
            prepared.authority === "delegated" ? prepared.context_sha256 : undefined,
          delegatedAuthority: prepared.authority,
          delegatedResultSha256: prepared.result_sha256,
          taskDeliveryId: taskPrepared?.delivery_id,
          taskContextSha256: taskPrepared?.context_sha256,
          taskId: taskPrepared?.task_id ?? ctx.taskId,
        });
        if (taskPrepared) {
          await recordBlackbox("task.context.prepared", undefined, ctx, {
            task_id: taskPrepared.task_id ?? ctx.taskId,
            task_disposition: taskPrepared?.disposition ?? "withheld",
            task_revision: taskPrepared?.revision,
            task_context_sha256: taskPrepared?.context_sha256?.replace(/^sha256:/, ""),
            task_reason_codes: taskPrepared?.reason_codes ?? [],
          });
        }
        if (
          prepared.authority === "delegated" &&
          prepared.inject &&
          (
            !prepared.context ||
            !prepared.context_sha256 ||
            digestText(prepared.context) !== prepared.context_sha256
          )
        ) {
          throw new Error("delegated context failed exact handoff digest validation");
        }
        if (prepared.authority === "delegated" || prepared.authority === "atmem_fallback") {
          await recordBlackbox(
            "context.provider_authorization",
            undefined,
            ctx,
            {
              disposition: prepared.decision ?? "provider_failure",
              provider: prepared.provider?.id,
              mode: prepared.authority,
              result_sha256: prepared.result_sha256,
              context_sha256: prepared.context_sha256,
              context_byte_length: Buffer.byteLength(prepared.context ?? "", "utf8"),
              context_receipt_sha256: prepared.receipt?.sha256,
              context_chars: (prepared.context ?? "").length,
              success: prepared.decision === "inject" || prepared.decision === "withhold",
            },
            undefined,
            { contextReceiptId: prepared.context_receipt_id },
          );
        }
        await recordBlackbox(
          "context.disposition",
          undefined,
          ctx,
          {
            disposition: prepared.inject && prepared.context
              ? "injected"
              : prepared.mode === "shadow" && (prepared.preview_context ?? "")
                ? "withheld_by_policy"
                : "no_relevant_memory",
            context_sha256: digestText(prepared.context ?? ""),
            context_block_sha256: digestText(prepared.context ?? ""),
            context_envelope_sha256: digestJson(
              prepared.authority === "delegated"
                ? { prependContext: prepared.context ?? "" }
                : { appendContext: prepared.context ?? "" },
            ),
            context_receipt_sha256: prepared.manifest_sha256,
            digest_profile: "atmem-context-envelope-canonical-json-v1",
            context_chars: (prepared.context ?? "").length,
            candidate_ids: prepared.candidate_ids ?? [],
            exposure_id: prepared.exposure_id,
            mode: prepared.mode,
            context_location: prepared.inject
              ? prepared.authority === "delegated" ? "prependContext" : "appendContext"
              : "none",
          },
          undefined,
          {
            contextReceiptId: prepared.context_receipt_id,
          },
        );
        if (prepared.inject && prepared.context) {
          api.logger.info(
            `${TAG} memory control plane ${prepared.mode ?? "active"} context exposed`,
          );
          return prepared.authority === "delegated"
            ? {
                prependContext: prepared.context,
                appendContext: taskPrepared?.disposition === "injected"
                  ? taskPrepared.context
                  : undefined,
              }
            : {
                appendContext: [
                  prepared.context,
                  taskPrepared?.disposition === "injected" ? taskPrepared.context : "",
                ].filter(Boolean).join("\n\n"),
              };
        }
        if (taskPrepared?.disposition === "injected" && taskPrepared.context) {
          return { appendContext: taskPrepared.context };
        }
        return;
      } catch (error) {
        await recordBlackbox("context.disposition", undefined, ctx, {
          disposition: "recall_failed",
          context_block_sha256: digestText(""),
          context_envelope_sha256: digestJson({}),
          digest_profile: "atmem-context-envelope-canonical-json-v1",
          context_chars: 0,
          candidate_ids: [],
          mode: "control-plane",
          context_location: "none",
          reason: error instanceof Error ? error.message : String(error),
        });
        api.logger.warn(
          `${TAG} memory control plane failed closed: ${
            error instanceof Error ? error.message : String(error)
          }`,
        );
        return;
      }
    }

    if (!cfg.recall.enabled && !cfg.persona.enabled) {
      const result = takeoverGuidance
        ? { appendSystemContext: takeoverGuidance }
        : {};
      await recordBlackbox("context.disposition", undefined, ctx, {
        disposition: "not_applicable",
        context_block_sha256: digestText(""),
        context_envelope_sha256: digestJson(result),
        digest_profile: "atmem-context-envelope-canonical-json-v1",
        context_chars: 0,
        candidate_ids: [],
        mode: "direct",
        context_location: "none",
      });
      if (Object.keys(result).length) return result;
      return;
    }

    let persona = "";
    let personaRecordIds: string[] = [];
    let personaContextEventId: string | undefined;
    let recall = "";
    let recallFailed = false;
    try {
      const personaResult = await personaBlock(sessionKey, ctx);
      persona = personaResult.block;
      personaRecordIds = personaResult.recordIds;
      personaContextEventId = personaResult.contextEventId;
    } catch (error) {
      recallFailed = true;
      api.logger.warn(
        `${TAG} persona skipped: ${error instanceof Error ? error.message : String(error)}`,
      );
    }
    try {
      if (cfg.recall.enabled) {
        const result = (await callFor(
          ctx,
          "memory_recall_block",
          {
            query: userText,
            session_id: sessionKey,
            max_records: cfg.recall.maxRecords,
            max_chars: cfg.recall.maxChars,
            min_score: cfg.recall.minScore,
            reference_mode: cfg.cacheAware.enabled && cfg.cacheAware.compactReferences
              ? "compact"
              : "full",
          },
          cfg.recall.timeoutMs,
        )) as {
          block?: string;
          count?: number;
          record_ids?: string[];
          retrieval_id?: string;
          context_event_id?: string;
        };
        if (result?.block) {
          api.logger.info(
            `${TAG} injected ${result.count} memories (${result.block.length} chars)`,
          );
          recall = result.block;
          const current = pendingPrompts.get(sessionKey);
          if (current) {
            pendingPrompts.set(sessionKey, {
              ...current,
              injectedRecordIds: result.record_ids ?? [],
              retrievalId: result.retrieval_id,
              contextEventId: result.context_event_id,
              contextReceiptId: result.context_event_id,
            });
          }
        }
      }
    } catch (error) {
      // Never block the turn on recall problems.
      recallFailed = true;
      api.logger.warn(
        `${TAG} auto-recall skipped: ${error instanceof Error ? error.message : String(error)}`,
      );
    }
    let result: {
      appendSystemContext?: string;
      appendContext?: string;
      prependContext?: string;
    } = {};
    let contextLocation = "none";
    if (cfg.cacheAware.enabled) {
      const systemParts = [takeoverGuidance, persona].filter(Boolean);
      if (systemParts.length) result.appendSystemContext = systemParts.join("\n\n");
      if (recall) result.appendContext = recall;
      contextLocation = recall
        ? "appendContext"
        : persona
          ? "appendSystemContext"
          : "none";
    } else {
      const parts = [persona, recall].filter(Boolean);
      if (parts.length) result.prependContext = parts.join("\n\n") + "\n\n";
      if (takeoverGuidance) result.appendSystemContext = takeoverGuidance;
      contextLocation = parts.length ? "prependContext" : "none";
    }
    const memoryContext = [persona, recall].filter(Boolean).join("\n\n");
    const current = pendingPrompts.get(sessionKey);
    const candidateIds = [...new Set([
      ...personaRecordIds,
      ...(current?.injectedRecordIds ?? []),
    ])];
    const componentEventIds = [...new Set([
      personaContextEventId,
      current?.contextEventId,
    ].filter((value): value is string => Boolean(value)))];
    const contextEnvelopeSha256 = digestJson(result);
    const contextReceiptId = componentEventIds.length
      ? `ctxr_${digestJson({ componentEventIds, contextEnvelopeSha256 })}`
      : undefined;
    if (current) {
      pendingPrompts.set(sessionKey, { ...current, contextReceiptId });
    }
    await recordBlackbox(
      "context.disposition",
      undefined,
      ctx,
      {
        disposition: memoryContext
          ? "injected"
          : recallFailed
            ? "recall_failed"
            : "no_relevant_memory",
        context_sha256: digestText(memoryContext),
        context_block_sha256: digestText(memoryContext),
        context_envelope_sha256: contextEnvelopeSha256,
        digest_profile: "atmem-context-envelope-canonical-json-v1",
        context_chars: memoryContext.length,
        candidate_ids: candidateIds,
        context_component_event_ids: componentEventIds,
        mode: "direct",
        context_location: contextLocation,
      },
      undefined,
      {
        retrievalId: current?.retrievalId,
        contextEventId: current?.contextEventId ?? personaContextEventId,
        contextReceiptId,
      },
    );
    if (Object.keys(result).length) return result;
  });

  // ---- flight recorder + takeover enforcement --------------------------
  api.on("before_tool_call", async (event: BeforeToolCallEvent, ctx) => {
    await recordBlackbox(
      "tool.requested",
      event.runId,
      ctx,
      {
        tool_name: event.toolName,
        tool_canonical_name: canonicalToolName(event.toolName),
        tool_kind: event.toolKind,
        params_sha256: digestJson(event.params ?? {}),
        param_keys: Object.keys(event.params ?? {}).sort(),
        derived_path_sha256: Array.isArray(event.derivedPaths)
          ? event.derivedPaths.map((value) => digestText(String(value)))
          : [],
      },
      event.toolCallId,
    );
    if (!cfg.takeoverActive || !cfg.nativeWorkspaces.some(
      (workspace) => touchesNativeMemory(event, workspace),
    )) return;
    const reason =
      "AtMem takeover blocked access to OpenClaw's frozen native memory " +
      "(MEMORY.md or memory/*). Use memory_remember for durable user facts, " +
      "and memory_search or memory_get for recall.";
    await recordBlackbox(
      "tool.completed",
      event.runId,
      ctx,
      {
        tool_name: event.toolName,
        tool_canonical_name: canonicalToolName(event.toolName),
        outcome: "error",
        error_category: "blocked_by_memory_boundary",
        result_sha256: digestText(reason),
        duration_ms: 0,
      },
      event.toolCallId,
    );
    api.logger.warn(`${TAG} ${reason} Tool: ${event.toolName}`);
    return { block: true, blockReason: reason };
  });

  api.on("after_tool_call", async (event: AfterToolCallEvent, ctx) => {
    await recordBlackbox(
      "tool.completed",
      event.runId,
      ctx,
      {
        tool_name: event.toolName,
        tool_canonical_name: canonicalToolName(event.toolName),
        result_sha256: digestJson(event.result ?? null),
        outcome: event.error ? "error" : "completed",
        error_category: event.error ? "tool_error" : undefined,
        duration_ms: event.durationMs ?? 0,
      },
      event.toolCallId,
    );
  });

  // ---- auto-capture: user turn through the pipeline, assistant as digest -
  api.on("agent_end", async (event: AgentEndEvent, ctx) => {
    const sessionKey = scopedKey(ctx.sessionKey ?? ctx.sessionId ?? "default-session", ctx);
    const observedTurnInputKey = turnInputKey(ctx);

    const cached = pendingPrompts.get(sessionKey);
    pendingPrompts.delete(sessionKey);
    const userText = cached?.text?.replace(INJECT_RE, "").trim();

    try {
      if (cfg.takeoverActive) {
        await callFor(
          ctx,
          "memory_clear_user_message",
          { source_aliases: contextIds(ctx) },
          cfg.recall.timeoutMs,
        );
      }
      if (cfg.controlPlane.enabled) {
        if (cached?.exposureId) {
          await callFor(
            ctx,
            "control_exposure_shown",
            { exposure_id: cached.exposureId },
            cfg.recall.timeoutMs,
          );
        }
        if (cached?.taskDeliveryId) {
          await callFor(
            ctx,
            "control_task_exposure_shown",
            { delivery_id: cached.taskDeliveryId },
            cfg.recall.timeoutMs,
          );
          await recordBlackbox("task.context.exposed", event.runId, ctx, {
            task_id: cached.taskId ?? ctx.taskId,
            task_disposition: "injected",
            task_context_sha256: cached.taskContextSha256?.replace(/^sha256:/, ""),
          });
        }
        if (event.success !== false) {
          await callFor(
            ctx,
            "control_sync_openclaw_memory",
            {},
            cfg.recall.timeoutMs,
          );
        }
        return;
      }
      if (cfg.takeoverActive && cached?.injectedRecordIds?.length) {
        const messages = Array.isArray(event.messages) ? event.messages : [];
        for (let index = messages.length - 1; index >= 0; index -= 1) {
          const message = messages[index] as { role?: string; content?: unknown };
          if (message?.role !== "assistant") continue;
          const responseText = messageText(message.content);
          if (responseText) {
            const assistantVisibleTextSha256 =
              cached.assistantVisibleTextSha256 ?? digestText(responseText);
            await callFor(ctx, "memory_log_action", {
              action_type: "agent.response_after_memory",
              payload: {
                response_sha256: assistantVisibleTextSha256,
                assistant_visible_text_sha256: assistantVisibleTextSha256,
                model_output_bundle_sha256: cached.modelOutputBundleSha256,
                response_digest_profile: "atmem-assistant-visible-text-utf8-v1",
                injected_record_ids: cached.injectedRecordIds,
                retrieval_id: cached.retrievalId,
                context_event_id: cached.contextEventId,
                context_receipt_id: cached.contextReceiptId,
                run_id: flightRunId(event.runId, ctx),
                response_content_stored: false,
                success: event.success !== false,
              },
              session_id: sessionKey,
            });
          }
          break;
        }
      }
      if (
        cfg.capture.enabled &&
        !cfg.takeoverActive &&
        event.success !== false &&
        userText
      ) {
        await callFor(ctx, "memory_capture", {
          role: "user",
          content: userText,
          session_id: sessionKey,
        });
        personaCaches.delete(subjectFor(ctx)); // new memory may change the persona
      }
      if (
        cfg.capture.enabled &&
        !cfg.takeoverActive &&
        event.success !== false &&
        cfg.capture.captureAssistant
      ) {
        const messages = Array.isArray(event.messages) ? event.messages : [];
        for (let index = messages.length - 1; index >= 0; index -= 1) {
          const message = messages[index] as { role?: string; content?: unknown };
          if (message?.role === "assistant") {
            const text = messageText(message.content);
            if (text) {
              await callFor(ctx, "memory_capture", {
                role: "assistant",
                content: text,
                session_id: sessionKey,
              });
            }
            break;
          }
        }
      }
    } catch (error) {
      api.logger.warn(
        `${TAG} auto-capture failed: ${error instanceof Error ? error.message : String(error)}`,
      );
    } finally {
      const cancelled = event.cancelled === true;
      const turnMessagesSha256 = digestJson(event.messages ?? []);
      await recordBlackbox("turn.ended", event.runId, ctx, {
        success: event.success === true && !cancelled,
        cancelled,
        error_category: event.error ? "agent_error" : undefined,
        failure_kind: cancelled ? "cancelled" : event.error ? "agent_error" : undefined,
        reason: event.error,
        duration_ms: event.durationMs ?? 0,
        messages_sha256: turnMessagesSha256,
        turn_messages_sha256: turnMessagesSha256,
        digest_profile: "atmem-turn-messages-canonical-json-v1",
        messages_count: Array.isArray(event.messages) ? event.messages.length : 0,
      }, undefined, {
        retrievalId: cached?.retrievalId,
        contextEventId: cached?.contextEventId,
        contextReceiptId: cached?.contextReceiptId,
      });
      observedTurnInputs.delete(observedTurnInputKey);
    }
  });

  // ---- keep injected blocks out of persisted history ---------------------
  api.on("before_message_write", (event, ctx = {}) => {
    const message = event.message;
    if (message.role !== "user") return;

    // Internal OpenClaw webchat persists the host-managed MediaPath on the
    // current user message before the model can call a tool. Earlier prompt
    // hooks intentionally omit that path. Capture this structured host field
    // here and hash the exact managed bytes asynchronously; never infer a file
    // by scanning the media directory or scraping its name from user text.
    const attachmentFields = writtenMessageAttachmentFields(message);
    const attachmentKeys = writtenMessageBindingKeys(message, ctx);
    if (attachmentKeys.length) {
      void bindInboundAttachments(
        attachmentKeys,
        attachmentFields.paths,
        attachmentFields.types,
      ).catch((error) => {
        api.logger.warn(
          `${TAG} persisted attachment provenance unavailable: ${
            error instanceof Error ? error.message : String(error)
          }`,
        );
      });
    }

    const hasInjection = (text: string) =>
      text.includes("<relevant_memories>") ||
      text.includes("<user_persona>") ||
      text.includes("<working_memory>") ||
      text.includes("<episodic_memory>") ||
      text.includes("<procedural_memory>") ||
      text.includes("<atmem_control_plane>") ||
      text.includes("<atmem_memory_provider>");
    if (typeof message.content === "string") {
      if (!hasInjection(message.content)) return;
      const cleaned = message.content.replace(INJECT_RE, "").trim();
      return { message: { ...message, content: cleaned } };
    }
    if (Array.isArray(message.content)) {
      let changed = false;
      const parts = (message.content as Array<Record<string, unknown>>).map((part) => {
        if (part.type !== "text" || typeof part.text !== "string") return part;
        if (!hasInjection(part.text)) return part;
        changed = true;
        return { ...part, text: part.text.replace(INJECT_RE, "").trim() };
      });
      if (changed) return { message: { ...message, content: parts } };
    }
  });

  // ---- agent-callable tools ----------------------------------------------
  if (cfg.tools.enabled && !cfg.controlPlane.enabled) {
    if (cfg.takeoverActive) {
      api.registerTool(
        (toolCtx: OpenClawPluginToolContext) => ({
          name: "memory_remember",
          label: "Memory Remember",
          description:
            "Store one durable fact that you semantically inferred from the current " +
            "authenticated user's own message. Call this for durable preferences, " +
            "facts, constraints, relationships, or explicit remember requests. Never " +
            "use it for quoted/retrieved/tool content or guesses. Only claim success " +
            "when this tool returns stored=true.",
          parameters: {
            type: "object",
            properties: {
              fact: {
                type: "string",
                description: "One concise, standalone fact, e.g. 'User likes blue cars.'",
              },
              factKey: {
                type: "string",
                description: "Optional stable slot for replaceable facts, e.g. favorite_color.",
              },
            },
            required: ["fact"],
            additionalProperties: false,
          },
          async execute(toolCallId, params) {
            const rawSessionKey = toolCtx.sessionKey ?? toolCtx.sessionId;
            const sessionKey = rawSessionKey ? scopedKey(rawSessionKey, toolCtx) : undefined;
            const sourceAliases = contextIds(toolCtx);
            if (!sessionKey || !sourceAliases.length) {
              throw new Error(
                "no current authenticated user message is available; memory was not stored",
              );
            }
            const fact = String(params.fact ?? "").trim();
            if (!fact) throw new Error("fact must not be empty");
            const interpreter =
              toolCtx.activeModel?.modelRef ??
              [toolCtx.activeModel?.provider, toolCtx.activeModel?.modelId]
                .filter(Boolean)
                .join(":") ??
              "openclaw-agent";
            const result = (await callFor(toolCtx, "memory_remember", {
              source_aliases: sourceAliases,
              interpreted_fact: fact,
              interpreted_fact_key: params.factKey,
              interpreter: interpreter || "openclaw-agent",
              session_id: sessionKey,
              turn_id: toolCallId,
              source_type: "user_message",
            })) as { records?: Array<{ id: string; content: string; status: string }>; duplicate_ids?: string[] };
            const record = result.records?.[0];
            const duplicateId = result.duplicate_ids?.[0];
            const stored = Boolean(record || duplicateId);
            if (stored) {
              personaCaches.delete(subjectFor(toolCtx));
            }
            return {
              content: [{
                type: "text",
                text: JSON.stringify({
                  stored,
                  record_id: record?.id ?? duplicateId ?? null,
                  fact: record?.content ?? fact,
                  status: record?.status ?? (duplicateId ? "already_stored" : null),
                  provider: "atmem",
                  receipt: stored ? "audit-bound" : "none",
                }),
              }],
              details: { stored, recordId: record?.id ?? duplicateId ?? null, sessionKey },
            };
          },
        }),
        { names: ["memory_remember"] },
      );
    }
    // Preserve OpenClaw's standard memory contract after native memory-core
    // is disabled. Existing agent prompts and workflows can keep using the
    // same tool names; only the governed storage/retrieval implementation
    // changes underneath them.
    api.registerTool(
      (toolCtx: OpenClawPluginToolContext) => ({
        name: "memory_search",
        label: "Memory Search",
        description:
          "Search governed AtMem long-term memory. Compatible with OpenClaw's " +
          "standard memory_search contract. The active takeover supports the " +
          "memory corpus; session and wiki corpora must be migrated explicitly.",
        parameters: {
          type: "object",
          properties: {
            query: { type: "string" },
            maxResults: { type: "integer", minimum: 1 },
            minScore: { type: "number" },
            corpus: {
              type: "string",
              enum: ["memory", "wiki", "all", "sessions"],
            },
          },
          required: ["query"],
          additionalProperties: false,
        },
        async execute(toolCallId, params) {
          const corpus = String(params.corpus ?? "memory");
          if (corpus === "wiki" || corpus === "sessions") {
            return {
              content: [{
                type: "text",
                text: JSON.stringify({
                  results: [],
                  disabled: true,
                  error:
                    `${corpus} corpus is not enabled in this AtMem takeover`,
                }),
              }],
              details: { count: 0, corpus, disabled: true },
            };
          }
          const sessionId = `openclaw-memory-search:${toolCallId}`;
          const maxResults = Math.min(
            Math.max(Number(params.maxResults) || 6, 1),
            20,
          );
          const records = (await callFor(toolCtx, "memory_recall", {
            query: String(params.query ?? ""),
            session_id: sessionId,
            limit: maxResults,
            min_score:
              params.minScore === undefined
                ? cfg.recall.minScore
                : Number(params.minScore),
            include_scores: true,
          })) as Array<{
            id: string;
            content: string;
            score?: number;
            created_at?: string;
            source_type?: string;
          }>;
          const results = records.map((record) => ({
            path: `atmem://record/${record.id}`,
            startLine: 1,
            endLine: Math.max(record.content.split("\n").length, 1),
            score: Number(record.score ?? 0),
            snippet: record.content,
            source: "atmem",
            corpus: "memory",
            id: record.id,
            sourceType: record.source_type,
            updatedAt: record.created_at,
            citation: `atmem:${record.id}`,
          }));
          return {
            content: [{
              type: "text",
              text: JSON.stringify({
                results,
                provider: "atmem",
                model: "deterministic-record-rank-v1",
                citations: "auto",
                mode: "governed",
              }),
            }],
            details: { count: results.length, corpus, sessionId },
          };
        },
      }),
      { name: "memory_search" },
    );

    api.registerTool(
      (toolCtx: OpenClawPluginToolContext) => ({
        name: "memory_get",
        label: "Memory Get",
        description:
          "Read one exact governed AtMem record returned by memory_search. " +
          "The read is bounded and added to the AtMem audit trail.",
        parameters: {
          type: "object",
          properties: {
            path: { type: "string" },
            from: { type: "integer", minimum: 1 },
            lines: { type: "integer", minimum: 1 },
            corpus: { type: "string", enum: ["memory", "wiki", "all"] },
          },
          required: ["path"],
          additionalProperties: false,
        },
        async execute(toolCallId, params) {
          const lookup = String(params.path ?? "");
          const recordId = recordIdFromPath(lookup);
          if (!recordId) {
            const sessionId = `openclaw-memory-get:${toolCallId}`;
            const sourceResult = (await callFor(toolCtx, "memory_get_source", {
              path: lookup,
              session_id: sessionId,
            })) as {
              path?: string;
              text?: string;
              source?: Record<string, unknown>;
            } | null;
            if (sourceResult?.text !== undefined) {
              const allLines = sourceResult.text.split("\n");
              const from = Math.max(Number(params.from) || 1, 1);
              const requested = Math.min(
                Math.max(Number(params.lines) || 50, 1),
                200,
              );
              const selected = allLines.slice(from - 1, from - 1 + requested);
              const payload = {
                path: lookup,
                text: selected.join("\n"),
                from,
                lines: selected.length,
                totalLines: allLines.length,
                truncated: from - 1 + selected.length < allLines.length,
                source: "atmem-frozen-openclaw",
                provenance: sourceResult.source ?? {},
              };
              return {
                content: [{ type: "text", text: JSON.stringify(payload) }],
                details: { found: true, sessionId },
              };
            }
            return {
              content: [{
                type: "text",
                text: JSON.stringify({
                  path: lookup,
                  text: "",
                  disabled: true,
                  error:
                    "No governed record or frozen OpenClaw memory file matched this path",
                }),
              }],
              details: { found: false },
            };
          }
          const sessionId = `openclaw-memory-get:${toolCallId}`;
          const result = (await callFor(toolCtx, "memory_get_record", {
            record_id: recordId,
            session_id: sessionId,
          })) as {
            record?: { content?: string };
            source?: Record<string, unknown>;
          } | null;
          const allLines = String(result?.record?.content ?? "").split("\n");
          const from = Math.max(Number(params.from) || 1, 1);
          const requested = Math.min(Math.max(Number(params.lines) || 50, 1), 200);
          const selected = allLines.slice(from - 1, from - 1 + requested);
          const payload = {
            path: lookup,
            text: selected.join("\n"),
            from,
            lines: selected.length,
            totalLines: allLines.length,
            truncated: from - 1 + selected.length < allLines.length,
            source: "atmem",
            provenance: result?.source ?? {},
          };
          return {
            content: [{ type: "text", text: JSON.stringify(payload) }],
            details: { found: Boolean(result?.record), sessionId },
          };
        },
      }),
      { name: "memory_get" },
    );

    api.registerTool(
      (toolCtx: OpenClawPluginToolContext) => ({
        name: "atmem_search",
        label: "Memory Search (atmem)",
        description:
          "Search the user's long-term auditable memory. Use when you need " +
          "preferences, facts, or context from previous conversations that " +
          "were not auto-injected.",
        parameters: {
          type: "object",
          properties: {
            query: { type: "string", description: "What to recall about the user" },
            limit: { type: "number", description: "Max results (default 5)" },
          },
          required: ["query"],
        },
        async execute(toolCallId, params) {
          const sessionId = `openclaw-tool:${toolCallId}`;
          const records = (await callFor(toolCtx, "memory_recall", {
            query: String(params.query ?? ""),
            session_id: sessionId,
            limit: Math.min(Math.max(Number(params.limit) || 5, 1), 20),
          })) as Array<{ id: string; content: string }>;
          const text = records.length
            ? records.map((record) => `- [${record.id}] ${record.content}`).join("\n")
            : "No matching memories.";
          return {
            content: [{ type: "text", text }],
            details: { count: records.length, sessionId },
          };
        },
      }),
      { name: "atmem_search" },
    );

    api.registerTool(
      (toolCtx: OpenClawPluginToolContext) => ({
        name: "atmem_forget",
        label: "Memory Forget (atmem)",
        description:
          "Delete the user's memories matching their request — only call when " +
          "the user explicitly asks to forget something. Deletion purges " +
          "content and returns a verifiable receipt; report the purged count " +
          "back to the user.",
        parameters: {
          type: "object",
          properties: {
            utterance: {
              type: "string",
              description: 'The user\'s words, e.g. "Forget my backup email."',
            },
          },
          required: ["utterance"],
        },
        async execute(toolCallId, params) {
          const sessionId = `openclaw-tool:${toolCallId}`;
          const result = (await callFor(toolCtx, "memory_forget", {
            utterance: String(params.utterance ?? ""),
            session_id: sessionId,
            turn_id: toolCallId,
          })) as { deleted: boolean; record_ids: string[]; receipt?: unknown };
          if (result.deleted) personaCaches.delete(subjectFor(toolCtx));
          const text = result.deleted
            ? `Deleted ${result.record_ids.length} memorie(s). Receipt: ${JSON.stringify(result.receipt)}`
            : "No matching memories found to delete.";
          return {
            content: [{ type: "text", text }],
            details: { deleted: result.deleted, sessionId },
          };
        },
      }),
      { name: "atmem_forget" },
    );

    api.registerTool(
      (toolCtx: OpenClawPluginToolContext) => ({
        name: "atmem_observe",
        label: "Media Observation (atmem)",
        description:
          "When the authenticated user's meaning is to remember or retain an uploaded " +
          "image, audio clip, video, document, or something observed from it for later " +
          "agent use, store one " +
          "typed text observation. For a current OpenClaw upload, exact-byte " +
          "SHA-256 provenance is supplied automatically by the trusted host hook. The " +
          "observation is quarantined until explicitly promoted. Confidence is " +
          "evidence only and never grants trust.",
        parameters: {
          type: "object",
          properties: {
            text: { type: "string", description: "What the extractor observed" },
            modality: {
              type: "string",
              enum: ["image", "audio", "video", "document"],
            },
            media_sha256: {
              type: "string",
              description: "Optional SHA-256 when no current OpenClaw upload is bound",
            },
            host_reference: {
              type: "string",
              description: "Optional secretless reference when no upload is bound",
            },
            segment: {
              type: "object",
              description:
                "Optional location inside the media. Omit for a whole-file observation.",
              properties: {
                page: {
                  type: "integer",
                  minimum: 1,
                  description: "One-based document page",
                },
                timestamp_start: {
                  type: "number",
                  minimum: 0,
                  description: "Audio/video start time in seconds",
                },
                timestamp_end: {
                  type: "number",
                  minimum: 0,
                  description: "Audio/video end time in seconds",
                },
                region: {
                  type: "string",
                  minLength: 1,
                  maxLength: 500,
                  description: "Human-readable region, for example 'upper-left logo'",
                },
              },
              additionalProperties: false,
            },
            extractor: {
              type: "object",
              description:
                "Extractor identity: provider, model, version, and optional model_digest",
              properties: {
                provider: { type: "string" },
                model: { type: "string" },
                version: { type: "string" },
                model_digest: { type: "string" },
              },
              additionalProperties: false,
            },
            confidence: {
              type: "number",
              description: "Extractor-local score from 0 to 1",
            },
            observed_at: { type: "string", description: "Optional ISO-8601 timestamp" },
            attachment_index: {
              type: "number",
              description: "Zero-based upload index when the user supplied multiple files",
            },
          },
          required: ["text", "modality"],
        },
        async execute(toolCallId, params) {
          const sessionId = `openclaw-tool:${toolCallId}`;
          sweep();
          const attachmentSet = await resolveInboundAttachmentSet(toolCtx);
          const requestedIndex = Math.max(0, Math.floor(Number(params.attachment_index) || 0));
          const attachment = attachmentSet?.items[requestedIndex];
          const requestedModality = String(params.modality ?? "");
          if (attachment && attachment.modality !== requestedModality) {
            throw new Error(
              `bound upload ${requestedIndex} is ${attachment.modality}, not ${requestedModality}`,
            );
          }
          const mediaSha256 = attachment?.mediaSha256 ?? String(params.media_sha256 ?? "");
          const hostReference = attachment?.hostReference ?? String(params.host_reference ?? "");
          if (!/^[a-f0-9]{64}$/i.test(mediaSha256) || !hostReference) {
            throw new Error(
              "No exact uploaded-file provenance is bound to this session. " +
              "Attach the file in the same OpenClaw message or provide its SHA-256 and secretless reference.",
            );
          }
          const suppliedRaw = params.extractor && typeof params.extractor === "object"
            ? params.extractor as Record<string, unknown>
            : {};
          const suppliedExtractor: Record<string, unknown> = {};
          for (const key of ["provider", "model", "version", "model_digest"] as const) {
            if (typeof suppliedRaw[key] === "string") suppliedExtractor[key] = suppliedRaw[key];
          }
          const extractor = {
            ...suppliedExtractor,
            provider: toolCtx.activeModel?.provider ?? suppliedExtractor.provider ?? "openclaw",
            model: toolCtx.activeModel?.modelId ?? suppliedExtractor.model ?? "unknown",
            version: suppliedExtractor.version ?? "openclaw-host-observation-v1",
          };
          const suppliedSegment = params.segment && typeof params.segment === "object"
            ? params.segment as Record<string, unknown>
            : {};
          const segment: Record<string, unknown> = {};
          for (const key of ["page", "timestamp_start", "timestamp_end", "region"] as const) {
            if (suppliedSegment[key] !== undefined) segment[key] = suppliedSegment[key];
          }
          const result = (await callFor(toolCtx, "memory_observe", {
            text: String(params.text ?? ""),
            modality: requestedModality,
            media_sha256: mediaSha256,
            host_reference: hostReference,
            segment,
            extractor,
            confidence: params.confidence,
            observed_at: params.observed_at,
            session_id: sessionId,
            turn_id: toolCallId,
          })) as {
            artifact: { id: string };
            observation: { id: string };
            record: { id: string; status: string };
            duplicate: boolean;
          };
          return {
            content: [
              {
                type: "text",
                text:
                  `Media observation ${result.duplicate ? "already existed" : "stored"} ` +
                  `as quarantined record ${result.record.id}.`,
              },
            ],
            details: {
              success: true,
              artifactId: result.artifact.id,
              observationId: result.observation.id,
              recordId: result.record.id,
              status: result.record.status,
              duplicate: result.duplicate,
              provenanceSource: attachment ? "openclaw-upload" : "caller",
              mediaSha256,
              sessionId,
            },
          };
        },
      }),
      { name: "atmem_observe" },
    );

    api.registerTool(
      (toolCtx: OpenClawPluginToolContext) => ({
        name: "atmem_forget_artifact",
        label: "Forget Media Artifact (atmem)",
        description:
          "Only when the user explicitly requests deletion, purge all AtMem " +
          "observations derived from one exact-byte SHA-256. This does not " +
          "delete the host's original file or a re-encoded copy.",
        parameters: {
          type: "object",
          properties: {
            media_sha256: {
              type: "string",
              description: "SHA-256 of the exact media byte stream",
            },
            artifact_id: {
              type: "string",
              description: "Optional artifact id that must match the digest",
            },
          },
          required: ["media_sha256"],
        },
        async execute(toolCallId, params) {
          const sessionId = `openclaw-tool:${toolCallId}`;
          const result = (await callFor(toolCtx, "memory_forget_artifact", {
            media_sha256: String(params.media_sha256 ?? ""),
            artifact_id: params.artifact_id,
            session_id: sessionId,
            turn_id: toolCallId,
          })) as { deleted: boolean; record_ids: string[]; receipt?: unknown };
          if (result.deleted) personaCaches.delete(subjectFor(toolCtx));
          const text = result.deleted
            ? `Purged ${result.record_ids.length} derived memorie(s). Receipt: ${JSON.stringify(result.receipt)}`
            : "No active AtMem artifact matched that exact digest.";
          return {
            content: [{ type: "text", text }],
            details: { deleted: result.deleted, sessionId },
          };
        },
      }),
      { name: "atmem_forget_artifact" },
    );

    // --- governed task tools (Amendment A) -------------------------------
    //
    // A control-plane operation is invisible to a model. Without these
    // registrations an agent receives a task checklist it has no way to tick,
    // which is worse than receiving nothing: it looks like progress is being
    // tracked when nothing is being recorded.
    //
    // Every one resolves through this conversation's own binding, so a model
    // can only touch the task its conversation is bound to.

    const taskScope = (toolCtx: OpenClawPluginToolContext) => ({
      agent_id: agentIdFor(toolCtx),
      workspace_id: workspaceIdFor(toolCtx),
    });

    api.registerTool(
      (toolCtx: OpenClawPluginToolContext) => ({
        name: "task_report_progress",
        label: "Report Task Progress (atmem)",
        description:
          "Report progress on the governed task this conversation is bound to. " +
          "State the item and its new status. AtMem validates the change and " +
          "decides; you are proposing, not writing. If no task is bound this " +
          "does nothing.",
        parameters: {
          type: "object",
          properties: {
            item_id: { type: "string", description: "Which task item changed" },
            status: {
              type: "string",
              enum: ["ready", "running", "blocked", "completed", "skipped", "failed"],
              description: "The item's new status",
            },
            base_revision: {
              type: "integer",
              description:
                "The task revision you read. If the task has moved since, this " +
                "returns a conflict instead of overwriting someone else's work.",
            },
            reason: { type: "string", description: "Why, in one line" },
          },
          required: ["item_id", "status", "base_revision"],
        },
        async execute(toolCallId, params) {
          const identity = sessionIdentityForTool(toolCtx);
          if (!identity) return refusal(NO_IDENTITY_MESSAGE);
          const result = (await callFor(toolCtx, "control_propose_task_delta", {
            ...identity,
            ...taskScope(toolCtx),
            task_id: String(params.task_id ?? ""),
            base_revision: Number(params.base_revision ?? 0),
            // Derived from stable host identifiers, never from payload content
            // or a clock, so a retried tool call collapses to one decision.
            idempotency_key: `${toolCtx.runId ?? "run"}:${toolCallId}`,
            operations: [
              {
                kind: "set_item_status",
                item_id: String(params.item_id ?? ""),
                status: String(params.status ?? ""),
                reason: params.reason ? String(params.reason) : undefined,
              },
            ],
            adapter: "openclaw",
            // The tool call is the evidence. Completing an item requires some,
            // and a host reporting its own tool outcome is asserting rather
            // than independently verifying -- AtMem records it at exactly that
            // assurance and never upgrades it.
            evidence: [
              { kind: "tool_call", reference_id: `${toolCtx.runId ?? "run"}-${toolCallId}` },
            ],
            reason: params.reason ? String(params.reason) : "",
          })) as Record<string, unknown>;
          return {
            content: [{ type: "text", text: describeDecision(result) }],
            details: { outcome: result.outcome ?? result.reason_code ?? null },
          };
        },
      }),
      { name: "task_report_progress" },
    );

    api.registerTool(
      (toolCtx: OpenClawPluginToolContext) => ({
        name: "task_binding_status",
        label: "Governed Task Binding (atmem)",
        description:
          "Show which governed task, if any, this conversation is bound to, and " +
          "the exact command to bind it. Owner only.",
        parameters: { type: "object", properties: {} },
        async execute() {
          if (!isConversationOwner(toolCtx)) return refusal(NOT_OWNER_MESSAGE);
          const identity = sessionIdentityForTool(toolCtx);
          if (!identity) return refusal(NO_IDENTITY_MESSAGE);
          const prepared = (await callFor(toolCtx, "control_prepare_task_context", {
            ...identity,
            ...taskScope(toolCtx),
          })) as { disposition?: string; task_id?: string; reason_codes?: string[] };
          // Binding stays an authenticated operator action at the terminal, so
          // the owner needs their own conversation's identity to run it. They
          // cannot see it otherwise -- it is an internal host value -- and
          // without it the whole feature is unreachable from inside OpenClaw.
          // Handing the owner a ready-to-run command is the same "one useful
          // next command" the CLI gives everywhere else. This discloses nothing
          // a non-owner can obtain: the gate above already refused them.
          const bindCommand =
            `atmem task bind DB_PATH TASK_ID --subject SUBJECT ` +
            `--agent ${agentIdFor(toolCtx)} --workspace ${workspaceIdFor(toolCtx) ?? "WORKSPACE"} ` +
            `--actor YOU --reason WHY --host-type ${identity.host_type} ` +
            `--session-key ${identity.session_key} --session-epoch ${identity.session_epoch} --yes`;
          if (prepared.disposition !== "injected") {
            return ok({
              bound: false,
              reason: (prepared.reason_codes ?? []).join(", ") || "not bound",
              bind_with: bindCommand,
            });
          }
          return ok({
            bound: true,
            task_id: prepared.task_id ?? null,
            rebind_with: bindCommand,
          });
        },
      }),
      { name: "task_binding_status" },
    );
  }

  api.logger.info(
    `${TAG} registered (db=${cfg.dbPath}, subject=${cfg.subject}, ` +
      `recall=${cfg.recall.enabled}, capture=${cfg.capture.enabled}, ` +
      `controlPlane=${cfg.controlPlane.enabled})`,
  );
}

export default {
  id: "memory-atmem",
  name: "Memory (atmem)",
  description: "Automatic, auditable memory for OpenClaw backed by AtMem",
  register,
};
