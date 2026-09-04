# Tasks: Entity and Relationship Memory

**Input**: Design documents from `specs/009-entity-relationship-memory/`

**Prerequisites**: Spec 008 plus the feature plan

**Organization**: Foundational work precedes independently testable user-story phases; release evidence and documentation finish the feature.

## Phase 1 — Foundational

- [ ] [T001] Define versioned entity/relation/path/evidence/mutation contracts in `atmem/graph/models.py` and `atmem/schemas/v1/graph-path.json` (FR-001–FR-002)
- [ ] [T003] Implement conservative alias resolution and ambiguity review in `atmem/graph/identity.py` and `tests/test_graph_aliases.py` (FR-006)

## Phase 2 — User Story 1 - Traverse evidence-backed relationships (Priority: P1)

- [ ] [T002] [US1] Move compatible graph behavior into the `atmem/graph/` package and implement deterministic evidence-bound materialization/rebuild generations in `atmem/graph/store.py` without changing the public `atmem.graph` imports (FR-003)
- [ ] [T004] [US1] Implement per-edge authorized bounded traversal in `atmem/graph/traverse.py` and register one entity/graph plugin through Spec 008's `atmem/retrieve/signals.py` registry from `atmem/retrieve/graph_signal.py`; do not modify base signal ownership (FR-004)

## Phase 3 — User Story 2 - Repair identity over time (Priority: P2)

- [ ] [T005] [US2] Implement previewed merge/split/rename/delete/supersede with lineage and repair in `atmem/graph/identity.py` and `atmem/maintenance.py` (FR-005)
- [ ] [T006] [US2] Add CLI/dashboard path and mutation explanations with safe redaction in `atmem/cli.py`, `atmem/control/server.py`, and `atmem/control/assets/app.js`; preserve `docs/dashboard-design-language.md` and route shared shell changes through `specs/integration-ownership.md` (FR-007)

## Phase 4 — Verification and Release Evidence

- [ ] [T007] Add graph-quality, multihop, temporal, cycle, cross-scope, and ambiguity benchmarks in `tests/test_graph_quality.py` (SC-001–SC-003)
- [ ] [T008] Verify deletion/rebuild/backup/restore/rollback in `tests/test_graph_lifecycle.py` and document graph proof boundaries in `docs/entity-relationship-memory.md` (SC-004)

## Dependencies and Execution Order

**Cross-spec dependency**: Spec 008.
**Task dependencies**: T001 → all; T002/T003 → T004/T005; T004/T005 → T006/T007; T007 → T008.
