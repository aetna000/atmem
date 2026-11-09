# Spec 050: Verified memory feedback and governed rule promotion

Status: approved for implementation on 2026-11-09; foundation implemented,
host-boundary prerequisite blocked. See `implementation-evidence.md`.
Owner confirmed feature directory in conversation on 2026-11-09.
Baseline: AtMem 2.3.14, upstream commit 1f5c72e.
Inputs: `research.md`, repository constitution 2.2.0, existing Specs 007, 018,
019, 028, 038, 040, 046. No amendment to the constitution is proposed.

## Outcome

A user can see whether an agent actually used an applicable memory correctly,
correct the failure with evidence, compare a proposed change against unchanged
behavior, and activate or revoke a narrowly scoped deterministic rule only at a
host that demonstrably enforces it. The system improves verified task outcomes,
not just retrieval scores or exposure counts.

Example: a project requires an approval receipt before a production deployment.
An agent retrieved the requirement but tried to deploy without the receipt.
AtMem records that distinction, the owner reviews a typed guard proposal, shadow
comparison tests both valid and invalid deployments, and the owner activates it
for a named adapter. That adapter refuses the actual tool invocation without a
valid receipt. A fresh session obeys the same rule. AtMem does not claim to
prevent deployment through unrelated tools or an unintegrated host.

## Scope and defaults

V1 includes outcome evidence, per-agent quality reporting, bounded retrieval-profile
qualification, typed rule promotion, one real enforcement adapter (Hermes), and
explicit verified-example export. Models may propose; AtMem authorizes.
All new behavior starts disabled, then shadow, then explicitly active by scope.
No automatic promotion from frequency, praise, confidence or repeated retrieval.
Existing stores, ordinary memory admission and local offline recall remain usable.

No model training or hosted inference provisioning, arbitrary executable policy,
new permission system, phone channel, legal corpus, universal agent interception,
benchmark launch, release or public superiority claim is part of this scope.
The model-training roadmap is an independently approved feature after outcome
benefit is demonstrated; v1 prepares only consented evidence exports.

## Users and acceptance scenarios

- **US1 — Investigate a mistake.** An authorized owner opens one run and sees
  required evidence, delivery receipt, exact action arguments and verified effect.
  A retrieved approval requirement omitted from the call is classified differently
  from evidence that was not delivered. Missing capture remains unknown.
- **US2 — Review a correction.** A reviewer approves a version-bound candidate;
  concurrent edits or revoked source access invalidate that decision. Injection
  text in a retrieved document cannot authorize a change.
- **US3 — Measure a change.** An owner compares unchanged/native and AtMem baseline
  with one candidate under a frozen evaluation manifest. A better score on development
  alone cannot activate it; failures and cost remain visible.
- **US4 — Promote a rule.** An authorized owner approves a typed receipt requirement,
  observes shadow results, and activates the qualified revision on Hermes. Missing,
  expired, replayed or wrong-scope approvals prevent execution in the instrumented
  tool path. A valid approval allows exactly the bound call. Revocation stops new calls.
- **US5 — Inspect quality.** Per-agent dashboard separates wrong-answer rate, coverage,
  action success, memory support and abstention with denominators. An apparent gain
  achieved by refusing all tasks fails the coverage gate.
- **US6 — Export verified examples.** Only explicitly consented and independently
  verified examples enter a previewed export. Another tenant, revoked consent, a
  deleted source or unknown result excludes the example and gives a reason code.

## Functional requirements

- **FR-001 — Scope and identity.** Derive caller identity from authenticated boundaries;
  bind every operation to tenant/subject, agent, workspace, run/turn and source revision
  as applicable. Access is the intersection of authenticated user authority and
  registered agent capability. Unknown scope or missing capability denies without
  leaking existence. The client cannot supply its own trusted role or verification tier.
- **FR-002 — Outcome chain.** Store immutable, versioned evidence linking candidate
  retrieval, authorized context, delivered bytes, model/tool output, action and observed
  effect. Preserve original captured content through existing encrypted evidence storage.
  Explicitly distinguish not captured, not delivered, delivered, reported success and
  independently verified success. Delivery does not prove model use or action correctness.
- **FR-003 — Verification and disputes.** Accept independent verification only from
  registered, scoped verifier identities with a versioned check and evidence reference
  (e.g. authorized destination readback). Human attestation is a separate tier, as are
  host reports and model judgements. Conflicting verifications are disputed, cannot
  qualify changes, and are resolved by a new attributable revision, never overwritten.
- **FR-004 — Failure attribution.** Support evidence-backed labels: source fact absent,
  retrieval miss, authority withheld, stale/conflicting state, delivered-but-not-applied,
  wrong argument/value, wording/precision, no call, execution failure and unknown.
  A trace or an LLM label alone cannot establish causality or source absence. Preserve
  proposed versus verified classification and the checks supporting it.
- **FR-005 — One action, all checks.** Report each required action with tool/schema
  identity, read/write kind, one matching invocation, required mechanical and judged
  checks, failed checks/reasons and verifier tier. Several partial calls cannot be
  combined into an invented successful call. Read success cannot mask write failure.
- **FR-006 — Idempotency and ordering.** Scope idempotency keys, bind payload digests,
  reject conflicting reuse, preserve late observations as revisions, and tolerate
  retry/restart without duplicate outcomes, approvals or activation. Outcomes bind exact
  action and source revisions rather than silently attaching to the latest revision.
- **FR-007 — Review authority.** Reuse the authenticated review service for proposed
  corrections, profile changes and rules. Require exact digest/revision, actor, scope,
  reason and explicit decision. AtBot/LLM confidence and stored instructions cannot
  approve. Ordinary fact admission keeps its existing policy rather than becoming
  universally manual. Review is distinct from activation and from approving a tool call.
- **FR-008 — Per-agent measures.** Report metrics defined below by agent/workspace,
  version and task class, including sample size, unverified/disputed totals, abstention,
  confidence intervals and cost. Deny cross-user totals that would reveal other users.
- **FR-009 — Frozen evaluation.** Before qualifying a candidate, freeze baseline and
  candidate IDs, task/action requirements, source/episode-based development/validation/
  held-out partitions, chronology, reader/verifier versions, budgets and thresholds.
  Prevent shared episodes/paraphrases crossing partitions and future-state leakage.
  Already inspected benchmark items are labelled diagnostics, not untouched evaluation.
- **FR-010 — Bounded profile qualification.** Candidate retrieval profiles may adjust
  authorized ranking, thresholds and packing within existing supported parameters;
  never scope, permissions or canonical truth. Evaluate baseline and candidate on the
  same frozen items, retain every attempt and regression, and issue accept/reject/
  inconclusive receipts bound to exact versions. No unchecked profile becomes active.
- **FR-011 — Typed rule proposal.** A candidate rule cites eligible memory revisions,
  verification and intended tool/schema scope. Initial vocabulary is only required
  argument presence, exact typed argument equality, and valid approval-receipt required.
  No generated Python/shell/SQL, arbitrary regex, inferred business thresholds or
  free-text executable instructions. Unexpressible rules remain advisory/review-only.
- **FR-012 — Rule lifecycle.** Track proposed, reviewed, shadow, qualified, active,
  suspended, revoked, expired and rejected states. Activation requires authenticated
  owner authority, valid qualification, current sources and matching adapter capability.
  No automatic generalization between subjects, projects, agents or tool schemas.
- **FR-013 — Shadow and qualification.** Shadow records would-allow/would-deny and
  disagreements without causing, replaying or blocking real side effects. Promotion
  requires immutable replay fixtures, safe control cases, held-out evaluation, false-
  denial measurement and independent adapter conformance; zero failures alone on a tiny
  sample is not production evidence. Qualification expires after 7 days by default and
  immediately on source, policy, verifier, compiler or adapter-version changes.
- **FR-014 — Real boundary enforcement.** Initially integrate the Hermes before-tool
  boundary with a shared host-neutral evaluator, composing with existing guards by
  deny-wins. Re-evaluate immediately before the actual call, binding normalized arguments,
  tool/schema, target, policy/source revision and single-use approval where required.
  Block bypass through registered wrappers/batches, mutated arguments, stale approvals
  and TOCTOU changes; refuse unsupported covered paths. All other hosts say advisory or
  unsupported until their own boundary conformance passes. Never claim system-wide
  prevention through paths the adapter does not own.
- **FR-015 — Failure and revocation.** For an active enforceable rule covering a write,
  unavailable policy/source/auth services, unverifiable revisions or unsupported schema
  block the covered call with a typed reason. Unrelated calls follow existing behavior.
  Revocation and expiry are checked on each dispatch; caches cannot preserve authorization.
  No rollback can bypass higher-priority authorization or revive deleted evidence.
- **FR-016 — Conflicts and priorities.** Exact alias ambiguity and contradictory or stale
  source rules prevent promotion. Deny overrides allow, and generated rules cannot weaken
  existing policy. Opposing argument-equality requirements are an explicit conflict and
  block covered operations pending resolution; they are never silently merged.
- **FR-017 — Reversible activation.** Store versioned activation receipts; support scoped
  suspension and rollback to a still-valid previously approved generation, with a fresh
  dispatch check. In-flight calls already dispatched are recorded and cannot be undone
  by revocation. Interrupted activation is atomic/recoverable; unknown state denies.
- **FR-018 — Privacy, retention and deletion.** Reuse encrypted authoritative storage,
  audit and scoped key release for outcomes, rules, manifests and exports. Authorize
  before reading/decrypting or sending content to proposers/verifiers. Delete/expire
  sources invalidates dependent candidates, active rules, derived profiles and export
  eligibility; verify registered copies and retain only allowed content-free tombstones.
  Backup/external-export limits must be stated, not called universal erasure.
- **FR-019 — Verified-example export.** Default off; preview exact eligible records,
  destination and digest; require authenticated explicit consent for that export purpose
  and scope. Include lineage, verification tier, consent version, exclusions and redaction
  receipts; exclude credentials, unverified/disputed cases, test partitions and other
  tenants. Export is a training candidate dataset, not evidence of learning, training,
  legal clearance, anonymization or successful deletion from trained weights.
- **FR-020 — Shared product surfaces.** CLI/API/MCP read/report/propose operations and a
  dashboard Feedback view use one service. Reviewer UI shows evidence, action failures,
  metrics, shadow differences, current scope, expiry, capabilities, activation and rollback.
  Privileged review/activation/export require authenticated permissions and existing
  platform approvals; model-facing proposal tools cannot invoke owner capabilities.
- **FR-021 — Compatibility and offline path.** Preserve Python 3.10–3.13, Linux/macOS/
  Windows, existing stores, local-first recall and adapters. Add versioned contracts and
  upgrade-tested migrations. Legacy outcomes are unknown, not backfilled as verified.
  Optional model loss does not disable ordinary deterministic memory retrieval.
- **FR-022 — Cost and stopping.** No paid calls or training by default. An explicitly
  approved evaluation manifest must set monetary, token, task, time and disk limits
  before model calls; otherwise only offline contract fixtures run. At most 3 candidate
  evaluations per failure hypothesis, then reassess. Preserve results and costs on
  failure; no automatic full benchmark, new corpus collection or repeated model training.
- **FR-023 — Observability.** Emit content-free operational counters/reason codes and
  separate authorized detailed evidence. Measure p50/p95, resource use, verifier errors,
  unknown outcomes, false blocks, regressions, receipt expiry and rollback. No memory
  content, secrets or cross-tenant labels in logs or metric dimensions.
- **FR-024 — Claims.** Report observed adaptation as retrieval calibration or policy
  enforcement. Do not claim trained learning, causal memory benefit, universal safety,
  universal host support or competitor superiority from synthetic tests, a chart,
  exposure counts, self-grading or unmatched historical scores.

## Metric definitions

- Verified full-task success = independently verified tasks satisfying every required
  action / all scheduled eligible tasks. Aborts, unknown and missing actions are not
  successes; reasons remain separately visible.
- Wrong-answer rate = independently assessed incorrect answers / independently assessed
  answers. Report unassessed outputs separately; never treat them as correct.
- Coverage = eligible answerable tasks receiving a verified complete answer/action /
  all eligible answerable tasks. Abstention lowers coverage; correct refusal on genuinely
  unanswerable/disallowed tasks is reported separately.
- Evidence precision = independently assessed relevant delivered evidence units /
  assessed delivered units, alongside assessment coverage. This is not answer accuracy.
- False denial = legitimate covered invocations blocked / legitimate covered invocations.
- Required-fact-in-action failure = verified writes missing an applicable required fact /
  assessed writes requiring that fact, separated by evidence delivery status.

Zero denominators produce undefined/insufficient evidence, never 0% error or 100%
precision. Every rate includes numerator/denominator and scope/version; uncertainty
clusters by source episode when observations are dependent.

## Success criteria and release gates

- **SC-001:** All scoped authorization, tamper, stale-source, duplicate/retry and injection
  acceptance cases pass with zero unauthorized admissions, disclosures or promotions.
- **SC-002:** Reconstruct at least one complete read/write/correction/activation/revocation
  journey using only a restored encrypted AtMem store after destroying fixture host logs
  and workspace. Unknown capture stays visibly unknown.
- **SC-003:** On the frozen paired evaluation, the 95% episode-clustered interval for
  verified full-task-success improvement has lower bound above zero; coverage loss is
  at most 2 percentage points and there is no new scope/authorization violation.
  If the manifest lacks adequate power/sample size, report inconclusive and do not
  activate on an efficacy claim. This gate applies to profiles and rule candidates.
- **SC-004:** Hermes conformance proves zero escaped forbidden calls in the specified
  hostile matrix, exact approval binding, successful legitimate calls, and no real
  side effects in shadow. Held-out false-denial rate must not exceed 1%, with counts
  and uncertainty reported; benchmark evidence does not become a universal guarantee.
- **SC-005:** Disabled mode has identical existing regression outcomes. On the same
  pinned environment/corpus, active retrieval p95 overhead is at most 20%; deterministic
  rule evaluation p95 is at most 10 ms with 1,000 applicable rules, excluding explicitly
  reported remote verification time. Failure meets FR-015, not a silent fallback allow.
- **SC-006:** An encrypted real-store journey passes on supported Python and Linux,
  Windows and macOS CI; upgrade, crash/retry, scoped rollback and dependent deletion pass.
- **SC-007:** Dashboard displays the same counts, rule states and denial reasons as CLI/
  API, passes keyboard navigation and browser acceptance tests, and cannot reveal another
  scope via rows, counts or errors. Export can be independently verified against source
  and consent revisions; excluded cases stay out.

## Edge cases

Multiple contradictory reviewers; incomplete capture; delayed tool callbacks; external
readback outage; stale or replayed approval; tool schema drift; ambiguous identity;
source deletion during dispatch; offline clients; duplicate activation; backup restore
of revoked rules; native/custom wrappers bypassing hooks; poisoned feedback; dataset
consent withdrawn after export; benchmark contamination; small/empty denominators.

## Delivery boundary

The owner authorized implementation on 2026-11-09. Tasks are checked only on
completion with evidence. Separate release qualification and approval precede publication. The owner
receives a native/current-baseline comparison before any costly evaluation expansion.
