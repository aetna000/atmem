# Tasks: Retrieval Quality and Reranking

**Input**: Design documents from `specs/008-retrieval-quality-and-reranking/`

**Prerequisites**: Specs 002 and 005 plus the feature plan

**Organization**: Foundational work precedes independently testable user-story phases; release evidence and documentation finish the feature.

## Phase 1 — Foundational

- [ ] [T001] Define typed candidate/signal/support/decision/explanation contracts in `atmem/retrieve/models.py` and `atmem/schemas/v1/retrieval-decision.json` (FR-001, FR-003, FR-006)
- [ ] [T002] Adapt lexical, fact-key, vector, trust, recency, and AtBot signals and define the downstream extension registry in `atmem/retrieve/signals.py`; preserve Spec 002 supporting-evidence fields and final `prepare_context_v1()` boundary (FR-001–FR-002)

## Phase 2 — User Story 1 - Recall a useful paraphrase or withhold (Priority: P1)

- [ ] [T003] [US1] Implement versioned calibration, no-useful-memory, and direct/background support decisions in `atmem/retrieve/rank.py` and `atmem/retrieve/calibration-v1.json` (FR-003–FR-004)
- [ ] [T005] [US1] Revalidate lifecycle/conflict candidates and integrate byte-stable context/evidence delivery in `atmem/retrieve/rank.py` and `atmem/memory.py` (FR-007–FR-008)

## Phase 3 — User Story 2 - Explain and degrade safely (Priority: P2)

- [ ] [T004] [US2] Add optional batched local cross-encoder and deterministic fallback/tie-breaking in `atmem/retrieve/rerank.py` (FR-005)
- [ ] [T006] [US2] Expose safe explanations and degradation reasons through `atmem/cli.py`, `atmem/control/server.py`, and `atmem/control/assets/app.js`; preserve `docs/dashboard-design-language.md` and route shared shell changes through `specs/integration-ownership.md` (FR-006)

## Phase 4 — Verification and Release Evidence

- [ ] [T007] Add Spec 002 compatibility, per-registered-signal ablation, paraphrase, temporal, conflict, unrelated, privacy, and failure benchmarks in `tests/test_retrieval_quality.py`, `tests/test_supporting_evidence.py`, and `atmem/benchmark/data/retrieval-quality-v1.json` (SC-001–SC-004)
- [ ] [T008] Shadow-evaluate and document calibration provenance/rollback in `docs/retrieval-quality.md`; run full regression gates

## Dependencies and Execution Order

**Cross-spec dependencies**: Specs 002 and 005. Spec 009 is a downstream signal plugin.
**Task dependencies**: T001 → all; T002 → T003/T007; T003 → T004/T005/T006; T004/T005 → T007; T007 → T008.
