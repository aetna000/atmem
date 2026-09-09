# Tasks: Entity and Relationship Memory

**Evidence policy**: Append verification to a new entry under `docs/implementation-evidence/009/` following `docs/implementation-evidence/README.md`. `docs/current-status.md` is a linked summary, not a raw test log; dated reviews are frozen. Task-ID suffixes are significant (see `specs/task-conventions.md`).

**Input**: Design documents from `specs/009-entity-relationship-memory/`

**Prerequisites**: Spec 008 plus the feature plan

**Organization**: Foundational work precedes independently testable user-story phases; release evidence and documentation finish the feature.

## Phase 1 — Foundational

- [x] [T001] Define versioned entity/relation/path/evidence/mutation contracts in `atmem/graph/models.py` and `atmem/schemas/v1/graph-path.json` (FR-001–FR-002)
- [x] [T003] Implement conservative alias resolution and ambiguity review in `atmem/graph/identity.py` and `tests/test_graph_aliases.py` (FR-006)

## Phase 2 — User Story 1 - Traverse evidence-backed relationships (Priority: P1)

- [x] [T002] [US1] Move compatible graph behavior into the `atmem/graph/` package and implement deterministic evidence-bound materialization/rebuild generations in `atmem/graph/store.py` without changing the public `atmem.graph` imports (FR-003)
- [x] [T004] [US1] Implement per-edge authorized bounded traversal in `atmem/graph/traverse.py` and register one entity/graph plugin through Spec 008's `atmem/retrieve/signals.py` registry from `atmem/retrieve/graph_signal.py`; do not modify base signal ownership (FR-004)

## Phase 3 — User Story 2 - Repair identity over time (Priority: P2)

- [x] [T005] [US2] Implement previewed merge/split/rename/delete/supersede with lineage in `atmem/graph/identity.py` and register graph repair through Spec 007's maintenance interface from `atmem/graph/maintenance.py` (FR-005)
- [x] [T006] [US2] Add CLI/dashboard path and mutation explanations with safe redaction in `atmem/cli.py`, `atmem/control/server.py`, and `atmem/control/assets/app.js`; preserve `docs/dashboard-design-language.md` and route shared shell changes through `specs/integration-ownership.md` (FR-007)

## Phase 4 — Verification and Release Evidence

- [x] [T007] Add graph-quality, multihop, temporal, cycle, cross-scope, and ambiguity benchmarks in `tests/test_graph_quality.py` (SC-001–SC-003)
- [x] [T008] Verify deletion/rebuild/backup/restore/rollback in `tests/test_graph_lifecycle.py` and document graph proof boundaries in `docs/entity-relationship-memory.md` (SC-004)

## Dependencies and Execution Order

**Cross-spec dependencies**: Spec 008.
**Task dependencies**: T001 → all; T002/T003 → T004/T005; T004/T005 → T006/T007; T007 → T008.


## Phase 5: Unified product integration

New work is unchecked. Existing task IDs and completion history remain intact. Contract prerequisites: Specs 019, 023; see the roadmap for foundation versus integration ordering.

- [ ] [T009] Define failing boundary fixtures for FR-008, FR-009, SC-005 using `tests/test_graph_lifecycle.py`; exercise authorized success, relevant failure, missing evidence and cross-scope refusal.
- [ ] [T010] Publish graph path provenance through common packages and lifecycle references in `atmem/graph/`, `atmem/retrieve/graph_signal.py` (FR-008, FR-009); depend on T009 and the published prerequisite contracts, preserving baseline behavior.
- [ ] [T011] Verify SC-005 through the affected public/host boundaries, run regression and applicable upgrade/privacy gates, and record exact tested versions, commands, unsupported configurations and results in `docs/implementation-evidence/009/` (new append-only entry; see `docs/implementation-evidence/README.md`); depend on T010 and do not mark completion from declarations alone.
