# Feature Specification: Governed Supporting-Evidence Ranking

**Feature directory**: `specs/002-supporting-evidence-ranking`
**Created**: 2026-09-02
**Status**: Approved for planning
**Input**: Improve evidence ranking after a matched LongMemEval-S campaign found every required session in AtMem's top five but placed one first relevant session at rank two. Implement `vector candidates → supporting-chunk aggregation → AtBot reranking → AtMem revalidation` without weakening authority, privacy, fallback, or compatibility.

## Overview

AtMem already authorizes candidate records before AtBot sees their content and revalidates AtBot's returned record IDs before context construction. It does not yet recognize that several eligible records can be independent chunks from the same authorized source session. A single attractive decoy chunk can therefore outrank a source supported by multiple relevant chunks.

This feature adds deterministic supporting-evidence aggregation inside AtMem's authority boundary. Only records already reloaded from canonical storage and proven eligible may contribute to a group score. AtBot receives the eligible records plus bounded, inspectable aggregation signals and may reorder only those record IDs. AtMem then performs its existing final revalidation before producing context. When AtBot is unavailable, the deterministic aggregated order is the safe fallback.

The feature improves robust ranking rather than hard-coding a benchmark answer. It must be evaluated on per-case evidence and a held-out sample, not accepted solely because one recorded score becomes `1.000`.

## User Scenarios and Acceptance

### User Story 1 — Related evidence reinforces the correct source (P1)

As an agent user, I want several relevant memory chunks from the same source session to reinforce one another so the most evidentially supported governed memory is selected before a superficially similar decoy.

**Independent test**: Create eligible records in two source sessions where one session has multiple moderately strong relevant chunks and the other has one marginally stronger decoy. The aggregated order ranks the supported session first while retaining all record-level scores.

**Acceptance scenarios**:

1. Given two or more eligible records with the same canonical source session, when candidates are prepared, then each receives the same opaque support-group identity and deterministic group evidence signals.
2. Given a supported group and a single-chunk decoy, when their aggregate scores differ, then the candidates are ordered by aggregate score before AtBot is called.
3. Given a record without a source session, when aggregation runs, then it forms a record-local singleton group and its score is not fabricated from another record.

### User Story 2 — Authorization remains stronger than ranking (P1)

As a memory owner, I want inaccessible, deleted, excluded, quarantined, stale, sensitive-for-egress, or cross-scope records to have no effect on ranking.

**Independent test**: Add a high-scoring ineligible record sharing a source-session label with an eligible record. The ineligible record is absent from AtBot input and does not change the eligible record's aggregate score.

**Acceptance scenarios**:

1. Given an ineligible candidate, when a durable candidate set is created, then it cannot contribute its score, count, content, identifier, or session metadata to supporting-evidence signals.
2. Given remote AtBot egress, when a source session contains sensitive or restricted records, then those records are rejected before aggregation and cannot influence remote ranking.
3. Given AtBot returns an unknown, stale, deleted, or newly ineligible ID, when context is prepared, then AtMem rejects it using the existing final validation boundary.
4. Given two different subjects or workspaces use the same host session text, when groups are formed, then no group identity or score crosses authority scopes.

### User Story 3 — Safe deterministic fallback and inspectable reasoning (P1)

As an operator, I want retrieval to remain useful and explainable when AtBot is unavailable, without adding a new model or database dependency.

**Independent test**: Disable AtBot and query a candidate set with grouped evidence. The fallback selects the first aggregated eligible record and reports that aggregation participated without exposing raw session identifiers.

**Acceptance scenarios**:

1. Given AtBot is unavailable, when eligible candidates exist, then fallback uses the deterministic aggregated ordering.
2. Given equal aggregate scores, when ordering candidates, then deterministic tie-breaking produces the same order across runs.
3. Given a candidate result, when inspected, then it exposes the record score, group support score, aggregate score, eligible support count, algorithm version, and opaque group identity.
4. Given audit evidence, when inspected, then it contains the aggregation algorithm identity and a digest of bounded signals, but not raw query text, memory content, or raw session identifiers.

### User Story 4 — AtBot can improve but never widen selection (P2)

As an integrator, I want AtBot to rerank candidates using supporting-evidence signals while remaining unable to introduce memory.

**Independent test**: Supply eligible candidates with aggregation signals to a fake AtBot. Valid reorderings are accepted; an extra record ID causes fallback or rejection and never enters prepared context.

**Acceptance scenarios**:

1. Given aggregation signals, when AtBot is available, then it receives only eligible candidate content and additive bounded signals.
2. Given AtBot returns a subset or permutation of eligible record IDs, when AtMem revalidates it, then only still-eligible IDs reach context serialization.
3. Given malformed signals or AtBot failure, when ranking proceeds, then AtMem safely uses deterministic aggregated ordering or withholds context according to existing policy.

### User Story 5 — Benchmark evidence explains improvements and regressions (P2)

As a maintainer, I want per-case ranking evidence and reproducible focused runs so a score change can be diagnosed rather than merely reported.

**Independent test**: Run one selected LongMemEval case and a fixed stratified campaign. Reports identify expected and retrieved sessions, ranks, aggregate inputs, latency, and the declared comparison outcome.

**Acceptance scenarios**:

1. Given a case identifier, when the campaign runner is invoked, then it runs only that eligible case or fails clearly if the case is unavailable.
2. Given a completed campaign, when its report is saved, then per-case results are retained rather than discarded from published evidence.
3. Given the existing 12-case selection, when AtMem is rerun, then recall@5 remains `1.000` and MRR@5 does not regress below `0.9583`.
4. Given a larger held-out selection, when evaluated, then its results are reported separately and are not mixed into the recorded 12-case result.

## Functional Requirements

- **FR-001**: AtMem MUST aggregate supporting evidence only after canonical reload, lifecycle filtering, exclusion filtering, scope validation, and egress-policy validation.
- **FR-002**: AtMem MUST group eligible candidates by a scope-bound opaque identity derived from canonical source-session provenance; records without a source session MUST use record-local singleton groups.
- **FR-003**: Raw customer session identifiers MUST NOT be disclosed in AtBot payloads, candidate signals, audit payloads, product summaries, or remote egress. An offline benchmark report MAY retain dataset-native evidence-session labels required by its declared scorer; those labels are benchmark fixtures, not customer provenance or product egress.
- **FR-004**: The aggregation algorithm MUST be deterministic, versioned, bounded, and dependency-free. It MUST retain the original record score and calculate a bounded support score, support count, and aggregate score.
- **FR-005**: The initial algorithm MUST add a bounded peer-support bonus equal to `0.15 × mean(up to two strongest other eligible scores in the group) × (1 - record_score)`. Scores MUST remain in `[0, 1]`; ties MUST resolve by original rank and then record ID.
- **FR-006**: Aggregation MUST NOT increase a singleton candidate's score above its bounded original score.
- **FR-007**: Durable candidate-set content and digests MUST include the additive aggregation signals so later mutation is detectable without a persistent schema migration.
- **FR-008**: Dashboard query and `control_prepare` MUST use aggregated deterministic ordering before invoking AtBot.
- **FR-009**: AtBot MUST receive only candidates from the durable eligible set and MUST be unable to add an unknown record ID.
- **FR-010**: AtMem MUST revalidate every AtBot-ranked ID through `prepare_context_v1()` before context construction; this feature MUST NOT weaken expiry, generation, lifecycle, deletion, exclusion, scope, or byte-stable serialization checks.
- **FR-011**: If AtBot is unavailable or fails, fallback MUST use the deterministic aggregated order and MUST remain local-first.
- **FR-012**: Candidate inspection and retrieval evidence MUST expose algorithm version, original score, support score, aggregate score, eligible support count, and opaque support-group identity without content or session identifiers in hash-chain payloads.
- **FR-013**: Existing `atmem-eligible-candidate-v1`, `atmem-eligible-candidate-set-v1`, and AtBot protocol-v1 consumers MUST remain compatible through additive `signals` fields; no SQLite migration or mandatory dependency may be introduced.
- **FR-014**: Existing OpenClaw, generic host, Pydantic AI, LangGraph, dashboard, shadow-mode, multi-agent, deletion, and fallback behavior MUST remain green.
- **FR-015**: The LongMemEval runner MUST support a focused case selector and retain per-case aggregation evidence in external result files.
- **FR-016**: The recorded 12-case regression MUST retain `session_recall_any_at_5 = 1.0`, `session_recall_all_at_5 = 1.0`, and `session_mrr_at_5 >= 0.9583`; any improvement claim MUST also include a separately identified held-out result.
- **FR-017**: Tests MUST prove that ineligible same-session records cannot affect group signals, AtBot input, fallback order, or final context.

## Edge Cases

- All candidates are singletons; ordering remains equivalent to bounded original scores.
- A group contains more than three eligible candidates; only the two strongest peers for each record contribute to its bounded support mean while the eligible count remains visible.
- Candidate scores are negative, greater than one, missing, NaN, or infinite; invalid values fail closed or normalize deterministically without entering persisted JSON as non-finite numbers.
- Two eligible sessions produce the same opaque digest due to an implementation defect; group material must include the full authority tuple and canonical session value before hashing, and tests cover scope separation.
- Several query expansions nominate the same record; it remains one candidate with merged query evidence and one contribution to its group.
- A candidate becomes stale after aggregation; final context preparation rejects it, and its earlier group support cannot authorize another record.
- AtBot returns no IDs; AtMem produces no context unless existing fallback policy explicitly selects the deterministic first eligible candidate before the AtBot call.

## Success Criteria

- **SC-001**: Unit tests cover singleton, multi-chunk support, bounded top-three support, deterministic ties, invalid scores, and scope-separated opaque groups.
- **SC-002**: Security tests demonstrate zero influence from deleted, excluded, quarantined, cross-scope, and remote-egress-ineligible records.
- **SC-003**: Integration tests show dashboard query and `control_prepare` both execute durable authorization, aggregation, AtBot ranking, and final revalidation in that order.
- **SC-004**: With AtBot unavailable, tests show the deterministic aggregated first candidate is selected without network or optional model dependencies.
- **SC-005**: The full existing test suite passes without a SQLite migration, new base dependency, or changed public versioned format identifier.
- **SC-006**: A reproducible focused benchmark identifies the formerly rank-two case and records its before/after rank evidence.
- **SC-007**: The fixed 12-case campaign meets FR-016, and a separately labeled held-out campaign is recorded before claiming general ranking improvement.

## Out of Scope

- Making AtBot a memory authority or independent agent.
- Changing canonical memory admission, deletion, scope, sensitivity, or exposure policy.
- Adding a cross-encoder, hosted provider, new vector database, or mandatory model SDK.
- Altering Mem0 configuration or weighting results to guarantee that AtMem wins.
- Persisting raw source-session identifiers in new evidence fields.
- Claiming that `MRR@5 = 1.000` on 12 questions proves general superiority.

## Compatibility and Migration

- No canonical or derived SQLite schema change.
- No package dependency change.
- Existing candidate and AtBot protocol format identifiers remain unchanged.
- Aggregation fields are additive entries inside the already-extensible candidate `signals` mapping.
- Older AtBot companions may ignore the new signals and continue returning eligible record IDs; AtMem fallback and final revalidation remain authoritative.
