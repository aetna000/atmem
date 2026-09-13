# Feature Specification: Temporal Memory Consolidation and Health Review

**Feature directory**: `specs/026-temporal-memory-consolidation`
**Created**: 2026-09-12
**Status**: Specified; implementation and verification pending
**Input**: Add an opt-in background memory-health cycle that identifies expired, stale, contradictory, duplicate and time-dependent memories; preserves history; and routes uncertain changes to user review.

## Overview

AtMem evaluates memory as a time-aware, governed record rather than an indefinitely true text fragment. It distinguishes when an assertion was observed from when it was valid, derives changing values only from sufficient stable evidence, and periodically prepares bounded health-review proposals. AtBot may perform semantic analysis through versioned capabilities, but AtMem selects its authorized input, validates every proposal and remains the only canonical mutation authority.

The user receives a Memory Health queue containing understandable findings and proposed effects. Expiry or another deterministic policy boundary may make a record ineligible automatically when explicitly configured. A semantic guess never silently corrects, supersedes, archives, forgets or deletes memory. Superseded and expired records remain inspectable history subject to existing retention and forgetting policy.

This feature extends Spec 006 admission/update semantics, Spec 015 lifecycle authority, Spec 008 ranking-signal registration, Spec 022 workspace presentation and Spec 001 benchmark evidence. It does not create a second memory store, lifecycle authority or independent AtBot agent.

## User scenarios and acceptance

### US1 — Retrieve a time-valid memory (P1)

As a user, I receive the fact that is valid at the question's explicit evaluation time, with derived values and uncertainty explained.

**Independent test**: Capture a dated age assertion and a date of birth in separate fixtures, query both at boundary dates, and reconcile the result with lifecycle inspection without using a model service.

1. Given a record with an explicit validity interval, when recall is evaluated before, inside and at the end boundary, then eligibility uses the supplied trusted time and reports `before_valid_from`, `eligible` or `after_valid_to` consistently.
2. Given an authorized date of birth with sufficient precision, when current age is requested, then a versioned deterministic rule derives the age for the evaluation date and cites the source record without persisting a newly asserted age fact.
3. Given only “I am 45” at a known observation time, when a future age is requested and the birthday is unknown, then AtMem reports the dated snapshot and bounded uncertainty rather than inventing a birthday or exact transition date.
4. Given a historical question, when an inactive but historically valid record is authorized for that purpose, then it may support the historical answer without becoming eligible as current memory.

### US2 — Review memory health without silent rewriting (P1)

As a user, I can inspect possible corrections, contradictions, duplicates and stale memories and decide what happens to uncertain proposals.

**Independent test**: Run one bounded consolidation cycle over synthetic duplicate, non-overlapping historical, overlapping-conflict, expired and uncertain-correction records and inspect the resulting queue before approving one proposal.

1. Given two values for the same fact key with non-overlapping validity intervals, when review runs, then they remain attributable history and are not labelled a current contradiction.
2. Given overlapping incompatible values, when review runs, then AtMem creates a conflict finding and withholds an unsafe current answer until policy or review resolves it.
3. Given a semantic correction proposed by AtBot, when evidence is incomplete or confidence is below policy, then the proposal enters review and canonical state is unchanged.
4. Given a user approves, edits or rejects a current proposal, when the expected generations still match, then AtMem records the actor, reason, evidence, result and immutable lineage; a stale decision fails closed.
5. Given an item is marked expired, stale or superseded, when ordinary current recall runs, then it is excluded or down-ranked according to its explicit state while remaining inspectable unless separately forgotten.

### US3 — Operate an opt-in consolidation cycle safely (P2)

As an operator, I can schedule, preview and monitor memory-health cycles without granting AtBot authority or making the base installation depend on a model.

**Independent test**: Enable preview-only review for one memory space, run it with deterministic fallback, AtBot success, malformed AtBot output and process restart, and verify identical authority boundaries.

1. Given background review is disabled, when maintenance runs, then no consolidation analysis or mutation occurs.
2. Given preview-only mode, when a cycle completes, then it may create findings and proposals but cannot change canonical eligibility.
3. Given AtBot is unavailable, remote egress is denied or output is malformed, when a cycle runs, then deterministic expiry and exact duplicate checks still work and semantic review reports unavailable coverage without widening access.
4. Given an AtBot capability is enabled, when AtMem sends a review package, then it contains only authorized lifecycle-eligible or explicitly authorized historical records, bounded evidence, opaque scope identities and a declared capability/version.
5. Given concurrent memory changes or membership removal, when proposals are committed or dispatched, then generation and authorization are revalidated and stale work cannot affect memory.

### US4 — Understand memory health in the shared workspace (P2)

As a user, I see what requires attention, why, when it was checked and which action I am permitted to take.

**Independent test**: Complete the Memory Health journey in the dashboard and equivalent API/CLI projection for private and shared spaces using keyboard and narrow/wide viewport fixtures.

1. Given authorized findings, when Context → Memory Health opens, then it groups possible corrections, stale records, conflicts, duplicates and derivations with readable reasons, absolute timestamps, evidence age and permitted next action.
2. Given inaccessible records contributed to a scoped aggregate, when another user views health, then counts, names, evidence and exports do not reveal their existence.
3. Given a display refresh, when no new cycle ran, then the original evaluation and verification times remain unchanged.
4. Given a review action is unavailable, when the item is displayed, then the UI explains the permission, stale-generation or evidence limitation without representing color as the decision.

## Edge cases

- Leap-day birthdays, daylight-saving transitions, timezone changes, partial dates and ambiguous phrases such as “next summer” retain explicit precision and do not acquire an invented instant.
- Observation time, source event time, validity time, AtMem receive time and review evaluation time remain distinct.
- A correction received late may alter current eligibility without rewriting when AtMem originally learned either assertion.
- A record can be old but still valid, recent but already invalid, or historically valid and currently superseded; recency alone is not truth.
- A semantic duplicate across private and shared spaces does not merge ownership, permissions or provenance.
- Scheduled work is idempotent, resumable and bounded; cancellation or crash cannot leave partially committed canonical transitions.
- Consolidation never interprets prompt-shaped content as authority and cannot use unauthorized records as hidden evidence.
- Forgetting follows existing verified deletion behavior; health review does not retain forgotten content in prompts, proposals, logs or derived indexes.

## Functional requirements

- **FR-001**: Define a versioned temporal assertion contract that distinguishes observation/receive time, world-validity interval, temporal kind, precision, timezone basis, confidence and derivation lineage while preserving legacy records with honest unknown fields.
- **FR-002**: Support at least `atemporal`, `event`, `bounded_state`, `snapshot`, `recurring` and `derived` temporal kinds; extraction may propose these values but AtMem validates their schema, scope, evidence and allowed transitions.
- **FR-003**: Evaluate current and historical eligibility at an explicit trusted time using half-open validity intervals and stable boundary reason codes; missing time is unknown rather than current time.
- **FR-004**: Provide a versioned deterministic derivation registry. Initial acceptance covers date-of-birth to age, including birthday boundaries, leap-day policy, timezone and insufficient-precision withholding. Derived values cite inputs and are not silently persisted as user assertions.
- **FR-005**: Detect exact duplicates and deterministic expiry locally without AtBot. Semantic staleness, contradiction, correction, refinement and merge analysis may be proposed by a configured AtBot capability but never directly committed by it.
- **FR-006**: Define a typed health finding/proposal with scope, category, candidate effect, affected record IDs, evidence references, confidence, reason codes, proposer/capability version, evaluation time, expected generations and review requirement.
- **FR-007**: Require explicit policy for scheduling, record classes, historical access, egress, auto-acceptance and review thresholds. The default is disabled; initial enablement is preview-only; semantic corrections, merges, supersession and destructive actions require authorized review.
- **FR-008**: Permit automatic canonical eligibility changes only for deterministic, explicitly configured lifecycle boundaries whose effect was previewed. Automatic expiry marks or transitions state and invalidates derivatives; it does not delete content.
- **FR-009**: AtMem MUST authorize and minimize every AtBot review package before egress, bind it to a scope/policy/generation/capability, reject unknown or unauthorized returned IDs and revalidate before any commit.
- **FR-010**: Approve, edit-and-approve, reject and defer operations MUST be authenticated, authorized, generation-checked, idempotent and auditable. Accepted corrections preserve immutable predecessor/successor lineage.
- **FR-011**: Current retrieval MUST exclude invalid, expired, rejected, excluded, forgotten and superseded assertions and MUST withhold unresolved overlapping conflicts according to policy. Historical retrieval requires an explicit purpose and remains scope-authorized.
- **FR-012**: Ranking MAY use bounded freshness and temporal-match signals only after canonical authorization. Age alone cannot establish invalidity, and an ineligible record cannot influence another record's rank.
- **FR-013**: Provide one Memory Health projection through shared service contracts for API, CLI, MCP and dashboard use, with accessible scoped counts, filters, evidence, proposed effect, review actions and distinct evaluation/check/display times.
- **FR-014**: Scheduled consolidation MUST be bounded, resumable, idempotent and observable. Record cycle scope, policy/capability versions, counts, latency, unavailable coverage and outcomes without persisting unnecessary raw content.
- **FR-015**: Invalidate vector, graph, cache, prepared-context and registered provider derivatives after accepted lifecycle changes, and distinguish local completion from external acknowledgment or unknown propagation.
- **FR-016**: Preserve host-neutral operation, private/shared-space ownership, contributor lineage, explicit egress, local deterministic fallback and existing signed delegated bytes. OpenClaw cannot be required for core behavior.
- **FR-017**: Add deterministic, hosted-optional and installed-host benchmark profiles covering temporal boundaries, conflicts, review safety, poisoning, cross-scope isolation, AtBot failure and consolidation restart.
- **FR-018**: Any schema or contract change MUST use negotiated versions, allocated migrations, persisted upgrade fixtures from supported release floors and documented rollback/forward recovery. Merely upgrading MUST NOT enable background review or reinterpret legacy content.

## Key entities

- **TemporalAssertion**: Canonical temporal meaning associated with a memory record, including distinct observation and validity times, kind, precision, confidence and derivation lineage.
- **DerivationRule**: Versioned deterministic computation with declared input fact keys, precision requirements and boundary behavior.
- **MemoryHealthPolicy**: Scope-bound schedule, mode, record classes, egress choice, thresholds and permitted automatic deterministic effects.
- **ConsolidationCycle**: Idempotent bounded evaluation of one authorized scope at a specific time and policy/capability generation.
- **HealthFinding**: Evidence-linked diagnosis such as expired, possibly stale, duplicate, conflict, correction candidate or derivable value.
- **HealthProposal**: Generation-bound requested lifecycle or canonical change requiring policy validation and, where applicable, human review.

## Success criteria

- **SC-001**: Boundary fixtures produce the same eligibility and date-of-birth-derived age across service, CLI, MCP and dashboard projections, with zero invented exact dates or current values.
- **SC-002**: All semantic correction, merge and supersession fixtures cause zero canonical changes before authorized review; stale-generation and cross-scope commits are rejected in every supported interface.
- **SC-003**: Ordinary current context contains zero expired, invalid, forgotten, superseded or unresolved-conflict records across native and declared provider/host profiles.
- **SC-004**: AtBot unavailable, malformed-output and denied-egress fixtures retain deterministic expiry/duplicate behavior, report semantic coverage unavailable and produce zero widened access or implicit model dependency.
- **SC-005**: Crash/restart and duplicate-schedule fixtures produce one reconciled cycle and at most one transition/proposal per idempotency identity, with no partially invalidated canonical state.
- **SC-006**: Private/shared and concurrent membership fixtures reveal zero inaccessible content, identifiers, counts or semantic influence to AtBot, another user or an unauthorized agent.
- **SC-007**: At least 9 of 10 intended users in each of two independent cohorts can identify why a memory was flagged and complete an allowed review action within two minutes; synthetic walkthroughs remain separate evidence.
- **SC-008**: Published performance reports measure scan throughput and retrieval overhead on declared hardware and corpus sizes; an initial target is at least 10,000 records per preview cycle and no more than 10 ms p95 added deterministic temporal filtering cost. With Spec 019 policy enforcement and Spec 026 temporal filtering enabled together, directly measured added pre-model control overhead is no more than 35 ms p95 on the declared profile. Provider, network, retrieval-model and AtBot latency are measured separately.

## Dependencies and ownership

Spec 006 owns admission and correction proposals; Spec 015 owns canonical lifecycle and invalidation; Spec 008 owns post-authorization ranking signals and their extension registry; Spec 012 owns shared service/feedback shapes; Spec 019 owns provider packaging/delivery policy; Spec 022 owns workspace navigation; Spec 001 owns benchmark reporting. This feature owns temporal assertion/derivation contracts, consolidation-cycle orchestration and memory-health findings. AtBot owns replaceable semantic proposal implementations only.

Deliver contract foundations with the 2.4 memory/access work, the Memory Health projection with the 2.5 workspace, investigation consumption with 2.6, and the complete opt-in background cycle in a proposed 2.8.0 release after 2.7 revocation propagation. These are staged dependencies, not a claim that any release exists.

## Compatibility, privacy and rollout

Legacy records receive unknown temporal semantics and remain governed by their existing lifecycle; no dates are inferred during migration. Roll out read-only inspection, then preview-only cycles, then separately activate supported deterministic automation. Remote AtBot review requires explicit model/egress configuration. Content-bearing review artifacts follow memory access and retention policy, and forgotten content must be purged from registered derivatives.

## Out of scope

- Autonomous semantic deletion, silent correction or rewriting immutable evidence.
- Treating recency, model confidence or vector similarity as truth.
- General calendar/world-event prediction or unconstrained temporal reasoning.
- Training or modifying model weights.
- Claiming that external cleanup retracts prior model exposure or unmanaged copies.

## Constitution check

I: AtMem remains authority and AtBot proposal-only. II: every temporal/health result retains exact evidence and distinct times. III: disabled and preview-only defaults preserve reversibility. IV: scope precedes analysis and forgetting covers derivatives. V: contracts are host-neutral and versioned. VI: boundary and installed-profile evidence gate claims. VII: deterministic local operation remains useful without AtBot or network egress.

## Invariant attestation

Touches INV-001, INV-002, INV-003, INV-004, INV-006, INV-007, INV-008, INV-010 and INV-011 through planned assertions `spec026.temporal_authority`, `spec026.review_authorization`, `spec026.temporal_revalidation`, `spec026.preview_activation`, `spec026.health_history`, `spec026.derived_deletion`, `spec026.proof_boundaries`, `spec026.local_fallback` and `spec026.upgrade_compatibility`. These assertions become proven only after the named boundary and installed-profile evidence executes; this specification creates no new invariant or current proof.
