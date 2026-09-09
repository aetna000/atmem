import { createHash } from "node:crypto";
import type { OpenClawHookCtx } from "./types.js";

export interface HostToolEvent {
  runId: string;
  stream: string;
  sessionKey?: string;
  sessionId?: string;
  agentId?: string;
  data: Record<string, unknown>;
}
export interface RunContextAccess {
  setRunContext(patch: { runId: string; namespace: string; value: unknown; unset?: boolean }): boolean;
  getRunContext(params: { runId: string; namespace: string }): unknown;
}
export interface ToolEventSubscription {
  id: string;
  streams: string[];
  handle(event: HostToolEvent): void;
}
const CACHE_KEY = Symbol.for("atmem.tool-observation-cache.v1");
type CacheEntry = { value: unknown; expires: number };
const sharedCache = globalThis as unknown as Record<symbol, Map<string, CacheEntry>>;
const cache = sharedCache[CACHE_KEY] ??= new Map();

/** Some hosts deny run-context writes from tool hooks after registry reload.
 * Keep a bounded content-free process fallback, isolated by installation config.
 */
export function observationContext(host: RunContextAccess | undefined, scope: string): RunContextAccess {
  const keyFor = (runId: string, namespace: string) => JSON.stringify([scope, runId, namespace]);
  const sweep = () => {
    for (const [key, entry] of cache) if (entry.expires <= Date.now()) cache.delete(key);
    while (cache.size >= 2048) cache.delete(cache.keys().next().value!);
  };
  return {
    setRunContext(patch) {
      sweep();
      cache.set(keyFor(patch.runId, patch.namespace), { value: structuredClone(patch.value), expires: Date.now() + 600_000 });
      try { host?.setRunContext(patch); } catch { /* Process fallback remains bounded. */ }
      return true;
    },
    getRunContext(params) {
      sweep();
      const entry = cache.get(keyFor(params.runId, params.namespace));
      if (entry) return structuredClone(entry.value);
      try { return host?.getRunContext(params); } catch { return undefined; }
    },
  };
}

interface RequestObservation {
  ctx: OpenClawHookCtx;
  name: string;
  callId: string;
  hookCompleted?: boolean;
  result?: { digest: string; error: boolean };
  conflict?: boolean;
}
const INDEX = "atmem-tool-observations-v1";
const namespace = (id: string) => INDEX + "-" + createHash("sha256").update(id).digest("hex");
/** The CLI exposes its native names; the request hook exposes OpenClaw names. */
function canonical(name: string): string {
  const unwrapped = name.replace(/^mcp__openclaw__/, "");
  return ({ Read: "read", Bash: "exec" } as Record<string, string>)[unwrapped] ?? unwrapped;
}

/** Stores only scope, names and digests in bounded ephemeral observation context. */
export class ToolObservations {
  constructor(private readonly access: RunContextAccess, private readonly digest: (value: unknown) => string) {}

  request(name: string, id: string | undefined, ctx: OpenClawHookCtx): void {
    if (!id || !ctx.runId || !ctx.agentId || !ctx.sessionId || !ctx.sessionKey) return;
    const runId = ctx.runId;
    const ids = (this.access.getRunContext({ runId, namespace: INDEX }) as string[] | undefined) ?? [];
    if (ids.includes(id) || ids.length >= 256) return;
    // Never store the full hook context: it may contain host config/credentials.
    const scope = { runId, agentId: ctx.agentId, sessionId: ctx.sessionId, sessionKey: ctx.sessionKey };
    if (this.access.setRunContext({ runId, namespace: namespace(id), value: { ctx: scope, name, callId: id } })) {
      this.access.setRunContext({ runId, namespace: INDEX, value: [...ids, id] });
    }
  }

  completed(id: string | undefined, ctx: OpenClawHookCtx): void {
    if (!id || !ctx.runId) return;
    const key = { runId: ctx.runId, namespace: namespace(id) };
    const saved = this.access.getRunContext(key) as RequestObservation | undefined;
    if (saved && saved.ctx.sessionId === ctx.sessionId && saved.ctx.sessionKey === ctx.sessionKey && saved.ctx.agentId === ctx.agentId) {
      this.access.setRunContext({ ...key, value: { ...saved, hookCompleted: true } });
    }
  }

  observe(event: HostToolEvent): void {
    const d = event.data;
    if (event.stream !== "tool" || d.phase !== "result" || typeof d.toolCallId !== "string" ||
        typeof d.name !== "string" || typeof d.isError !== "boolean" ||
        !Object.hasOwn(d, "result") || d.incomplete === true || d.synthetic === true) return;
    const key = { runId: event.runId, namespace: namespace(d.toolCallId) };
    const saved = this.access.getRunContext(key) as RequestObservation | undefined;
    if (!saved || event.sessionKey !== saved.ctx.sessionKey ||
        (event.sessionId !== undefined && event.sessionId !== saved.ctx.sessionId) ||
        (event.agentId !== undefined && event.agentId !== saved.ctx.agentId) ||
        canonical(d.name) !== canonical(saved.name)) return;
    const result = { digest: this.digest(d.result), error: d.isError };
    const conflict = saved.conflict || (saved.result !== undefined &&
      (saved.result.digest !== result.digest || saved.result.error !== result.error));
    this.access.setRunContext({ ...key, value: { ...saved, result, conflict } });
  }

  async flush(ctx: OpenClawHookCtx, record: (saved: RequestObservation) => Promise<void>): Promise<void> {
    if (!ctx.runId) return;
    const runId = ctx.runId;
    const ids = (this.access.getRunContext({ runId, namespace: INDEX }) as string[] | undefined) ?? [];
    for (const id of ids) {
      const key = { runId, namespace: namespace(id) };
      const saved = this.access.getRunContext(key) as RequestObservation | undefined;
      if (saved && !saved.hookCompleted && !saved.conflict && saved.result &&
          saved.ctx.sessionKey === ctx.sessionKey && saved.ctx.sessionId === ctx.sessionId && saved.ctx.agentId === ctx.agentId) {
        await record(saved);
        this.access.setRunContext({ ...key, value: { ...saved, hookCompleted: true } });
      }
    }
  }
}
