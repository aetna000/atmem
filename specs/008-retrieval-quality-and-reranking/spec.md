# Feature Specification: Retrieval Quality and Reranking

**Feature directory**: `specs/008-retrieval-quality-and-reranking`
**Created**: 2026-09-05
**Status**: Draft
**Input**: `todo.md` P0.4

## Overview

Combine independently measurable retrieval signals into an explainable, calibrated ranking that confidently returns no useful memory when evidence is weak. Related context must not be mislabeled as a direct answer.

## User Scenarios & Testing

### User Story 1 - Recall a useful paraphrase or withhold (Priority: P1)

Authorized lexical, fact-key, vector, trust, recency, and optional AtBot signals generate candidates through an extensible signal contract. Spec 009 registers entity and graph signals through that contract after the base ranker is available. Calibrated eligibility and answer-support thresholds determine whether a result is direct support, background context, or withheld.

**Why this priority**: Useful recall and reliable withholding are the core user-visible retrieval outcomes.

**Independent Test**: Run answerable, topical-non-answer, and unrelated holdout fixtures with the base registered signals.

**Acceptance Scenario**: **Given** authorized candidates, **when** ranking runs, **then** it returns calibrated direct/background support or explicit `no_useful_memory`.

### User Story 2 - Explain and degrade safely (Priority: P2)

Every result explains contributing signals, normalized scores, scope/lifecycle checks, policy decisions, rerank stage, final rank, and withhold reason. If an optional local cross-encoder or AtBot fails, deterministic ranking is used and degradation is visible.

**Why this priority**: Operators must understand and reproduce ranking and fallback decisions.

**Independent Test**: Disable each optional ranker and reconcile every explanation component to the deterministic decision.

**Acceptance Scenario**: **Given** an optional reranker failure, **when** ranking completes, **then** deterministic order is used and the exact degradation reason is reported.

### Edge Cases

- Empty candidates, equal scores, non-finite scores, missing signal providers, stale epochs, and byte-budget overflow produce deterministic typed outcomes.
- Conflicting temporal facts retain evidence; unauthorized or deleted candidates never contribute scores or explanation metadata.
- A topical but non-answering memory is classified as background or withheld, never direct support.

## Requirements

### Functional Requirements

- **FR-001**: Each registered retrieval signal MUST be independently switchable, measured, and attributable in benchmark output. This feature owns lexical, fact-key, vector, trust, recency, and AtBot signal adapters plus the extension contract; Spec 009 owns entity and graph signal implementations.
- **FR-002**: Candidate generation MUST occur only inside authorized scope; every candidate MUST be revalidated for scope and lifecycle before ranking and delivery.
- **FR-003**: Versioned calibration MUST define candidate, useful-memory, and direct-answer-support thresholds plus an explicit `no_useful_memory` outcome.
- **FR-004**: Merely topical content MUST NOT be described or injected as direct answer support without evidence that satisfies the support threshold.
- **FR-005**: Optional local cross-encoder reranking MUST receive authorized candidates only, record model identity, and fall back deterministically on absence/failure.
- **FR-006**: Explanations MUST use stable signal/reason codes and expose score, scope, policy, lifecycle, stage, and rank without leaking inaccessible content.
- **FR-007**: Conflicts and temporal facts MUST preserve competing evidence and rank the lifecycle-valid current claim without erasing history.
- **FR-008**: Ranking MUST honor byte-stable context selection and exact-delivery receipts.

### Key Entities

- **Signal Contribution**: Named algorithm/version, normalized score, evidence identity, and availability state.
- **Rank Decision**: Ordered eligible IDs, support class, thresholds, fallback state, and reason codes.
- **Calibration Profile**: Versioned thresholds, training/holdout identities, and metric directions.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Ablation reports exist for every signal registered in this release on paraphrase, temporal, conflict, unrelated, and privacy fixtures; Spec 009 adds alias and multi-hop graph coverage when its signals register.
- **SC-002**: The checked-in calibration meets declared recall floors while producing zero unauthorized results and the declared maximum incorrect-injection rate.
- **SC-003**: Cross-encoder failure produces the same deterministic fallback ordering and an explicit degraded reason.
- **SC-004**: For every benchmark selection or withhold, aggregate scores reconcile with recorded component signals.

## Out of Scope

Implementing entity or graph signals (Spec 009), letting a ranker authorize data, treating generated answers as canonical evidence, or requiring an optional model for base retrieval.

## Assumptions

- Specs 002 and 005 provide supporting-evidence and semantic-epoch foundations.
- Spec 009 registers graph/entity signals after the base extension contract is available.
- Calibration fixtures are versioned and distinct from final evaluation fixtures.
