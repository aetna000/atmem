# Feature Specification: Memory Extraction and Updating

**Feature directory**: `specs/006-memory-extraction-and-updating`
**Created**: 2026-09-05
**Status**: Draft
**Unified product amendment status**: Specified; implementation and verification pending. The status above describes the historical baseline only.
**Input**: `todo.md` P0.3

## Overview

Turn observations into typed, evidence-linked proposals that distinguish useful durable memory from temporary state, episodes, procedures, and content that must not be remembered. Intelligence may propose; AtMem validates and commits.

## User Scenarios & Testing

### User Story 1 - Produce a governed proposal (Priority: P1)

For each eligible observation, extraction returns `ADD`, `UPDATE`, `SUPERSEDE`, `REJECT`, or `NOOP`, a memory class, confidence, bounded reason, exact source evidence, and affected canonical IDs where applicable.

**Why this priority**: No memory mutation is safe unless its proposed effect and evidence are explicit.

**Independent Test**: Submit one deterministic fixture for every action and class and validate the typed proposal without committing it.

**Acceptance Scenario**: **Given** an eligible observation, **when** extraction runs, **then** exactly one schema-valid evidence-linked proposal outcome is returned.

### User Story 2 - Correct without duplicate pollution (Priority: P2)

A correction or refinement resolves entities using only bounded recent context and authorized eligible memory, preserves prior history, and results in one unambiguous current value. Uncertain, sensitive, ambiguous, or policy-relevant proposals wait for review.

**Why this priority**: Corrections must improve memory rather than create contradictory duplicates.

**Independent Test**: Apply a correction fixture and verify one current record, preserved lineage, and review routing for ambiguity.

**Acceptance Scenario**: **Given** a correction with eligible evidence, **when** it is accepted, **then** one current fact remains and the replaced fact stays in history.

### User Story 3 - Resist instruction-shaped memory (Priority: P3)

Instructions, prompt injection, secrets, and content marked “do not remember” cannot bypass policy through extraction or entity resolution.

**Why this priority**: Hostile content is a safety boundary even when memory quality is otherwise correct.

**Independent Test**: Run poisoning, secret, exclusion, and cross-scope fixtures with AtBot available and unavailable.

**Acceptance Scenario**: **Given** instruction-shaped or excluded source content, **when** extraction runs, **then** it is rejected/quarantined as data and never changes authority.

### Edge Cases

- Empty or evidence-free output becomes `REJECT`, not an implicit add.
- Ambiguous pronouns, conflicting current facts, stale proposal generations, and concurrent review decisions fail closed with stable reasons.
- AtBot timeout, malformed output, or provider unavailability selects deterministic fallback without broadening candidate access.

## Requirements

### Functional Requirements

- **FR-001**: Extraction MUST classify candidates as durable fact, temporary state, episode, procedure, or non-memory.
- **FR-002**: Every outcome MUST be one typed proposal with reason, confidence, source spans/digests, and affected records; absence of change MUST be explicit `NOOP` or `REJECT`.
- **FR-003**: Pronoun/entity resolution MUST use a configured bounded recent window plus authorized, lifecycle-eligible memory only and MUST record which evidence influenced resolution.
- **FR-004**: The proposer MUST detect duplicates, refinements, contradictions, corrections, and supersession against normalized fact keys and current eligible values.
- **FR-005**: AtMem MUST validate schema, scope, evidence, policy, lifecycle preconditions, and optimistic generation before atomic commit.
- **FR-006**: Sensitive, low-confidence, ambiguous, or destructive proposals MUST be quarantined for review by configurable policy.
- **FR-007**: Instruction-as-memory, poisoned evidence, and explicit exclusion signals MUST be detected before admission; untrusted content remains data.
- **FR-008**: Review MUST support approve, edit-and-approve, reject, and inspect evidence with auditable actor/time/reason.
- **FR-009**: Deterministic fallback MUST emit safe typed outcomes when AtBot is absent or fails.
- **FR-010**: No proposer may see unauthorized candidates or directly mutate canonical storage.
- **FR-011**: Any SQLite schema change MUST pass upgrade tests using real persisted state from every supported published AtMem upgrade floor and MUST include forward-recovery and rollback evidence.

### Key Entities

- **Memory Proposal**: Typed requested action, class, confidence, reason, evidence, and preconditions.
- **Resolution Context**: Bounded authorized evidence used for entity/pronoun interpretation.
- **Review Decision**: Auditable approval, edited approval, rejection, or unresolved state.
- **Memory Lineage**: Immutable relationship among original, corrected, and superseding records.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A versioned suite covers every class and action plus duplicate, correction, ambiguity, sensitivity, poisoning, and cross-scope cases.
- **SC-002**: Correction fixtures yield one current fact and a complete evidence-linked history in 100% of deterministic safety cases.
- **SC-003**: Poisoning and unauthorized-candidate exposure are zero-tolerance release gates.
- **SC-004**: CLI/dashboard review show identical proposal state and allowed actions.

## Out of Scope

Autonomous policy changes, unbounded conversation replay, or deleting historical provenance when a fact is superseded.

## Assumptions

- Existing fact-key and canonical admission primitives remain available.
- Policy determines sensitive/uncertain thresholds and authorized reviewers.
- Spec 015 owns general retention and expiry; this feature owns admission/update proposal semantics.
## Invariant Attestation

Touches INV-001, INV-002, INV-006, and INV-011 through `spec006.canonical-write`, `spec006.pre-extraction-auth`, `spec006.history`, and `spec006.upgrade`.


## Unified product amendment — 2026-09-09

**Roadmap status**: Baseline status above is historical; this amendment is specified and not implemented. Existing unchecked tasks remain prerequisites where referenced.

**Product role**: memory admission. See [product roadmap](../product-roadmap.md) and [implementation review](../implementation-review-2026-09-09.md).

**Observed foundation**: Typed admission, review and immutable correction lineage exist.

### Additional functional requirements

- **FR-012**: Native memory writes MUST continue through existing admission and review when native memory uses the shared provider interface; retrieval connectors have no implicit write authority.
- **FR-013**: Link an explicitly captured native memory proposal to observed execution/source evidence when available; investigation summaries and temporary task progress MUST NOT automatically become durable memories.

### Acceptance and success criteria

- **SC-005**: Standalone capture still works without an execution ID; external retrieval and incident-summary fixtures create zero canonical memories without an explicit authorized capture.

**Scenario**: Given the declared capability and scope, when the integrated journey executes with the relevant provider or host failure, then the additional requirements above hold and the result distinguishes observed, enforced, missing and unsupported evidence.

### Compatibility and ownership

Integration contracts: Specs 019, 021. This feature owns its existing component adaptation only; new contract ownership is in `specs/integration-ownership.md`. New navigation follows Spec 022; historical four-workspace task text is retained as delivery history and is superseded for future integration. Preserve canonical authority, explicit activation, optional task state, host-owned checkpoints, local fallback and existing public contracts. No new capability may be advertised until its acceptance evidence passes.
