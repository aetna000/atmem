# Tasks: Memory Quality Benchmarks

## Phase 1: Setup and Contracts

- [x] T001 Create the benchmark package and public exports in `atmem/benchmark/__init__.py` (FR-001, FR-013)
- [x] T002 Implement versioned case, profile, metric, case-result, report, and comparison validation plus canonical digests in `atmem/benchmark/contracts.py` (FR-001, FR-005, FR-006, FR-013, FR-014, FR-016)
- [x] T003 [P] Add public case and report schemas in `atmem/schemas/v1/benchmark-cases.schema.json` and `atmem/schemas/v1/benchmark-report.schema.json` (FR-001, FR-013)
- [x] T004 [P] Add contract, digest, invalid-input, unavailable-metric, and secret-minimization tests in `tests/test_benchmark_contracts.py` (SC-004, SC-005, SC-007)

## Phase 2: Deterministic Release Gate

- [x] T005 Add at least 16 positive/negative synthetic cases and versioned thresholds in `atmem/benchmark/data/deterministic-v1.json` and `atmem/benchmark/data/thresholds-v1.json` (FR-002, FR-009, SC-002, SC-003)
- [x] T006 Implement isolated case execution, final-context inspection, metric aggregation, unavailable usage/cost handling, and stable quality digests in `atmem/benchmark/runner.py` (FR-003–FR-006, FR-010, FR-011)
- [x] T007 Implement absolute safety gates and checked-in extraction/contradiction/retrieval non-regression floors in `atmem/benchmark/runner.py` (FR-009, SC-003)
- [x] T008 Add deterministic category, scoring-math, safety-failure, threshold-failure, and repeatability tests in `tests/test_benchmark_runner.py` (SC-001–SC-005, SC-007)

## Phase 3: Execution Profiles

- [x] T009 Implement deterministic, local-embeddings, local-AtBot, and hosted-AtBot profile definitions, availability diagnostics, explicit egress metadata, and structured skips in `atmem/benchmark/profiles.py` (FR-007, FR-008)
- [x] T010 Connect available optional profiles to the common runner without changing AtMem authority or importing optional SDKs on the deterministic path in `atmem/benchmark/runner.py` (FR-007, FR-010, FR-018)
- [x] T011 Add profile identity, unavailable-profile, missing-usage, missing-price, and no-optional-import tests in `tests/test_benchmark_runner.py` (FR-005–FR-008, SC-004, SC-007)

## Phase 4: External Evaluation and Fair Comparison

- [x] T012 Implement local LongMemEval JSON/JSONL normalization with supported/skipped/unsupported accounting in `atmem/benchmark/external.py` (FR-012)
- [x] T013 Implement external-result validation and fair-comparison rejection for dataset, case-set, scoring, and model mismatches in `atmem/benchmark/external.py` (FR-013, FR-014, SC-006)
- [x] T014 [P] Add an exact Mem0 OSS environment manifest in `atmem/benchmark/data/mem0-oss-v1.json` without adding it to AtMem dependencies (FR-013, FR-018)
- [x] T015 [P] Add licensed synthetic external fixtures and adapter/comparison tests in `tests/fixtures/benchmarks/`, `tests/test_benchmark_external.py` (FR-012–FR-014, SC-006, SC-007)

## Phase 5: CLI, Packaging, and Documentation

- [x] T016 Add `benchmark run`, `profiles`, `import-longmemeval`, and `compare` parsing, human guidance, JSON output, report-file output, and exit semantics in `atmem/cli.py` (FR-009, FR-012–FR-017)
- [x] T017 Add CLI coverage for default pass, threshold failure, optional skip, report creation, JSON output, import, and mismatch rejection in `tests/test_benchmark_cli.py` (FR-009, FR-017, SC-007)
- [x] T018 Package benchmark JSON data without changing runtime dependencies in `pyproject.toml` and add package-data coverage in `tests/test_benchmark_contracts.py` (FR-018)
- [x] T019 Document copyable offline, optional-profile, LongMemEval, and Mem0 comparison commands and limitations in `docs/benchmarks.md` and link them from `README.md` (FR-015, FR-017, SC-008)
- [x] T020 Protect customer-visible benchmark claims and documentation links in `tests/test_documentation.py` (Constitution VI, SC-008)

## Phase 6: Verification and Release Evidence

- [x] T021 Run the deterministic gate twice and retain a normalized example report in `docs/examples/benchmark-deterministic-v1.json` (SC-001, SC-005, SC-008)
- [x] T022 Run focused benchmark tests and the full existing pytest suite, fixing only regressions within this feature's approved scope (FR-017, FR-018, Constitution VI)
- [x] T023 Reconcile `spec.md`, `plan.md`, implementation, and benchmark evidence so controlled AtMem-versus-Mem0 results state their measured winner directly in `docs/benchmarks.md` (FR-015)

## Phase 7: Convergence

- [x] T024 Connect opted-in local/hosted AtBot profiles to actual health-verified companion ranking of AtMem-authorized candidates and fail safely if ranking becomes unavailable per FR-007 and plan §4 (partial)
- [x] T025 Connect the opted-in local-embeddings profile to an explicitly configured embedder and verified temporary semantic epoch per FR-007 and plan §4 (partial)

## Phase 8: Comparison Outcome Alignment

- [x] T026 Replace non-conclusive Mem0 comparison language with declared metric directions, per-metric winners, and Pareto overall outcomes in `atmem/benchmark/external.py`, `docs/benchmarks.md`, and comparison tests per FR-014–FR-015 (partial)
- [x] T027 Run a matched 12-case, six-category LongMemEval-S retrieval campaign against AtMem and pinned Mem0 OSS 2.0.19 with identical raw chunks and `nomic-embed-text:latest`; publish the runner, configuration, result, and direct comparison outcome in `tools/run_longmemeval_retrieval.py` and `docs/examples/longmemeval-s-retrieval-12-v1.json` (FR-013–FR-015)

## Phase 9: Remaining End-to-End Profile Evidence

- [ ] T028 Run the local AtBot profile end to end against a configured, version-pinned local model; retain exact identity, availability, results, latency, and limitations in `docs/examples/benchmark-local-atbot-v1.json` and add an installed-package smoke test in `tests/test_benchmark_profiles_e2e.py` (FR-006–FR-008, SC-004, SC-008)
- [ ] T029 Run the hosted AtBot profile end to end with explicit opt-in; retain provider/model identity, egress, token usage, pricing source/time or explicit unknown cost, results, latency, and redacted diagnostics in `docs/examples/benchmark-hosted-atbot-v1.json` with credential-safety coverage in `tests/test_benchmark_profiles_e2e.py` (FR-005–FR-008, FR-015–FR-016, SC-004, SC-008)
