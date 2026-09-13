import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import { ExecutionSpool } from "../dist/src/execution-spool.js";

const root = await mkdtemp(path.join(os.tmpdir(), "atmem-execution-spool-"));
const spoolPath = path.join(root, "spool.json");
try {
  const first = new ExecutionSpool(spoolPath, 4);
  const event = await first.enqueue({ event_type: "turn.input", run_id: "run-1", payload: {} });
  assert.equal((await first.snapshot()).pending.length, 1);
  await assert.rejects(first.flush(async () => { throw new Error("offline"); }), /offline/);
  assert.equal((await first.snapshot()).pending.length, 1, "failed delivery remains durable");

  const restarted = new ExecutionSpool(spoolPath, 4);
  const seen = [];
  assert.equal(await restarted.flush(async value => {
    seen.push(value);
    return { durably_accepted: true, decision: "replayed" };
  }), 1);
  assert.equal(seen[0].event_id, event.event_id);
  assert.equal((await restarted.snapshot()).pending.length, 0);

  await restarted.enqueue({ event_type: "model.output", run_id: "conflict-run", payload: {
    _atmem_evidence: { assistant_texts: ["PLANTED-SPOOL-SECRET"] },
  } });
  assert.equal(await restarted.flush(async () => ({
    durably_accepted: false, durably_classified: true, decision: "conflict",
  })), 1);
  assert.equal((await restarted.snapshot()).pending.length, 0);

  for (let index = 0; index < 6; index += 1) {
    await restarted.enqueue({ event_type: "model.input", run_id: "run-capacity", payload: {} });
  }
  const bounded = await restarted.snapshot();
  assert.ok(bounded.pending.length <= 4);
  assert.ok(bounded.pending.some(item => item.event_type === "capture.gap"));
  const stored = JSON.parse(await readFile(spoolPath, "utf8"));
  assert.equal(stored.format, "atmem-openclaw-encrypted-execution-spool-v2");
  assert.equal((await readFile(spoolPath, "utf8")).includes("PLANTED-SPOOL-SECRET"), false);
  const retentionPath = path.join(root, "retention.json");
  const expiring = new ExecutionSpool(retentionPath, 4, -1);
  await expiring.enqueue({ event_type: "turn.input", run_id: "expired", payload: {} });
  await expiring.enqueue({ event_type: "turn.input", run_id: "current", payload: {} });
  const retained = await expiring.snapshot();
  assert.ok(retained.pending.some(item => item.event_type === "capture.gap" && item.payload?.reason === "spool_retention_expired"));
  console.log("execution spool: restart, durable ack and bounded-loss checks passed");
} finally {
  await rm(root, { recursive: true, force: true });
}
