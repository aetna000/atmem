#!/usr/bin/env node
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { chmodSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { tmpdir } from "node:os";
import path from "node:path";

import plugin from "../dist/index.js";
import { AtmemClient } from "../dist/src/rpc-client.js";

const repoRoot = path.resolve(import.meta.dirname, "../../..");
process.env.PYTHONPATH = [repoRoot, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter);

function fakeApi(config, toolContext = {}) {
  const hooks = new Map();
  const tools = new Map();
  const services = [];
  const logs = [];
  const logger = {
    debug(message) { logs.push(String(message)); },
    info(message) { logs.push(String(message)); },
    warn(message) { logs.push(String(message)); },
    error(message) { logs.push(String(message)); },
  };
  const api = {
    pluginConfig: config,
    logger,
    on(name, handler) { hooks.set(name, handler); },
    registerTool(spec) {
      if (typeof spec === "function") {
        const tool = spec({
          sessionKey: "takeover-1",
          senderIsOwner: true,
          activeModel: { provider: "openai", modelId: "test-model" },
          ...toolContext,
        });
        tools.set(tool.name, tool);
        return;
      }
      tools.set(spec.name, spec);
    },
    registerService(service) { services.push(service); },
  };
  plugin.register(api);
  return { hooks, tools, services, logs };
}

function controlCli(...args) {
  const result = spawnSync("atmem", ["control", ...args, "--json"], {
    encoding: "utf8",
  });
  assert.equal(result.status, 0, result.stderr || result.stdout);
  return result.stdout.trim() ? JSON.parse(result.stdout) : null;
}

function blackboxCli(...args) {
  const result = spawnSync("python", ["-m", "atmem.cli", "blackbox", ...args, "--json"], {
    encoding: "utf8",
    cwd: repoRoot,
    env: { ...process.env, PYTHONPATH: repoRoot },
  });
  assert.equal(result.status, 0, result.stderr || result.stdout);
  return result.stdout.trim() ? JSON.parse(result.stdout) : null;
}


const dataDir = mkdtempSync(path.join(tmpdir(), "atmem-hooks-"));
const dbPath = path.join(dataDir, "memory.db");
const mediaRoot = path.join(dataDir, "openclaw-media");
mkdirSync(mediaRoot);
process.env.ATMEM_OPENCLAW_MEDIA_ROOT = mediaRoot;
const base = {
  command: "atmem",
  commandArgs: ["mcp", "--db", dbPath, "--subject", "hook-user"],
  dbPath,
  subject: "hook-user",
  recall: { enabled: true, maxRecords: 3, maxChars: 1200, minScore: 0.3, timeoutMs: 5000 },
  persona: { enabled: true, maxChars: 600, ttlSeconds: 3600 },
  capture: { enabled: true, captureAssistant: false },
  cacheAware: { enabled: true, compactReferences: true },
  tools: { enabled: true },
};

const missingEngine = new AtmemClient({
  command: `atmem-deliberately-missing-${process.pid}`,
  args: ["mcp"],
  defaultTimeoutMs: 1000,
});
await assert.rejects(
  missingEngine.hasTool("memory_recall"),
  /engine executable .* was not found.*Install the engine first.*pip install atmem/s,
);
missingEngine.close();

// Closing and immediately reconnecting must not let the old child's delayed
// exit event tear down the replacement process.
const reconnectClient = new AtmemClient({
  command: "atmem",
  args: ["mcp", "--db", dbPath, "--subject", "reconnect-user"],
  idleTimeoutMs: 60_000,
});
await reconnectClient.connect();
reconnectClient.close();
const reconnectResult = await reconnectClient.callTool("memory_recall", {
  query: "reconnect probe",
  limit: 1,
});
assert.ok(Array.isArray(reconnectResult));
reconnectClient.close();

const runtime = fakeApi(base);
const beforePrompt = runtime.hooks.get("before_prompt_build");
const agentEnd = runtime.hooks.get("agent_end");
const beforeWrite = runtime.hooks.get("before_message_write");

try {
  assert.equal(runtime.tools.size, 6);

  const observe = runtime.tools.get("atmem_observe");
  const attachmentBytes = Buffer.from("exact uploaded image bytes");
  const attachmentPath = path.join(mediaRoot, "upload.png");
  writeFileSync(attachmentPath, attachmentBytes);
  const messageReceived = runtime.hooks.get("message_received");
  await messageReceived(
    {
      content: "Analyze this upload",
      sessionKey: "takeover-1",
      metadata: {
        mediaPath: attachmentPath,
        mediaPaths: [attachmentPath],
        mediaType: "image/png",
        mediaTypes: ["image/png"],
      },
    },
    { sessionKey: "takeover-1" },
  );
  const autoObserved = await observe.execute("observe-auto-1", {
    text: "The upload contains a geometric logo.",
    modality: "image",
    segment: { region: "whole image", dimensions: { width: 640, height: 480 } },
  });
  assert.equal(autoObserved.details.status, "quarantined");
  assert.equal(autoObserved.details.provenanceSource, "openclaw-upload");
  assert.equal(
    autoObserved.details.mediaSha256,
    createHash("sha256").update(attachmentBytes).digest("hex"),
  );

  // OpenClaw can execute the inbound hook and the later agent tool in
  // separate plugin runtimes. The trusted upload binding must survive that
  // boundary instead of depending on one process-local Map.
  const separateRuntime = fakeApi(base);
  try {
    const crossRuntimeObserved = await separateRuntime.tools
      .get("atmem_observe")
      .execute("observe-cross-runtime-1", {
        text: "The separately executed tool can resolve the geometric logo upload.",
        modality: "image",
      });
    assert.equal(crossRuntimeObserved.details.status, "quarantined");
    assert.equal(crossRuntimeObserved.details.provenanceSource, "openclaw-upload");
    assert.equal(crossRuntimeObserved.details.mediaSha256, autoObserved.details.mediaSha256);
  } finally {
    for (const service of separateRuntime.services) await service.stop?.();
  }

  // Internal OpenClaw webchat does not broadcast message_received, and its
  // prompt hooks intentionally omit local attachment paths. The synchronous
  // transcript hook receives the current user message with canonical
  // MediaPath fields before the model can call tools, so it establishes the
  // trusted binding without scraping text or guessing the newest file.
  const webchatBytes = Buffer.from("exact webchat image bytes");
  const webchatPath = path.join(mediaRoot, "webchat-upload.png");
  writeFileSync(webchatPath, webchatBytes);
  const webchatPrompt = "Remember this webchat upload for later.";
  beforeWrite({
    message: {
      role: "user",
      content: webchatPrompt,
      idempotencyKey: "webchat-run-1:user",
      MediaPath: webchatPath,
      MediaPaths: [webchatPath],
      MediaType: "image/png",
      MediaTypes: ["image/png"],
    },
  }, { sessionKey: "takeover-1" });
  const webchatRuntime = fakeApi(base, { runId: "webchat-run-1" });
  try {
    const webchatObserved = await webchatRuntime.tools
      .get("atmem_observe")
      .execute("observe-webchat-runtime-1", {
        text: "The webchat upload is available through trusted structured metadata.",
        modality: "image",
      });
    assert.equal(webchatObserved.details.status, "quarantined");
    assert.equal(webchatObserved.details.success, true);
    assert.equal(webchatObserved.details.provenanceSource, "openclaw-upload");
    assert.equal(
      webchatObserved.details.mediaSha256,
      createHash("sha256").update(webchatBytes).digest("hex"),
    );
  } finally {
    for (const service of webchatRuntime.services) await service.stop?.();
  }

  const forgetArtifact = runtime.tools.get("atmem_forget_artifact");
  const artifactForgotten = await forgetArtifact.execute("forget-artifact-1", {
    media_sha256: autoObserved.details.mediaSha256,
    artifact_id: autoObserved.details.artifactId,
  });
  assert.equal(artifactForgotten.details.deleted, true);
  await messageReceived(
    { content: "A later text-only turn", sessionKey: "takeover-1", metadata: {} },
    { sessionKey: "takeover-1" },
  );
  await assert.rejects(
    observe.execute("observe-stale-1", {
      text: "This must not reuse the previous upload.",
      modality: "image",
    }),
    /No exact uploaded-file provenance is bound/,
  );

  await beforePrompt({ prompt: "My favorite color is teal." }, { sessionKey: "capture-1" });
  await agentEnd({ success: true, messages: [] }, { sessionKey: "capture-1" });

  const injected = await beforePrompt(
    { prompt: "What is my favorite color?" },
    { sessionKey: "recall-1" },
  );
  assert.equal(injected.prependContext, undefined);
  assert.ok(injected.appendSystemContext.includes("<user_persona>"));
  assert.ok(injected.appendContext.includes("<relevant_memories>"));
  assert.ok(injected.appendContext.includes("teal"));
  assert.match(injected.appendContext, /\[m:[a-f0-9]{8}\]/);
  assert.doesNotMatch(injected.appendContext, /\[rec_[a-f0-9]+\]/);

  const compatibleSearch = runtime.tools.get("memory_search");
  const searchResult = await compatibleSearch.execute("compat-search-1", {
    query: "favorite color",
    maxResults: 5,
  });
  const searchPayload = JSON.parse(searchResult.content[0].text);
  assert.ok(searchPayload.results.length >= 1);
  assert.match(searchPayload.results[0].path, /^atmem:\/\/record\/rec_/);
  assert.equal(typeof searchPayload.results[0].score, "number");

  const compatibleGet = runtime.tools.get("memory_get");
  const getResult = await compatibleGet.execute("compat-get-1", {
    path: searchPayload.results[0].path,
    from: 1,
    lines: 10,
  });
  const getPayload = JSON.parse(getResult.content[0].text);
  assert.ok(getPayload.text.includes("teal"));
  assert.equal(getResult.details.found, true);

  await beforePrompt(
    { prompt: "Actually, use blue as my favorite color going forward." },
    { sessionKey: "capture-2" },
  );
  await agentEnd({ success: true, messages: [] }, { sessionKey: "capture-2" });
  const corrected = await beforePrompt(
    { prompt: "What is my favorite color?" },
    { sessionKey: "recall-2" },
  );
  assert.ok(corrected.appendSystemContext.includes("blue"));
  assert.ok(!corrected.appendSystemContext.includes("teal"));

  const forget = runtime.tools.get("atmem_forget");
  const forgotten = await forget.execute("forget-1", {
    utterance: "Forget my favorite color.",
  });
  assert.equal(forgotten.details.deleted, true);
  const afterForget = await beforePrompt(
    { prompt: "What is my favorite color?" },
    { sessionKey: "recall-3" },
  );
  assert.equal(afterForget?.appendSystemContext, undefined);
  assert.equal(afterForget?.appendContext, undefined);

  const cleaned = beforeWrite({
    message: {
      role: "user",
      content:
        "Question\n<user_persona>\n- private\n</user_persona>\n" +
        "<relevant_memories>\n- private\n</relevant_memories>",
    },
  });
  assert.equal(cleaned.message.content, "Question");

  const toolFree = fakeApi({ ...base, tools: { enabled: false } });
  assert.equal(toolFree.tools.size, 0);
  for (const service of toolFree.services) await service.stop?.();

  const legacy = fakeApi({
    ...base,
    dbPath: path.join(dataDir, "legacy.db"),
    commandArgs: ["mcp", "--db", path.join(dataDir, "legacy.db"), "--subject", "legacy"],
    cacheAware: { enabled: false, compactReferences: false },
    tools: { enabled: false },
  });
  const legacyBefore = legacy.hooks.get("before_prompt_build");
  const legacyEnd = legacy.hooks.get("agent_end");
  await legacyBefore({ prompt: "My home city is Sydney." }, { sessionKey: "legacy-capture" });
  await legacyEnd({ success: true, messages: [] }, { sessionKey: "legacy-capture" });
  const legacyInjection = await legacyBefore(
    { prompt: "What is my home city?" },
    { sessionKey: "legacy-recall" },
  );
  assert.ok(legacyInjection.prependContext.includes("Sydney"));
  assert.equal(legacyInjection.appendContext, undefined);
  assert.equal(legacyInjection.appendSystemContext, undefined);
  for (const service of legacy.services) await service.stop?.();

  // Delegated context is an exclusive, exact prepend contribution. The
  // adapter keeps it only until llm_input proves one exact occurrence.
  const delegatedLog = path.join(dataDir, "delegated-rpc.jsonl");
  const delegatedServer = path.join(dataDir, "delegated-mcp.py");
  const exactDelegated = "Reviewed context 🧠\r\nKeep these bytes.";
  const exactTask = "<<<atmem-governed-task-data>>>\ntask: task-1\nremaining: verify\n<<<end-atmem-governed-task-data>>>";
  writeFileSync(delegatedServer, `#!/usr/bin/env python3
import json, sys
LOG = ${JSON.stringify(delegatedLog)}
EXACT = ${JSON.stringify(exactDelegated)}
TASK = ${JSON.stringify(exactTask)}
for line in sys.stdin:
    request = json.loads(line)
    if request.get("method") == "notifications/initialized":
        continue
    if request.get("method") == "initialize":
        result = {"protocolVersion":"2025-06-18","capabilities":{},"serverInfo":{"name":"fake","version":"1"}}
    elif request.get("method") == "tools/call":
        params = request.get("params") or {}
        name = params.get("name")
        with open(LOG, "a", encoding="utf-8") as handle:
            handle.write(json.dumps({"name": name, "arguments": params.get("arguments")}, separators=(",", ":")) + "\\n")
        if name == "control_prepare_task_context":
            value = {"disposition":"injected","context":TASK,"context_sha256":"sha256:${createHash("sha256").update(exactTask).digest("hex")}","delivery_id":"task-delivery-1","revision":4,"reason_codes":[]}
        elif name == "control_prepare":
            arguments = params.get("arguments") or {}
            query = arguments.get("query") or ""
            if not arguments.get("user_id"):
                value = {"inject":False,"context":"","authority":"delegated","decision":"provider_failure","mode":"active","candidate_ids":[],"reason":"missing authenticated user"}
            elif "withhold" in query:
                value = {"inject":False,"context":"","authority":"delegated","decision":"withhold","mode":"active","candidate_ids":[],"context_receipt_id":"receipt-withhold"}
            elif "reject" in query:
                value = {"inject":False,"context":"","authority":"delegated","decision":"provider_failure","mode":"active","candidate_ids":[],"reason":"signature verification failed"}
            elif "corrupt" in query:
                value = {"inject":True,"context":EXACT,"context_sha256":"${"0".repeat(64)}","authority":"delegated","decision":"inject","result_sha256":"${"e".repeat(64)}","exposure_id":"delivery-corrupt","context_receipt_id":"receipt-corrupt","receipt":{"id":"receipt-corrupt","sha256":"${"f".repeat(64)}"},"provider":{"id":"fixture-provider","version":"test","instance_id":"local"},"mode":"active","candidate_ids":[]}
            elif "fallback" in query:
                value = {"inject":True,"context":"native fallback context","authority":"atmem_fallback","decision":"native_context","native_fallback":True,"mode":"active","candidate_ids":["native-1"]}
            else:
                value = {"inject":True,"context":EXACT,"context_sha256":"${createHash("sha256").update(exactDelegated).digest("hex")}","authority":"delegated","decision":"inject","result_sha256":"${"c".repeat(64)}","exposure_id":"delivery-1","context_receipt_id":"receipt-1","receipt":{"id":"receipt-1","sha256":"${"d".repeat(64)}"},"provider":{"id":"fixture-provider","version":"test","instance_id":"local"},"mode":"active","candidate_ids":[]}
        else:
            value = {"ok": True}
        result = {"content":[{"type":"text","text":json.dumps(value, separators=(",", ":"))}],"isError":False}
    else:
        result = {}
    print(json.dumps({"jsonrpc":"2.0","id":request.get("id"),"result":result}, separators=(",", ":")), flush=True)
`);
  chmodSync(delegatedServer, 0o700);
  const delegatedRuntime = fakeApi({
    ...base,
    command: delegatedServer,
    controlPlane: { enabled: true, statePath: path.join(dataDir, "unused-state.json") },
    agentWorkspaces: { main: path.join(dataDir, "delegated-workspace") },
    delegatedContext: { userId: "owner", requireOwner: true },
  });
  const delegatedCtx = {
    agentId: "main",
    sessionKey: "delegated-session",
    sessionId: "delegated-session",
    runId: "delegated-run",
    senderIsOwner: true,
  };
  const delegatedInsertion = await delegatedRuntime.hooks.get("before_prompt_build")(
    { prompt: "What context should I use?" },
    delegatedCtx,
  );
  assert.equal(delegatedInsertion.prependContext, exactDelegated);
  assert.equal(delegatedInsertion.appendContext, undefined);
  const delegatedModelInput = {
    runId: "delegated-run",
    sessionId: "delegated-session",
    provider: "anthropic",
    model: "test",
    prompt: exactDelegated + "\nWhat context should I use?",
    historyMessages: [],
    imagesCount: 0,
    tools: [],
  };
  await delegatedRuntime.hooks.get("llm_input")(delegatedModelInput, delegatedCtx);
  await delegatedRuntime.hooks.get("llm_input")(delegatedModelInput, delegatedCtx);
  const withheld = await delegatedRuntime.hooks.get("before_prompt_build")(
    { prompt: "withhold this turn" },
    { ...delegatedCtx, sessionKey: "withhold", sessionId: "withhold", runId: "withhold" },
  );
  assert.equal(withheld, undefined);
  const rejected = await delegatedRuntime.hooks.get("before_prompt_build")(
    { prompt: "reject invalid signed result" },
    { ...delegatedCtx, sessionKey: "reject", sessionId: "reject", runId: "reject" },
  );
  assert.equal(rejected, undefined);
  const corrupt = await delegatedRuntime.hooks.get("before_prompt_build")(
    { prompt: "corrupt local handoff" },
    { ...delegatedCtx, sessionKey: "corrupt", sessionId: "corrupt", runId: "corrupt" },
  );
  assert.equal(corrupt, undefined);
  const fallback = await delegatedRuntime.hooks.get("before_prompt_build")(
    { prompt: "fallback this turn" },
    { ...delegatedCtx, sessionKey: "fallback", sessionId: "fallback", runId: "fallback" },
  );
  assert.equal(fallback.appendContext, "native fallback context");
  assert.equal(fallback.prependContext, undefined);
  const taskCtx = { ...delegatedCtx, taskId: "task-1", sessionKey: "task", sessionId: "task", runId: "task" };
  const taskInsertion = await delegatedRuntime.hooks.get("before_prompt_build")(
    { prompt: "Continue the exact governed task" },
    taskCtx,
  );
  assert.equal(taskInsertion.prependContext, exactDelegated);
  assert.equal(taskInsertion.appendContext, exactTask);
  await delegatedRuntime.hooks.get("agent_end")(
    { success: true, messages: [], runId: "task" },
    taskCtx,
  );
  const missingOwner = await delegatedRuntime.hooks.get("before_prompt_build")(
    { prompt: "missing owner" },
    { ...delegatedCtx, sessionKey: "missing", sessionId: "missing", runId: "missing", senderIsOwner: false },
  );
  assert.equal(missingOwner, undefined);
  const delegatedCalls = readFileSync(delegatedLog, "utf8")
    .split("\n")
    .filter(Boolean)
    .map((line) => JSON.parse(line));
  assert.equal(JSON.stringify(delegatedCalls).includes(exactDelegated), false);
  assert.equal(
    delegatedCalls.filter((row) =>
      row.name === "control_record_blackbox_event" &&
      row.arguments?.event_type === "context.injected"
    ).length,
    1,
  );
  const authorizationEvents = delegatedCalls.filter((row) =>
    row.name === "control_record_blackbox_event" &&
    row.arguments?.event_type === "context.provider_authorization"
  );
  assert.equal(authorizationEvents.length, 6);
  assert.equal(authorizationEvents[0].arguments.context_receipt_id, "receipt-1");
  assert.equal(
    delegatedCalls.filter((row) => row.name === "control_prepare").length,
    7,
  );
  assert.equal(
    delegatedCalls.filter((row) => row.name === "control_prepare_task_context").length,
    1,
  );
  assert.equal(
    delegatedCalls.filter((row) => row.name === "control_task_exposure_shown").length,
    1,
  );
  assert.equal(
    delegatedCalls.filter((row) =>
      row.name === "control_record_blackbox_event" &&
      row.arguments?.event_type === "task.context.exposed"
    ).length,
    1,
  );
  for (const service of delegatedRuntime.services) await service.stop?.();

  const takeover = fakeApi({
    ...base,
    takeoverActive: true,
    nativeWorkspace: path.join(dataDir, "openclaw-workspace"),
  });
  const takeoverBefore = takeover.hooks.get("before_prompt_build");
  const guided = await takeoverBefore(
    { prompt: "What do I remember about my favorite color?" },
    { sessionKey: "takeover-1" },
  );
  assert.ok(guided.appendSystemContext.includes("<atmem_memory_provider>"));
  assert.ok(guided.appendSystemContext.includes("MEMORY.md and memory/*"));
  assert.ok(guided.appendSystemContext.includes("Use memory_search"));
  assert.ok(guided.appendSystemContext.includes("intentionally unavailable"));
  assert.ok(guided.appendSystemContext.includes("Never call Bash"));
  assert.ok(guided.appendSystemContext.includes("Interpret intent semantically"));
  assert.ok(guided.appendSystemContext.includes("If the user's meaning is both"));
  assert.ok(takeover.tools.has("memory_search"));
  assert.ok(takeover.tools.has("memory_get"));
  assert.ok(takeover.tools.has("memory_remember"));
  assert.equal(typeof takeover.hooks.get("before_model_resolve"), "function");
  await takeover.hooks.get("before_model_resolve")(
    { prompt: "I like blue cars", messages: [], queuedInjections: [] },
    {
      sessionKey: "agent:main:takeover-1",
      sessionId: "takeover-1",
      runId: "run-blue",
    },
  );
  const remembered = await takeover.tools.get("memory_remember").execute(
    "remember-blue",
    { fact: "User likes blue cars." },
  );
  const rememberedPayload = JSON.parse(remembered.content[0].text);
  assert.equal(rememberedPayload.stored, true);
  assert.equal(rememberedPayload.fact, "User likes blue cars.");
  const blueGet = await takeover.tools.get("memory_get").execute(
    "get-blue",
    { path: `atmem://record/${rememberedPayload.record_id}` },
  );
  assert.match(blueGet.content[0].text, /User likes blue cars\./);
  const beforeTool = takeover.hooks.get("before_tool_call");
  assert.equal(typeof beforeTool, "function");
  const workspace = path.join(dataDir, "openclaw-workspace");
  const blockedShell = await beforeTool({
    toolName: "Bash",
    params: { command: "sed -n '1,200p' MEMORY.md", cwd: workspace },
  }, {});
  assert.equal(blockedShell.block, true);
  assert.match(blockedShell.blockReason, /memory_remember/);
  const blockedWrite = await beforeTool({
    toolName: "write_file",
    params: { path: path.join(workspace, "memory", "today.md"), content: "note" },
    derivedPaths: [path.join(workspace, "memory", "today.md")],
  }, {});
  assert.equal(blockedWrite.block, true);
  const blockedPatch = await beforeTool({
    toolName: "apply_patch",
    params: { patch: "*** Update File: MEMORY.md\n+preference" },
  }, {});
  assert.equal(blockedPatch.block, true);
  assert.equal(await beforeTool({
    toolName: "Bash",
    params: { command: "pwd && git status", cwd: workspace },
  }, {}), undefined);
  assert.equal(await beforeTool({
    toolName: "write_file",
    params: { path: "/tmp/unrelated/MEMORY.md", content: "project notes" },
    derivedPaths: ["/tmp/unrelated/MEMORY.md"],
  }, {}), undefined);
  for (const service of takeover.services) await service.stop?.();

  const migrationState = path.join(dataDir, "control-plane.json");
  const migrationRoot = path.join(dataDir, "migrations");
  controlCli(
    "shadow",
    "--host",
    "openclaw",
    "--state",
    migrationState,
    "--control-root",
    migrationRoot,
    "--no-configure",
  );
  const controlPlane = fakeApi({
    ...base,
    commandArgs: ["mcp", "--db", path.join(dataDir, "must-not-be-used.db")],
    controlPlane: { enabled: true, statePath: migrationState },
    tools: { enabled: true },
  });
  assert.equal(controlPlane.tools.size, 0);
  const safeBefore = controlPlane.hooks.get("before_prompt_build");
  const safeEnd = controlPlane.hooks.get("agent_end");
  const blackboxCtx = {
    sessionKey: "migration-1",
    sessionId: "migration-session-1",
    runId: "run-blackbox-1",
  };
  await controlPlane.hooks.get("before_model_resolve")(
    {
      runId: "run-blackbox-1",
      prompt: "Remember my terminal preference.",
      historyMessages: [],
      imagesCount: 0,
      tools: [{ name: "memory_remember" }],
    },
    blackboxCtx,
  );
  await controlPlane.hooks.get("llm_input")(
    {
      runId: "run-blackbox-1",
      sessionId: "migration-session-1",
      provider: "openai",
      model: "gpt-test",
      systemPrompt: "private system prompt",
      prompt: "Remember my terminal preference.",
      historyMessages: [],
      imagesCount: 0,
      tools: [{ name: "memory_remember" }],
    },
    blackboxCtx,
  );
  const captureOnly = await safeBefore(
    { prompt: "Remember that my preferred terminal is Ghostty." },
    blackboxCtx,
  );
  assert.equal(captureOnly, undefined);
  await controlPlane.hooks.get("before_tool_call")(
    {
      toolName: "memory_search",
      toolCallId: "blackbox-tool-1",
      runId: "run-blackbox-1",
      params: { query: "terminal" },
    },
    blackboxCtx,
  );
  await controlPlane.hooks.get("after_tool_call")(
    {
      toolName: "memory_search",
      toolCallId: "blackbox-tool-1",
      runId: "run-blackbox-1",
      params: { query: "terminal" },
      result: { found: true, private: "not stored except as a digest" },
      durationMs: 5,
    },
    blackboxCtx,
  );
  await controlPlane.hooks.get("llm_output")(
    {
      runId: "run-blackbox-1",
      sessionId: "migration-session-1",
      provider: "openai",
      model: "gpt-test",
      assistantTexts: ["I remembered your terminal preference."],
      usage: { input: 10, output: 6, total: 16 },
    },
    blackboxCtx,
  );
  await safeEnd({ runId: "run-blackbox-1", success: true, messages: [] }, blackboxCtx);
  const migrationStatus = controlCli("status", "--state", migrationState);
  assert.equal(migrationStatus.mode, "shadow");
  assert.equal(migrationStatus.changes_model_context, false);
  const flight = blackboxCli("verify", "run-blackbox-1", "--state", migrationState);
  assert.equal(flight.timeline_chain_valid, true);
  assert.equal(flight.structurally_complete, true);
  assert.equal(flight.verdict, "completed_successfully");
  assert.equal(
    flight.timeline.filter((entry) => entry.event_type === "turn.input").length,
    1,
    "before_model_resolve and before_prompt_build must observe one turn input",
  );
  const serializedFlight = JSON.stringify(flight);
  assert.doesNotMatch(serializedFlight, /private system prompt/);
  assert.doesNotMatch(serializedFlight, /I remembered your terminal preference/);

  // External CLI harnesses such as OpenClaw's claude-cli path can skip
  // before_model_resolve while still invoking the prompt, model, and terminal
  // hooks. before_prompt_build must provide the same authenticated turn-input
  // observation and source staging without requiring a host-side workaround.
  const claudeCliCtx = {
    sessionKey: "claude-cli-session",
    sessionId: "claude-cli-session",
    runId: "run-claude-cli-fallback",
  };
  await safeBefore(
    { prompt: "Recall my governed terminal preference." },
    claudeCliCtx,
  );
  await controlPlane.hooks.get("llm_input")(
    {
      runId: "run-claude-cli-fallback",
      sessionId: "claude-cli-session",
      provider: "anthropic",
      model: "claude-cli-test",
      systemPrompt: "private cli system prompt",
      prompt: "Recall my governed terminal preference.",
      historyMessages: [],
      imagesCount: 0,
      tools: [],
    },
    claudeCliCtx,
  );
  await controlPlane.hooks.get("llm_output")(
    {
      runId: "run-claude-cli-fallback",
      sessionId: "claude-cli-session",
      provider: "anthropic",
      model: "claude-cli-test",
      assistantTexts: ["Your governed preference is available."],
      usage: { input: 12, output: 7, total: 19 },
    },
    claudeCliCtx,
  );
  await safeEnd(
    {
      runId: "run-claude-cli-fallback",
      success: true,
      messages: [],
    },
    claudeCliCtx,
  );
  const claudeCliFlight = blackboxCli(
    "verify",
    "run-claude-cli-fallback",
    "--state",
    migrationState,
  );
  assert.equal(claudeCliFlight.structurally_complete, true);
  assert.equal(claudeCliFlight.verdict, "completed_successfully");
  assert.equal(
    claudeCliFlight.timeline.filter((entry) => entry.event_type === "turn.input").length,
    1,
  );
  for (const service of controlPlane.services) await service.stop?.();

  // Managed active mode uses the normal memory engine and a separate private
  // control process for Black Box evidence. Recording must survive cutover.
  const activeRecorder = fakeApi({
    ...base,
    takeoverActive: true,
    nativeWorkspace: path.join(dataDir, "openclaw-workspace"),
    controlPlane: {
      enabled: false,
      statePath: migrationState,
      blackboxEnabled: true,
    },
  });
  const activeCtx = {
    sessionKey: "active-session",
    sessionId: "active-session",
    runId: "run-blackbox-active",
  };
  await activeRecorder.hooks.get("before_model_resolve")(
    { prompt: "Check the active recorder.", attachments: [] },
    activeCtx,
  );
  await activeRecorder.hooks.get("before_prompt_build")(
    { prompt: "Check the active recorder.", messages: [] },
    activeCtx,
  );
  await activeRecorder.hooks.get("llm_input")(
    {
      runId: "run-blackbox-active",
      sessionId: "active-session",
      provider: "openai",
      model: "gpt-test",
      prompt: "Check the active recorder.",
      systemPrompt: "private active system prompt",
      historyMessages: [],
      imagesCount: 0,
      tools: [],
    },
    activeCtx,
  );
  await activeRecorder.hooks.get("before_tool_call")(
    {
      toolName: "memory_search",
      toolCallId: "active-tool-1",
      runId: "run-blackbox-active",
      params: { query: "recorder" },
      derivedPaths: ["/private/example/path"],
    },
    activeCtx,
  );
  await activeRecorder.hooks.get("after_tool_call")(
    {
      toolName: "memory_search",
      toolCallId: "active-tool-1",
      runId: "run-blackbox-active",
      params: { query: "recorder" },
      result: { found: true },
      durationMs: 4,
    },
    activeCtx,
  );
  await activeRecorder.hooks.get("llm_output")(
    {
      runId: "run-blackbox-active",
      sessionId: "active-session",
      provider: "openai",
      model: "gpt-test",
      assistantTexts: ["The active recorder is working."],
      usage: { input: 8, output: 5, total: 13 },
    },
    activeCtx,
  );
  await activeRecorder.hooks.get("agent_end")(
    { runId: "run-blackbox-active", success: true, messages: [], durationMs: 9 },
    activeCtx,
  );
  const activeFlight = blackboxCli(
    "verify",
    "run-blackbox-active",
    "--state",
    migrationState,
  );
  assert.equal(activeFlight.structurally_complete, true, JSON.stringify(activeFlight));
  assert.equal(activeFlight.verdict, "completed_successfully");
  assert.doesNotMatch(JSON.stringify(activeFlight), /private\/example\/path/);
  for (const service of activeRecorder.services) await service.stop?.();

  // Persistent agents sharing an exact workspace share one subject. Agents
  // with distinct (including nested) workspaces remain isolated at every
  // direct tool boundary.
  const multiConfig = {
    ...base,
    defaultAgentId: "main",
    agentSubjects: {
      main: "workspace-shared",
      helper: "workspace-shared",
      research: "workspace-research",
      nested: "workspace-nested",
    },
    agentWorkspaces: {
      main: "/workspace",
      helper: "/workspace",
      research: "/research",
      nested: "/workspace/projects/nested",
    },
  };
  const seed = new AtmemClient({
    command: "atmem",
    args: ["mcp", "--db", dbPath, "--subject", "unused-default"],
  });
  await seed.callTool("memory_remember", {
    subject_id: "workspace-shared",
    message: "Remember that the shared agent codeword is ALPHA-SHARED.",
    source_type: "user_message",
  });
  await seed.callTool("memory_remember", {
    subject_id: "workspace-research",
    message: "Remember that the research agent codeword is CHARLIE-RESEARCH.",
    source_type: "user_message",
  });
  const mainAgent = fakeApi(multiConfig, { agentId: "main", sessionKey: "agent:main:tool" });
  const helperAgent = fakeApi(multiConfig, { agentId: "helper", sessionKey: "agent:helper:tool" });
  const researchAgent = fakeApi(multiConfig, { agentId: "research", sessionKey: "agent:research:tool" });
  const mainSearch = await mainAgent.tools.get("atmem_search").execute("multi-main", { query: "ALPHA-SHARED" });
  const helperSearch = await helperAgent.tools.get("atmem_search").execute("multi-helper", { query: "ALPHA-SHARED" });
  const researchSearch = await researchAgent.tools.get("atmem_search").execute("multi-research", { query: "CHARLIE-RESEARCH" });
  assert.match(mainSearch.content[0].text, /ALPHA-SHARED/);
  assert.match(helperSearch.content[0].text, /ALPHA-SHARED/);
  assert.doesNotMatch(mainSearch.content[0].text, /CHARLIE-RESEARCH/);
  assert.match(researchSearch.content[0].text, /CHARLIE-RESEARCH/);
  assert.doesNotMatch(researchSearch.content[0].text, /ALPHA-SHARED/);
  const unknownAgent = fakeApi(multiConfig, { agentId: "unknown" });
  await assert.rejects(
    unknownAgent.tools.get("atmem_search").execute("multi-unknown", { query: "codeword" }),
    /unmapped OpenClaw persistent agent/,
  );
  for (const instance of [mainAgent, helperAgent, researchAgent, unknownAgent]) {
    for (const service of instance.services) await service.stop?.();
  }
  seed.close();

  console.log(
    "hooks: direct engine and fail-closed memory control plane paths verified",
  );
} finally {
  for (const service of runtime.services) await service.stop?.();
  rmSync(dataDir, { recursive: true, force: true });
}
