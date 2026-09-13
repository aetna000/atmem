import assert from "node:assert/strict";
import { ToolObservations } from "../dist/src/tool-observations.js";
import { toolErrorReason } from "../dist/src/tool-errors.js";

assert.equal(toolErrorReason("Fetch failed (403): https://host/private?token=secret\nstack and private content"), "Fetch failed (403): [redacted-url]");
assert.equal(toolErrorReason("Timeout"), "Timeout");
assert.equal(toolErrorReason({ content: [{ type: "text", text: "DNS lookup failed" }] }), "DNS lookup failed");
assert.equal(toolErrorReason({ error: { message: "Connection refused" } }), "Connection refused");
assert.equal(toolErrorReason({}), undefined);
assert.equal(toolErrorReason("x".repeat(1000)).length, 512);
const redacted = toolErrorReason('Failure token=secret password="pass word" Bearer abc sk-123abc /private/file user@example.com "private body"');
assert.doesNotMatch(redacted, /secret|pass word|abc|private|example/);

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
  if (variant === "error") { e.data.isError = true; e.data.result = { error: "Read failed: permission denied" }; }
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
  if (variant === "conflict") recorder.observe({ ...event, data: {...event.data, isError: true, result: { error: "Conflicting outcome" }} });
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

{
  const { recorder, data } = fixture();
  recorder.observe({ ...event, data: { ...event.data, isError: true,
    result: { content: [{ type: "text", text: "Fetch failed (403) https://private.example/token" }] } } });
  const recorded = [];
  await recorder.flush(ctx, async saved => recorded.push(saved));
  assert.equal(recorded[0].result.reason, "Fetch failed (403) [redacted-url]");
  assert.ok(!JSON.stringify([...data.values()]).includes("private.example"));
}

// Real host wrapper shape: only its HTTP diagnostic may survive, not page text.
const wrapped403 = 'SECURITY NOTICE: external content\n\n<<<EXTERNAL_UNTRUSTED_CONTENT id="abcdef">>>\nSource: API\n---\nWeb fetch failed (403): SECURITY NOTICE: nested wrapper\nprivate page body';
assert.equal(toolErrorReason(wrapped403), 'Web fetch failed (403)');
assert.equal(toolErrorReason('SECURITY NOTICE: external content\nprivate text'), undefined);
