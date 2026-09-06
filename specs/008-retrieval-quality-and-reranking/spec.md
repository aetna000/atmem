# Feature Specification: Retrieval Quality, Embeddings, and Reranking

**Feature directory**: `specs/008-retrieval-quality-and-reranking`
**Created**: 2026-09-05
**Updated**: 2026-09-06
**Status**: Approved for implementation
**Input**: `todo.md` P0.4 and the cross-adapter retrieval investigation

## Overview

AtMem MUST retrieve paraphrased governed memory when the evidence is genuinely useful and MUST return an explicit no-useful-memory decision when it is not. Candidate generation, relevance, answer support, policy authorization, ranking, and delivery are separate stages. A weak diagnostic embedding MUST never turn an unrelated record into injected context.

OpenClaw is one supported host, not a special authority path. Dashboard query, `control_prepare`, Pydantic AI, LangGraph, OpenClaw, and MCP MUST consume the same typed retrieval decision and preserve the same authorization boundary.

## User Scenarios & Testing

### User Story 1 - Recall the right memory or inject nothing (Priority: P1)

A user can ask “what is my favourite lunch?” and retrieve “JT likes burgers.” If the user asks “what cars are available in Australia?”, unrelated facts about burgers or appearance are withheld.

**Why this priority**: Incorrect injection pollutes agent reasoning and destroys trust.

**Independent Test**: Run answerable paraphrases, topical non-answers, and unrelated prompts through dashboard, control, every adapter, OpenClaw, and MCP.

**Acceptance Scenarios**:

1. **Given** an authorized food-preference memory, **when** a paraphrased food query is submitted, **then** it is direct support and may be injected.
2. **Given** only unrelated personal memories, **when** an Australian-car query is submitted, **then** the result is `no_useful_memory` and no memory text is injected.
3. **Given** AtBot is unavailable, **when** the negative query runs, **then** deterministic fallback also withholds instead of selecting the first candidate.
4. **Given** an authorized food memory, **when** the user submits a bounded spelling error such as `pizzaa` or `burggger`, **then** hybrid retrieval recalls the intended food without relaxing the unrelated-query withholding gate.

### User Story 2 - Use a production semantic profile (Priority: P1)

An operator can configure and verify a strong local or hosted embedding model with exact model identity, dimensions, normalization, query/document prefixes, and epoch state. Hashing remains only for deterministic diagnostics, migration plumbing, and tests.

**Independent Test**: Build a supported strong epoch, restart AtMem, and meet held-out paraphrase and negative-query thresholds.

**Acceptance Scenarios**:

1. With no production model configured, semantic health labels hashing diagnostic and guides the operator to a strong local profile.
2. Changing provider/model/prefix/dimension makes the old epoch stale until rebuilt.
3. A supported strong profile applies model-specific query/document prefixes and normalization consistently.

### User Story 3 - Explain and reproduce a decision (Priority: P2)

An operator can see why memory was selected, treated as background, or withheld, including normalized signals, support class, policy/lifecycle checks, model identity, fallback state, and stable reason codes.

**Independent Test**: Reconcile every explanation to the recorded decision and reproduce it with the same calibration and embedding epochs.

### Edge Cases

- Empty candidates, equal or non-finite scores, stale epochs, byte overflow, and provider failure produce deterministic typed outcomes.
- Unauthorized, deleted, excluded, expired, or generation-changed records never contribute content to intelligence or delivery.
- Expansion may generate candidates but cannot prove they answer the original query.
- Trust and recency may reorder relevant candidates but cannot create relevance.
- Conservative spelling tolerance is a generic lexical fallback, not a substitute for production embeddings or model-based reranking.

## Requirements

### Functional Requirements

- **FR-001**: Retrieval MUST expose independently attributable lexical, fact-key, semantic, graph/entity when available, trust, recency, and AtBot contributions through a versioned signal contract.
- **FR-002**: AtMem MUST authorize before candidate content reaches intelligence and revalidate selected record IDs before context construction.
- **FR-003**: A versioned calibration profile MUST distinguish `direct_support`, `background_context`, and `no_useful_memory` with stable reason codes.
- **FR-004**: Deterministic fallback MUST be query-aware, abstain below threshold, and MUST NOT select the first candidate merely because one exists.
- **FR-005**: Hashing embeddings MUST be labelled diagnostic-only and MUST NOT independently make a record eligible for injection or be presented as production semantic quality.
- **FR-006**: A production semantic profile MUST record provider, exact model/revision, dimensions, distance, normalization, query prefix, document prefix, preprocessing version, and embedding epoch.
- **FR-007**: CLI help and Settings MUST let users select a supported strong local profile, explicitly approve any download, and automatically install, build, verify, and activate its vector epoch while preserving explicitly configured hosted/OpenAI-compatible providers.
- **FR-008**: Changing any FR-006 compatibility field MUST make the old epoch stale and require rebuild before querying it.
- **FR-009**: Raw scores from different scales MUST NOT be combined by uncalibrated `max` or addition; each signal MUST be normalized first.
- **FR-010**: Candidate-generation and injection-eligibility thresholds MUST be separate; trust and recency only reorder already relevant candidates.
- **FR-011**: Query expansion is candidate generation only; injection candidates MUST be rescored for answer support against the original query.
- **FR-012**: Only `direct_support` is injected by default. `background_context` requires an explicit policy-permitted request and remains labelled.
- **FR-013**: A general-knowledge query with no supported governed memory MUST return `no_useful_memory`, allowing the host to answer without memory.
- **FR-014**: Dashboard query, `control_prepare`, OpenClaw, Pydantic AI, LangGraph, and MCP MUST use the same versioned decision contract without host-specific ranking rules.
- **FR-015**: Optional AtBot/cross-encoder ranking accepts eligible candidates only, records model identity, and cannot add unknown, stale, or unauthorized IDs.
- **FR-016**: Decisions MUST safely explain normalized signals, thresholds, support, authorization/revalidation, degradation, and final rank without inaccessible content.
- **FR-017**: Final selection MUST preserve Spec 002 aggregation and `prepare_context_v1()` byte-stability and revalidation.
- **FR-018**: Calibration and evaluation MUST use separate checked-in fixtures covering paraphrase, topical non-answer, unrelated, temporal/conflict, privacy, poisoning, and fallback failures.
- **FR-019**: Evaluation MUST measure AtMem and MAY run pinned Mem0 comparison under equal documented assumptions; reports state actual results without dismissing or overstating them.
- **FR-020**: Query/vector/rerank caches MUST include authorization scope, generation, embedding epoch, calibration version, query bytes, and relevant policy inputs.

### Key Entities

- **Signal Contribution**: Algorithm/version, normalized and diagnostic raw score, evidence identity, and availability.
- **Retrieval Decision**: Eligible ordered IDs, support class, thresholds, fallback state, reason codes, and revalidation result.
- **Calibration Profile**: Versioned transformations/thresholds with training and holdout identities.
- **Embedding Profile**: Exact compatibility identity and health for document/query vectors.

## Success Criteria

- **SC-001**: AtMem reaches MRR@5 1.000 on the checked-in primary benchmark with zero unauthorized results.
- **SC-002**: The no-answer set reaches 1.000 withholding accuracy and zero incorrect injections.
- **SC-003**: At least 20 paraphrases and 20 unrelated/general queries meet the declared recall floor with zero privacy leakage.
- **SC-004**: The Australian-cars query injects none of the burger, appearance, or unrelated fixtures through dashboard, control, OpenClaw, Pydantic AI, LangGraph, and MCP.
- **SC-005**: AtBot/embedding/reranker failure has deterministic query-aware fallback with an explicit degraded reason and no increased incorrect injection.
- **SC-006**: Every benchmark selection/withholding reconciles with recorded signal components and calibration version.
- **SC-007**: Full Spec 002 authorization, deletion, generation, byte-stability, and delivery tests remain green.
- **SC-008**: Strong local setup, health, restart, staleness, and rebuild pass end to end.

## Out of Scope

Model-owned authorization, generated answers as canonical evidence, mandatory hosted egress, or entity/relationship storage owned by Spec 009.

## Assumptions

Specs 002 and 005 provide aggregation and semantic-epoch foundations. Spec 009 registers graph/entity signals later. Strong embedding dependencies remain optional and enterprise-compatible.
