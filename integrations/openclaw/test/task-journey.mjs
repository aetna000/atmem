#!/usr/bin/env node
/**
 * The governed-task journey, end to end, against a real control-plane server.
 *
 * Spec 007 Amendment A, T079. This spawns `atmem control mcp` and drives the
 * exact tool calls the bridge makes, in the order a real turn makes them, so
 * the whole chain is exercised rather than mocked:
 *
 *   bind (operator, CLI) -> a turn carrying no task identity is delivered its
 *   bound task -> exposure confirmed once -> progress reported by the model's
 *   own tool -> premature completion denied -> unbind -> the next turn
 *   withholds.
 *
 * Usage: node test/task-journey.mjs [--command /path/to/atmem]
 */

import { spawn, spawnSync } from "node:child_process";
import { createInterface } from "node:readline";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import assert from "node:assert/strict";

const commandIndex = process.argv.indexOf("--command");
const command = commandIndex > -1 ? process.argv[commandIndex + 1] : "atmem";

const dataDir = mkdtempSync(path.join(tmpdir(), "atmem-task-journey-"));
const statePath = path.join(dataDir, "control.json");
// The control plane owns the subject; the journey follows it rather than
// asserting one, so a default change upstream does not silently unbind the test.
const SUBJECT = "local-user";
const AGENT = "default-agent";
const WORKSPACE = "default-workspace";
const IDENTITY = {
  host_type: "openclaw",
  session_key: "conversation-1",
  session_epoch: "generation-1",
};

function cli(args, { expectFailure = false } = {}) {
  const result = spawnSync(command, args, { encoding: "utf8" });
  if (!expectFailure) {
    assert.equal(
      result.status, 0,
      `${args.join(" ")} failed: ${result.stdout}${result.stderr}`,
    );
  }
  return result;
}

// --- a real control plane, shadow-free and explicitly enabled ---------------

const memoryDb = path.join(dataDir, "memories.db");
cli(["control", "shadow", "--state", statePath, "--host", "generic",
     "--control-root", path.join(dataDir, "migrations"),
     "--memory-db", memoryDb, "--no-configure"]);
cli(["control", "activate", "--state", statePath, "--yes"]);

const stateDoc = JSON.parse(
  cli(["control", "status", "--state", statePath, "--json"]).stdout,
);
assert.equal(stateDoc.subject_id, SUBJECT, "the control plane chose a different subject");
const scope = ["--subject", SUBJECT, "--agent", AGENT, "--workspace", WORKSPACE];

cli(["task", "enable", memoryDb, ...scope]);
cli(["task", "start", memoryDb, "--task-id", "migrate", "--goal", "Ship the migration",
     ...scope, "--actor", "operator@example.com",
     "--required-item", "schema=Apply the schema change",
     "--required-item", "verify=Verify row counts"]);

// --- the server the bridge talks to ----------------------------------------

const child = spawn(command, ["control", "mcp", "--state", statePath], {
  stdio: ["pipe", "pipe", "inherit"],
  env: process.env,
});
const reader = createInterface({ input: child.stdout });
const pending = new Map();
let nextId = 1;

reader.on("line", (line) => {
  if (!line.trim()) return;
  const message = JSON.parse(line);
  if (message.id !== undefined && pending.has(message.id)) {
    const { resolve, timer } = pending.get(message.id);
    pending.delete(message.id);
    clearTimeout(timer);
    resolve(message);
  }
});

function request(method, params) {
  const id = nextId++;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      if (pending.delete(id)) reject(new Error(`${method} timed out`));
    }, 15_000);
    pending.set(id, { resolve, timer });
    child.stdin.write(JSON.stringify({ jsonrpc: "2.0", id, method, params }) + "\n");
  });
}

async function callTool(name, args) {
  const response = await request("tools/call", { name, arguments: args });
  assert.equal(response.error, undefined, `${name}: ${JSON.stringify(response.error)}`);
  return JSON.parse(response.result.content[0].text);
}

const routing = { agent_id: AGENT, workspace_id: WORKSPACE };

try {
  await request("initialize", {});

  // The three write tools must actually be published, or a model cannot reach
  // any of this no matter what the manager supports.
  const tools = (await request("tools/list", {})).result.tools.map((t) => t.name);
  for (const name of [
    "control_prepare_task_context",
    "control_observe_task_step",
    "control_propose_task_delta",
    "control_request_task_lifecycle",
  ]) {
    assert.ok(tools.includes(name), `${name} is not published to the host`);
  }

  // 1. Unbound: a turn carrying no task identity gets nothing. This is the
  //    behaviour before an operator binds, and the behaviour a legacy install
  //    keeps forever.
  const unbound = await callTool("control_prepare_task_context", {
    ...IDENTITY, ...routing,
  });
  assert.equal(unbound.disposition, "withheld");
  assert.equal(unbound.context, "");
  assert.deepEqual(unbound.reason_codes, ["task_context_selection_required"]);

  // 2. The operator binds this conversation from the terminal.
  cli(["task", "bind", memoryDb, "migrate", ...scope,
       "--actor", "operator@example.com", "--reason", "drive it from this chat",
       "--host-type", IDENTITY.host_type,
       "--session-key", IDENTITY.session_key,
       "--session-epoch", IDENTITY.session_epoch, "--yes"]);

  // 3. The same turn shape now delivers, with no host task identity anywhere.
  const delivered = await callTool("control_prepare_task_context", {
    ...IDENTITY, ...routing,
  });
  assert.equal(delivered.disposition, "injected");
  assert.equal(delivered.task_id, "migrate");
  assert.ok(delivered.context.includes("Ship the migration"));
  assert.ok(delivered.delivery_id);

  // 4. Exposure is confirmed exactly once.
  assert.deepEqual(
    await callTool("control_task_exposure_shown", { delivery_id: delivered.delivery_id }),
    { confirmed: true },
  );
  assert.deepEqual(
    await callTool("control_task_exposure_shown", { delivery_id: delivered.delivery_id }),
    { confirmed: false },
  );

  // 5. The agent reports progress against its own task.
  const progressed = await callTool("control_propose_task_delta", {
    ...IDENTITY, ...routing,
    task_id: "migrate",
    base_revision: delivered.revision,
    idempotency_key: "run-1:tool-1",
    operations: [{ kind: "set_item_status", item_id: "schema", status: "completed" }],
    adapter: "openclaw",
    // Completing an item requires evidence. A host citing its own tool call is
    // asserting, not verifying, and AtMem records it at that assurance.
    evidence: [{ kind: "tool_call", reference_id: "run-1-tool-1" }],
  });
  assert.equal(progressed.outcome, "accepted", JSON.stringify(progressed));
  assert.equal(progressed.resulting_revision, delivered.revision + 1);

  // 6. A replayed hook collapses to the same decision, not a second revision.
  const replayed = await callTool("control_propose_task_delta", {
    ...IDENTITY, ...routing,
    task_id: "migrate",
    base_revision: delivered.revision,
    idempotency_key: "run-1:tool-1",
    operations: [{ kind: "set_item_status", item_id: "schema", status: "completed" }],
    adapter: "openclaw",
    evidence: [{ kind: "tool_call", reference_id: "run-1-tool-1" }],
  });
  assert.equal(replayed.resulting_revision, progressed.resulting_revision);

  // 7. Completion is denied while a required item is outstanding. The agent
  //    asked; the gate decided.
  const denied = await callTool("control_request_task_lifecycle", {
    ...IDENTITY, ...routing,
    task_id: "migrate",
    action: "complete",
    expected_revision: progressed.resulting_revision,
    idempotency_key: "run-1:end",
    adapter: "openclaw",
  });
  assert.equal(denied.reason_code, "required_items_incomplete");

  // 8. A conversation may not touch a task it is not bound to.
  cli(["task", "start", memoryDb, "--task-id", "docs-audit", "--goal", "Audit the docs",
       ...scope, "--actor", "operator@example.com", "--item", "scan=Scan endpoints"]);
  const crossed = await callTool("control_propose_task_delta", {
    ...IDENTITY, ...routing,
    task_id: "docs-audit",
    base_revision: 1,
    idempotency_key: "run-1:tool-9",
    operations: [{ kind: "set_item_status", item_id: "scan", status: "completed" }],
    adapter: "openclaw",
    evidence: [{ kind: "tool_call", reference_id: "run-1-tool-9" }],
  });
  assert.equal(crossed.reason_code, "host_task_not_bound_to_session");

  // 9. A terminal task is withheld, and that withholding is recorded: the
  //    binding still resolves, so there is a task to file the refusal under.
  cli(["task", "cancel", memoryDb, "migrate", ...scope,
       "--actor", "operator@example.com", "--reason", "superseded", "--yes"]);
  const terminal = await callTool("control_prepare_task_context", {
    ...IDENTITY, ...routing,
  });
  assert.equal(terminal.disposition, "withheld");
  assert.equal(terminal.context, "");
  assert.deepEqual(terminal.reason_codes, ["task_context_not_eligible"]);

  // 10. A reset conversation does not inherit the binding.
  const afterReset = await callTool("control_prepare_task_context", {
    ...IDENTITY, session_epoch: "generation-2", ...routing,
  });
  assert.equal(afterReset.disposition, "withheld");
  assert.deepEqual(afterReset.reason_codes, ["task_binding_stale_session"]);

  // 11. Revocation is the rollback, and it takes effect on the next turn.
  const bindings = JSON.parse(
    cli(["task", "bindings", memoryDb, ...scope, "--json"]).stdout,
  );
  cli(["task", "unbind", memoryDb, ...scope,
       "--binding-id", bindings.bindings[0].binding_id,
       "--actor", "operator@example.com", "--reason", "finished", "--yes"]);

  const afterRevoke = await callTool("control_prepare_task_context", {
    ...IDENTITY, ...routing,
  });
  assert.equal(afterRevoke.disposition, "withheld");
  assert.equal(afterRevoke.context, "");

  // 12. The counters tell the same story the journey did.
  const health = JSON.parse(
    cli(["task", "health", memoryDb, ...scope, "--json"]).stdout,
  );
  assert.equal(health.context.prepared > 0, true, "preparations were not counted");
  assert.equal(
    health.context.exposed, 1,
    `exactly one delivery reached the model: ${JSON.stringify(health.context)}`,
  );
  // The terminal-task refusal above resolved to a real task, so it is counted.
  // Turns where nothing resolved are not: there is no task to file them under,
  // and inventing one would put a task id in the evidence that never existed.
  assert.equal(
    health.context.withheld > 0, true,
    `resolved withholdings were not counted: ${JSON.stringify(health.context)}`,
  );
  assert.equal(health.integrity.valid, true);

  console.log(
    "task journey: bind -> deliver with no host task id -> expose once -> " +
      "report progress -> denied premature completion -> cross-session refused -> " +
      "reset withholds -> revoke withholds; counters agree",
  );
} finally {
  child.stdin.end();
  child.kill();
  rmSync(dataDir, { recursive: true, force: true });
}
