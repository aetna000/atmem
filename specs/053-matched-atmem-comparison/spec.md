# Spec 053 — Actual AtMem three-arm comparison

The user identified a missing baseline in Spec 052: generic notes were never
original AtMem. Preserve its failed results, but do not use them to compare package
versions or to claim improved AtMem. This correction is a separate experiment.

FR-001: Exactly three conditions: no memory; installed unchanged AtMem 2.3.14;
installed candidate 2.3.15b2 with Spec052's already frozen experimental policy and
derived notes. The third arm deliberately evaluates the rejected candidate; it is
not automatically selected or activated. All memory-enabled conditions exercise
real encrypted episode import, frozen Context Engine V3 and prepare_context_v3.

FR-002: Same model/provider/settings, public task prompt, read-only SQL tools,
15-query ceiling, 8192-byte retrieval budget and independent scalar grader. Both
AtMem arms import identical original training observations (IDs1–10). Only the
pilot adds its frozen derived notes and advisory LOAD instruction. No new proposal,
training inference, outcome leakage, manually invented facts or final memory writes.

FR-003: Python -I subprocesses must attest installed version/module hashes and
source outside the checkout. No-memory must not call a memory worker. Retain actual
retrieval status, canonical generation, selected evidence and exact exposed context;
an empty retrieval is an observed result, never replaced with hand-written notes.

FR-004: Fresh holdout is drift IDs106–120, unused by Spec052. Freeze all identities,
history/policy/context hashes and cases before inference. First three cases (106–108)
are a fixed feasibility stage: if every arm scores zero, stop and report no capable
baseline rather than expanding. Otherwise evaluate all remaining IDs109–120 once.
No policy changes, retries or reselection after any outcome. This is a drift-only,
one-lineage diagnostic, not a general production or native-host benchmark.

FR-005: Durable encrypted reservations before every paid call, no automatic resume
or retry, unknown calls charged conservatively. Maximum400 calls/1M tokens/USD1.5/
45 minutes/24MiB serialized evidence. Log all three-arm paired outcomes, unknowns,
strict and preserved upstream parser results, latency and resources. Preserve the
existing encrypted Spec052 vault; use a new dedicated Home and no private accounts.

SC-001: Real installed-package workers build and retrieve through both versions;
checks reject wrong versions, source contamination, changed canonical generation,
empty/malformed packages, and no-memory worker invocation. Empty authorized context
is allowed and measured explicitly, but never counted as a memory benefit.
SC-002: One preregistered bounded comparison finishes or reports the exact blocker;
all failed/unknown/early-stop outcomes stay visible. Success means measured benefit
only if observed; infrastructure and retrieval success cannot establish learning.

## Protocol v2 correction (before new inference)
The v1 attempt consumed only106–108 and stopped all-zero. Audit found that the
adaptation omitted the upstream public prompt's separate-dataset framing and
reduced its SQL tool timeout from10 to3seconds. Preserve v1 unchanged; it cannot
qualify the task protocol. Restore that public framing (never reveal the hidden
group/category mapping) and the common10-second SQL limit for all three arms.
Use only the still-unattempted IDs109–120. Stage1 is109–111; stop if all nine outcomes
are incorrect, otherwise finish112–120. No memory-policy, grader, model, history or
candidate change. This is one protocol repair, not a score-driven candidate search.
Deduct v1's entire resource use from the original shared ceiling: v2 maximum363calls,
916357tokens/USD1.49368864/2400seconds/23153146serialized reservation bytes.
Do not perform another live protocol/candidate rerun if this fails.
