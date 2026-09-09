import assert from "node:assert/strict";
import { ToolObservations } from "../dist/src/tool-observations.js";

const ctx = { runId: "run", agentId: "main", sessionId: "generation", sessionKey: "session" };
const event = { runId: "run", sessionKey: "session", stream: "tool", data: {
  phase: "result", name: "Read", toolCallId: "call", isError: false, result: "dummy content",
} };
function fixture() {
  const data = new Map();
  const access = {
    setRunContext({runId, namespace, value}) { data.set(`${runId}:${namespace}`, structuredClone(value)); return true; },
    getRunContext({runId, namespace}) { return structuredClone(data.get(`${runId}:${namespace}`)); },
  };
  const recorder = new ToolObservations(access, x => `digest:${String(x).length}`);
  recorder.request("read", "call", { ...ctx, config: { secret: "never retain" } });
  assert.ok(!JSON.stringify([...data.values()]).includes("never retain"));
  return {recorder, access, data};
}
for (const variant of ["ok", "error", "missing", "wrong-run", "wrong-session", "wrong-epoch", "wrong-agent", "wrong-tool", "unknown-call", "incomplete", "no-result", "no-outcome", "conflict", "typed", "reloaded"]) {
  const { recorder, access, data } = fixture();
  const e = structuredClone(event);
  if (variant === "error") e.data.isError = true;
  if (variant === "wrong-run") e.runId = "other";
  if (variant === "wrong-session") e.sessionKey = "other";
  if (variant === "wrong-epoch") e.sessionId = "other";
  if (variant === "wrong-agent") e.agentId = "other";
  if (variant === "wrong-tool") e.data.name = "Bash";
  if (variant === "unknown-call") e.data.toolCallId = "other";
  if (variant === "incomplete") e.data.incomplete = true;
  if (variant === "no-result") delete e.data.result;
  if (variant === "no-outcome") delete e.data.isError;
  if (variant !== "missing") recorder.observe(e);
  if (variant === "conflict") recorder.observe({ ...event, data: {...event.data, isError: true} });
  if (variant === "typed") recorder.completed("call", ctx);
  const active = variant === "reloaded" ? new ToolObservations(access, String) : recorder;
  const completed = [];
  await active.flush(ctx, async r => completed.push(r));
  await active.flush(ctx, async r => completed.push(r));
  assert.equal(completed.length, ["ok", "error", "reloaded"].includes(variant) ? 1 : 0, variant);
  if (completed.length) assert.equal(completed[0].result.error, variant === "error");
  assert.ok(!JSON.stringify([...data.values()]).includes("dummy content"));
}
console.log("tool observations: scoped terminal results, errors, gaps, conflict, reload and deduplication passed");

const { observationContext } = await import("../dist/src/tool-observations.js");
const unavailable = { setRunContext() { return false; }, getRunContext() { return undefined; } };
const first = new ToolObservations(observationContext(unavailable, "fixture-installation"), String);
first.request("exec", "reload-call", ctx);
const second = new ToolObservations(observationContext(unavailable, "fixture-installation"), String);
second.observe({ ...event, data: { ...event.data, name: "Bash", toolCallId: "reload-call" } });
const isolated = new ToolObservations(observationContext(unavailable, "other-installation"), String);
const isolatedResults = [];
await isolated.flush(ctx, async r => isolatedResults.push(r));
assert.equal(isolatedResults.length, 0);
const reloadResults = [];
await second.flush(ctx, async r => reloadResults.push(r));
assert.equal(reloadResults.length, 1);
const third = new ToolObservations(observationContext(unavailable, "fixture-installation"), String);
await third.flush(ctx, async r => reloadResults.push(r));
assert.equal(reloadResults.length, 1);
console.log("tool observations: denied host writes, registry reload, installation isolation and replay passed");
