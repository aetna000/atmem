# Tasks: Production Storage Backends

**Input**: Design documents from `specs/010-production-storage-backends/`

**Prerequisites**: Specs 005 and 008 plus the feature plan

**Organization**: Foundational work precedes independently testable user-story phases; release evidence and documentation finish the feature.

## Phase 1 — Foundational

- [ ] [T001] Define versioned canonical/derived protocols, capabilities, errors, and conformance fixtures in `atmem/core/storage.py` and `tests/storage/conformance.py` (FR-001–FR-005)

## Phase 2 — User Story 1 - Select and operate a backend (Priority: P1)

- [ ] [T002] [US1] Adapt SQLite/local sidecar in `atmem/store/sqlite.py` and `atmem/semantic/index.py` and prove behavioral parity in `tests/storage/test_sqlite_conformance.py` (FR-002)
- [ ] [T003] [US1] Implement optional PostgreSQL canonical adapter with migrations/concurrency/recovery in `atmem/store/postgres.py` and `tests/storage/test_postgres.py` (FR-002, FR-004)
- [ ] [T004] [US1] Implement generation-bound pgvector and Qdrant derived adapters in `atmem/semantic/pgvector.py` and `atmem/semantic/qdrant.py` (FR-002–FR-005)
- [ ] [T005] [US1] Add cross-backend backup/restore/migration/deletion and fault tests in `tests/storage/test_backend_lifecycle.py` (FR-004–FR-005)
- [ ] [T008] [US1] Add connection/TLS/lag/outage health and deterministic degradation in `atmem/store/health.py` and `tests/storage/test_backend_health.py` (FR-011)

## Phase 3 — User Story 2 - Meet measured performance safely (Priority: P2)

- [ ] [T006] [US2] Add privacy-safe per-stage profiling and query-plan capture in `atmem/telemetry/__init__.py`, `atmem/telemetry/retrieval.py`, and `tools/benchmark_storage.py` (FR-006–FR-008)
- [ ] [T007] [US2] Implement bounded scope/generation/digest cache and complete invalidation matrix in `atmem/retrieve/cache.py` and `tests/test_retrieval_cache.py` (FR-009–FR-010)
- [ ] [T009] [US2] Publish dataset/concurrency targets and cold/warm/degraded evidence with `tools/benchmark_storage.py` in `docs/storage-performance.md` (SC-001–SC-004)

## Phase 4 — Verification and Release Evidence

- [ ] [T010] [P] Verify Python 3.10–3.13, Apache-2.0-compatible dependency licensing, clean base installation, and—if SQLite schema changes—real persisted upgrades from published AtMem versions in `pyproject.toml`, `tools/smoke_upgrade_from_2_1.py`, and `tests/test_storage_packaging.py` (FR-012–FR-013, SC-005)

## Dependencies and Execution Order

**Cross-spec dependencies**: Specs 005 and 008.
**Task dependencies**: T001 → all; T002 → T003/T004; T003/T004 → T005/T008/T009; T006 → T007/T009; T005/T007/T008 → T009; T010 gates release.
