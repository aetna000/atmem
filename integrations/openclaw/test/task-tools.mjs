#!/usr/bin/env node
/**
 * Governed task tools at the boundary a model actually sees.
 *
 * Spec 007 Amendment A, T070, T076 and T078.
 *
 * Scope, honestly: this drives the bridge's own logic through fabricated hook
 * and tool contexts. It proves how the bridge behaves when OpenClaw supplies,
 * or fails to supply, each optional identity field. It does not prove what a
 * real OpenClaw passes -- nothing here can, which is exactly why absence has
 * to fail closed rather than be assumed away.
 */

import assert from "node:assert/strict";

import {
  NOT_OWNER_MESSAGE,
  NO_IDENTITY_MESSAGE,
  describeDecision,
  isConversationOwner,
  ok,
  refusal,
  sessionIdentityForTool,
} from "../dist/src/task-tools.js";

// --- identity: all three parts or nothing ----------------------------------

assert.deepEqual(
  sessionIdentityForTool({ sessionKey: "conv-1", sessionId: "gen-1" }),
  { host_type: "openclaw", session_key: "conv-1", session_epoch: "gen-1" },
);

// sessionId alone still yields a complete identity: it is both the address of
// last resort and the generation.
assert.deepEqual(
  sessionIdentityForTool({ sessionId: "gen-1" }),
  { host_type: "openclaw", session_key: "gen-1", session_epoch: "gen-1" },
);

// No generation means no identity. The alternative -- binding on the session
// key alone -- is what lets a reset conversation inherit an earlier task.
assert.equal(sessionIdentityForTool({ sessionKey: "conv-1" }), undefined);
assert.equal(sessionIdentityForTool({}), undefined);

// --- epoch rotation across a reset -----------------------------------------
//
// OpenClaw changes sessionId when a conversation is reset or newly started.
// The bridge must present the new generation, so the old binding stops
// resolving instead of silently carrying over.

const beforeReset = sessionIdentityForTool({ sessionKey: "conv-1", sessionId: "gen-1" });
const afterReset = sessionIdentityForTool({ sessionKey: "conv-1", sessionId: "gen-2" });
assert.equal(beforeReset.session_key, afterReset.session_key);
assert.notEqual(
  beforeReset.session_epoch,
  afterReset.session_epoch,
  "a reset must rotate the epoch, or a recycled conversation inherits the task",
);

// A recycled session key with a recycled generation is the same conversation
// and is allowed to keep resolving; only the generation decides.
assert.deepEqual(
  sessionIdentityForTool({ sessionKey: "conv-1", sessionId: "gen-1" }),
  beforeReset,
);

// --- owner gate: absence is never permission -------------------------------

assert.equal(isConversationOwner({ senderIsOwner: true }), true);
for (const ctx of [
  { senderIsOwner: false },
  { senderIsOwner: undefined },
  {},
  { senderIsOwner: "true" },
  { senderIsOwner: 1 },
]) {
  assert.equal(
    isConversationOwner(ctx),
    false,
    `owner signal ${JSON.stringify(ctx)} must not be treated as the owner`,
  );
}

// A non-owner refusal says nothing about whether a binding exists, so asking
// cannot be used to discover what a conversation is working on.
assert.ok(!NOT_OWNER_MESSAGE.includes("bound"));
assert.ok(!NOT_OWNER_MESSAGE.includes("task_"));

// --- every decision is interpretable by the model --------------------------
//
// A rejection the model cannot read is a rejection it will retry blindly, so
// each outcome has to say what to do next rather than only that it failed.

const accepted = describeDecision({ outcome: "accepted", resulting_revision: 5 });
assert.ok(accepted.includes("revision 5"));

const noChange = describeDecision({ outcome: "no_change", reason_codes: ["state_already_matches"] });
assert.ok(noChange.includes("state_already_matches"));

const conflict = describeDecision({ outcome: "conflict", reason_codes: ["stale_base_revision"] });
assert.ok(conflict.includes("task_state"), "a conflict must name the recovery action");
assert.ok(conflict.includes("again"));

const rejected = describeDecision({ outcome: "rejected", reason_codes: ["capability_denied"] });
assert.ok(rejected.includes("capability_denied"));
assert.ok(rejected.includes("Do not retry"), "a rejection must not read as retryable");

const refused = describeDecision({
  reason_code: "host_task_not_bound_to_session",
  message: "This conversation is not bound to that task.",
});
assert.ok(refused.includes("host_task_not_bound_to_session"));

// Every outcome produces a non-empty, distinct sentence.
const rendered = [accepted, noChange, conflict, rejected, refused];
assert.equal(new Set(rendered).size, rendered.length);
for (const text of rendered) assert.ok(text.length > 0);

// --- result envelopes ------------------------------------------------------

const okPayload = JSON.parse(ok({ bound: true, task_id: "migrate" }).content[0].text);
assert.deepEqual(okPayload, { ok: true, bound: true, task_id: "migrate" });

const refusalPayload = JSON.parse(refusal(NO_IDENTITY_MESSAGE).content[0].text);
assert.equal(refusalPayload.ok, false);
assert.ok(refusalPayload.message.includes("session identity"));

// The owner does get their conversation's identity back, inside a ready-to-run
// bind command. That is not a leak: the owner gate already refused everyone
// else, and without it an operator has no way to discover the host-internal
// values `atmem task bind` requires -- which would leave the feature
// unreachable from inside OpenClaw entirely.
const ownerView = JSON.parse(
  ok({ bound: false, reason: "not bound", bind_with: "atmem task bind ..." }).content[0].text,
);
assert.equal(ownerView.ok, true);
assert.ok(ownerView.bind_with.startsWith("atmem task bind"));

// A non-owner still learns nothing, including whether a binding exists.
assert.ok(!NOT_OWNER_MESSAGE.includes("session"));

console.log(
  "task tools: identity completeness, epoch rotation, owner gating, and " +
    "decision legibility verified (bridge logic only; runtime population unproven)",
);
