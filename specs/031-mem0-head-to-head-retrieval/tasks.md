# Tasks: 2.3.3 Beta Retrieval and Mem0 Comparison

**Evidence:** append observed commands, exact identities, results and limitations under `docs/implementation-evidence/031/`; historical measurements remain unchanged. A checked task means implementation and its named independent validation passed, not merely that code exists.

## Phase 1: Freeze baseline and comparison rules

- [x] [T001] Pin the 2.3.2 commit, pre-change deterministic report, public LongMemEval-S dataset digest/cases, model endpoint and hardware in `docs/implementation-evidence/031/baseline.md`; preserve the 2.0.19 historical report (FR-002, SC-001).
- [ ] [T002] Re-run the pre-change raw LongMemEval retrieval campaign against AtMem and an isolated pinned Mem0 OSS build, deriving the result label from the installed package rather than a hardcoded 2.0.19 value; record per-case outputs, indexing time, warm/cold search, dependency/NLP/BM25 status and exact timed boundary, or report inability separately (FR-002–FR-005, SC-001).
- [x] [T003] Freeze calibration and held-out case IDs, valid comparison metric definitions and target/claim rules in `atmem/benchmark/data/` before quality tuning; test manifest mismatch rejection in `tests/test_benchmark_external.py` (FR-004–FR-007).
- [ ] [T004] Add an independent native `control_prepare` comparison profile and report schema under `tools/` and `atmem/benchmark/`, proving preparation versus delivery distinctions in `tests/test_benchmark_native.py` (FR-003–FR-006, FR-013, SC-001).

## Phase 2: Failing quality and authority fixtures

- [ ] [T005] Add original-query answer-support fixtures for daughter-age topical nonanswer, negation, entity ambiguity, corrections, spelling and non-Latin text in `tests/test_retrieval_quality.py` and held-out data; assert protected bytes and scope behavior at preparation boundaries (FR-001, FR-007–FR-009, SC-002, SC-004).
- [ ] [T006] Add independent lexical-only, fact-key-only, semantic-only and bounded-graph candidate nominations plus hidden cross-scope aggregate adversaries in `tests/test_retrieval_candidate_union.py` (FR-001, FR-008, SC-002).
- [ ] [T007] Add stale policy/membership/lifecycle/model/epoch/forget and final-reload cache races in `tests/test_retrieval_cache.py`, and one-record mutation counting-embedder plus interrupted activation tests in `tests/test_semantic_rebuild.py` (FR-001, FR-011–FR-012, SC-002, SC-005).

## Phase 3: Quality implementation

- [ ] [T008] Implement Unicode-aware concept tokens and general relation/attribute support in `atmem/retrieve/rank.py`, revise versioned calibration as required, and pass T005 without a case-specific answer rule (FR-009, SC-004).
- [ ] [T009] Introduce independent bounded authorized candidate nominations and measured fusion in `atmem/memory.py`/`atmem/store/sqlite.py`; preserve original-query gating and final preparation/revalidation; pass T006 and adapter conformance (FR-001, FR-008, FR-015).
- [ ] [T010] Measure held-out quality and ablations after T008–T009 using the frozen partition; keep any regression visible and do not tune after inspecting final held-out outcomes (FR-005–FR-007, SC-002, SC-004).

## Phase 4: Latency and indexing

- [ ] [T011] Mirror the versioned AtBot 0.1.0 deterministic expansion in a local pure helper used by the AtMem client, test parity without coupling AtBot's independent package to AtMem, avoid unnecessary health/request calls, and prove companion-unavailable fallback and equivalent selected bytes in `tests/test_atbot_companion.py`/control tests (FR-001, FR-010, SC-002).
- [ ] [T012] Integrate the existing scoped decision cache with complete identities, bounded entries and final reload; instrument real hit/miss behavior; pass T007 race fixtures without retaining ungoverned plaintext (FR-001, FR-011, SC-002).
- [ ] [T013] Reuse unchanged, identity-compatible embeddings during staged semantic rebuilds; preserve epoch activation/crash safety, derivative deletion and model/policy invalidation; pass T007 counting and failpoint fixtures (FR-001, FR-012, SC-005).
- [ ] [T014] Add content-free candidate, support, companion, reload and packing stage counts/timings to native retrieval diagnostics and the benchmark report, with secret/no-query logging tests (FR-013).
- [ ] [T015] Run per-step latency/quality ablations on the same fixed workloads; keep only optimizations that preserve authority and quality; report the observed ratio and uncertainty for the 2× target and 10× stretch (FR-005–FR-006, SC-002–SC-003).

## Phase 5: Product and documentation

- [ ] [T016] Expose the common authenticated benchmark summary and case drilldown read model in `atmem/service/` and CLI, with role and plaintext-denial tests (FR-014, SC-006).
- [ ] [T017] Add compact retrieval health and benchmark cards/drilldown to the existing dashboard under `atmem/control/assets/`, testing keyboard, desktop, narrow layout, no-result and failure states without creating a new settings wall (FR-014, SC-006).
- [ ] [T018] Audit all tracked Markdown for current status/version contradictions and broken local links; update README, `docs/benchmarks.md`, `docs/current-status.md`, `docs/release-roadmap.md` and active cross-links, retaining dated historical evidence (FR-016, SC-007).
- [ ] [T019] Write honest `docs/releases/v2.3.3b1.md` with user-visible changes, exact beta install/upgrade/rollback, migration/opt-in, verified compatibility, benchmark method/result and limitations; align all AtMem/bridge/AtBot pins if a release candidate is prepared (FR-016–FR-017, SC-007).

## Phase 6: Beta verification

- [ ] [T020] Run deterministic, held-out, Mem0 head-to-head and native-path benchmarks on the exact reviewed candidate; retain per-case, full stage and aggregate reports with matched identities in `docs/implementation-evidence/031/` (FR-002–FR-007, SC-001–SC-004).
- [ ] [T021] Run full relevant Python, AtBot, OpenClaw build/typecheck/hook and locked-host tests, Pydantic AI/LangGraph/MCP contracts, UI and docs checks; fix regressions within this feature (FR-001, FR-014–FR-017, SC-002, SC-006–SC-007).
- [ ] [T022] Build and install the beta wheel and npm bridge in isolated environments; verify metadata, version pins, upgrade from 2.3.2 and no new base dependencies or plaintext derivative leaks; record all package hashes (FR-001, FR-016–FR-017).
- [ ] [T023] Review the final diff, task/evidence coverage, benchmark claims and unresolved limits. A beta tag/push/publish happens only under the repository release procedure when expressly requested as a release, and only after all required gates pass (FR-017, SC-001–SC-007).

## Dependencies and checkpoints

T001–T004 establish a frozen baseline. T005–T007 precede production edits. T008–T010 establish quality. T011–T015 optimize and measure one change at a time. T016–T019 expose measured facts. T020–T023 are final verification. T008/T009 and T011/T013 may be developed independently after fixtures, but their final benchmark is sequential on one immutable candidate. If T015 does not meet 2× on a comparable boundary, the report must say so and T019 cannot claim the target.
