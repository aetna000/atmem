#!/usr/bin/env node
/**
 * Spec 007 Amendment A, T058 — the premise gate.
 *
 * Amendment A exists because no OpenClaw hook supplies a governed task
 * identity. Its design then depends on two host-supplied values: `sessionId`,
 * bound as FR-052 `session_epoch`, and `sessionKey`, the FR-042 conversation
 * address; plus `senderIsOwner` to gate FR-050's in-host binding surface.
 *
 * What a declaration can and cannot prove
 * ---------------------------------------
 * These fields are declared **optional** on the contexts that carry them. A
 * `sessionId?: string` says the host *may* supply it, never that it does. So
 * this file does not assert that identity is present at runtime -- it cannot,
 * and an earlier version of it claimed exactly that and was wrong. It asserts
 * the weaker, true premise: the capability is declared, so binding is possible
 * for this host. Because every such field is optional, the adapter MUST fail
 * closed on absence (FR-050, FR-052), and the optional set is printed so that
 * obligation stays visible rather than being quietly assumed away.
 *
 * Runtime population is not proven anywhere, and no test here should claim it.
 * The npm harness drives handlers through a fabricated `fakeApi` context, so
 * T078 proves the bridge's own rotation and fail-closed logic, not what a real
 * OpenClaw passes. That gap is the reason absence must fail closed.
 *
 * Each premise is compared with a recorded fixture, so an upstream change
 * produces a reviewable diff rather than a silent wrong answer:
 *
 *   - Task identity appears  -> re-scope the amendment. FR-043's first
 *     resolution step already consumes native identity; binding stops being
 *     load-bearing. This is not a failure to work around.
 *   - `sessionId` undeclared -> the epoch design is impossible at that hook and
 *     session binding must report unavailable for this host (FR-052).
 *   - Owner signal undeclared -> FR-050's in-host surface has no gate.
 *   - A field becomes required -> good news, and still a reviewable diff.
 *
 * Runs against the resolved dependency only, never a global install.
 */

import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

import {
  AMENDMENT_HOOKS,
  hooksMissingField,
  hooksWithOptionalField,
  ownerContextsMissingSignal,
  ownerContextsWithOptionalSignal,
  readHookContextShape,
  taskIdentityFieldsIn,
} from "./lib/hook-context-shape.mjs";

const shape = readHookContextShape();
const fixtureDir = path.join(import.meta.dirname, "fixtures", "hook-context");
const fixturePath = path.join(fixtureDir, `${shape.version}.json`);

console.log(`[hook-context] resolved openclaw ${shape.version}`);

// The compatibility matrix is finite and every entry is executed. An
// unrecorded resolved version means CI resolved something outside the tested
// set -- record it deliberately rather than letting the range drift untested.
assert.ok(
  existsSync(fixturePath),
  `openclaw ${shape.version} has no recorded hook-context fixture.\n` +
    `The tested matrix is finite: minimum, lockfile, and latest-compatible.\n` +
    `If this version belongs in it, record and review:\n` +
    `  node test/lib/record-hook-context.mjs --label <min|lockfile|latest>`,
);

// Premise 1 -- no host-supplied governed task identity, optional or otherwise.
// Unlike the identity fields below, presence here is disqualifying rather than
// enabling, so an optional declaration counts: a host that may pass a task id
// is a host whose task id must be honoured (FR-043 step one).
const taskIdentity = taskIdentityFieldsIn(shape);
assert.deepEqual(
  taskIdentity,
  [],
  `openclaw ${shape.version} declares task identity ${JSON.stringify(taskIdentity)} on a ` +
    `hook context. Amendment A assumed none existed. Re-scope it toward FR-043's ` +
    `explicit-identity step rather than treating this as a regression.`,
);

// Premise 2 -- the epoch and address are declared, so binding is possible.
// Optional is acceptable and expected; undeclared is not.
for (const field of ["sessionId", "sessionKey"]) {
  const missing = hooksMissingField(shape, field);
  assert.deepEqual(
    missing,
    [],
    `openclaw ${shape.version} does not declare ${field} on ${JSON.stringify(missing)}. ` +
      `FR-052 binds sessionId as session_epoch and FR-042 uses sessionKey as the ` +
      `conversation address; without either, session binding must report ` +
      `unavailable for this host rather than resolving unsafely.`,
  );
}

// Premise 3 -- the in-host binding surface has an owner gate to read.
const missingOwner = ownerContextsMissingSignal(shape);
assert.deepEqual(
  missingOwner,
  [],
  `openclaw ${shape.version} does not declare senderIsOwner on ${JSON.stringify(missingOwner)}. ` +
    `FR-050's in-host bind/unbind/status has no gate without it.`,
);

// Fixture equality -- any other drift, including a change in optionality, is
// surfaced for review rather than absorbed.
const recorded = JSON.parse(readFileSync(fixturePath, "utf8"));
const { label, ...recordedShape } = recorded;
assert.deepEqual(
  recordedShape,
  shape,
  `openclaw ${shape.version} hook-context shape differs from its recorded fixture ` +
    `(${label ?? "unlabelled"}). Review the change, then re-record:\n` +
    `  node test/lib/record-hook-context.mjs --label ${label ?? "<label>"}`,
);

for (const hook of AMENDMENT_HOOKS) {
  console.log(`[hook-context]   ${hook} -> ${shape.hookContexts[hook]}`);
}

// The fail-closed obligation, stated every run so it cannot be forgotten.
const optionalEpoch = hooksWithOptionalField(shape, "sessionId");
const optionalKey = hooksWithOptionalField(shape, "sessionKey");
const optionalOwner = ownerContextsWithOptionalSignal(shape);
console.log(
  `[hook-context] openclaw ${shape.version} (${label ?? "unlabelled"}): ` +
    `no task identity; sessionId and sessionKey declared on every amendment hook`,
);
if (optionalEpoch.length || optionalKey.length || optionalOwner.length) {
  console.log(
    `[hook-context] OPTIONAL, so the adapter must fail closed on absence:\n` +
      `[hook-context]   sessionId optional on:     ${JSON.stringify(optionalEpoch)}\n` +
      `[hook-context]   sessionKey optional on:    ${JSON.stringify(optionalKey)}\n` +
      `[hook-context]   senderIsOwner optional on: ${JSON.stringify(optionalOwner)}\n` +
      `[hook-context]   Absent identity withholds (FR-052); absent owner signal is ` +
      `not the owner (FR-050). Whether a host populates these at runtime is ` +
      `unproven by any test; that is why absence must fail closed.`,
  );
}
