# Tasks: 2.3.3 Retrieval Improvements and Continuing Research

## Approved stable release scope — 2026-09-17

The owner approved moving the 2× target to future work. T001–T039 retain their
honest research status; unchecked broad research tasks are not silently completed.
The original beta release sequence T018–T023 is superseded for stable 2.3.3 by
T040–T044. Default-promotion and comparative-claim gates remain in force.

- [x] [T040] Record approved stable scope, retaining default retrieval and disabling matrix reuse by default; preserve historical benchmark results.
- [x] [T041] Align AtMem/bridge 2.3.3 and unchanged AtBot 0.1.0; audit current docs and write `docs/releases/v2.3.3.md` with exact upgrade, compatibility and opt-in boundaries.
- [x] [T042] Run Python, companion, host/framework, UI, deterministic benchmark, build, metadata and installed/upgrade checks on the reviewed candidate. Evidence: `release-2.3.3.md`; preflight 35186097845 passed.
- [x] [T043] Review the exact release diff, commit/push, and pass release workflow preflight from a clean candidate before tagging. Candidate `6431296` passed; the evidence-only follow-up must also pass before tagging.
- [ ] [T044] Publish annotated `v2.3.3`, await publish workflow, verify stable GitHub release and PyPI/npm artifacts, and report exact identities. AtBot is unchanged and requires no new tag.

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

## Core hybrid amendment: independently scoped execution

- [x] [T029] Review FR-021–FR-024 design with Claude CLI read-only until substantive concerns are resolved; record analysis and review history in `docs/implementation-evidence/031/core-hybrid-review.md`.
- [x] [T030] Add failing fusion, independent nomination, scope isolation, support and fallback fixtures in `tests/test_retrieval_candidate_union.py` (FR-021–FR-024).
- [x] [T031] Implement scoped lexical/fact/semantic nomination and deterministic fusion in `atmem/retrieve/fusion.py`, `atmem/retrieve/hybrid.py`, `atmem/memory.py`, request contracts/schema, store streaming and `atmem/semantic/index.py`, preserving canonical revalidation (FR-021–FR-023).
- [x] [T032] Measure frozen quality fixtures and latency, run relevant native/control/semantic/delegated contracts, and document actual results and comparison limits in `docs/implementation-evidence/031/core-hybrid-benchmark.md` (FR-024). Measurement completed, not quality clearance; interrupted delegated-control check remains disclosed.
- [x] [T033] Obtain read-only Claude implementation review, fix substantive defects and re-review; reconcile tasks/docs without claiming full Spec 031 or release completion (FR-021–FR-024).
- [ ] [T034] Resolve measured core-fusion MRR regression through separately reviewed calibration in `atmem/retrieve/fusion.py` and validate on frozen unseen cases before adapter/default activation; rerun a genuinely matched Mem0 comparison (FR-007, FR-024).
- [ ] [T035] Integrate independently scope-safe graph nominations and measure corpus reuse/scaling before replacing legacy mixed graph requests in `atmem/memory.py`/`atmem/control/manager.py`; retain graph coverage and authority (FR-008, FR-021–FR-022).

## Scoped graph amendment: independently scoped execution

- [x] [T036] Review FR-025–FR-027 design and consistency; incorporate initial Claude feedback. Further Claude review waived by user on 2026-09-17 after session limit; locally check revised safeguards before code. Evidence: `docs/implementation-evidence/031/graph-nomination.md`.
- [x] [T037] Add graph-only/mixed nomination, hidden-bridge, lifecycle/egress, root/cycle/budget and stale-path tests in `tests/test_retrieval_graph_fusion.py`; implement `atmem/retrieve/graph.py` and integrate contracts, `hybrid.py` and protected audit path evidence (FR-025–FR-026).
- [x] [T038] Run graph/core/semantic/contract regressions and calibration with `tools/benchmark_core_hybrid.py`, including a fourth no-graph legacy control; retain quality, graph coverage and latency in `docs/implementation-evidence/031/graph-nomination.md` (FR-027). Measurement complete, quality/default-promotion gate not passed.
- [x] [T039] Review implementation locally (further Claude review waived by user), resolve substantive findings, rerun affected gates and recommend the next release default in evidence/status docs without claiming release completion (FR-025–FR-027).

## NumPy amendment: independently scoped execution

- [x] [T024] Specify FR-018–FR-020, obtain iterative read-only Claude review and resolve substantive findings before implementation; record feedback in `docs/implementation-evidence/031/numpy-review.md`.
- [x] [T025] Add cached/uncached equivalence, malformed vector, identity invalidation, optional dependency and bounded cleanup fixtures in `tests/test_semantic_matrix_cache.py` (FR-018–FR-019).
- [x] [T026] Implement bounded instance-local matrix reuse in `atmem/semantic/index.py`, without changing candidate selection or final validation; pass T025 (FR-018–FR-019).
- [x] [T027] Measure cold/reused/distinct-query and alternating-subject matrix preparation and search, run semantic/search/rebuild regression tests, and record commands/results/backend coverage/limits in `docs/implementation-evidence/031/numpy-benchmark.md` (FR-020).
- [x] [T028] Review implementation and spec consistency; mark only this slice complete when verified. No release/version changes; broader tasks remain open (FR-018–FR-020).

T001–T004 establish a frozen baseline. T005–T007 precede production edits. T008–T010 establish quality. T011–T015 optimize and measure one change at a time. T016–T019 expose measured facts. T020–T023 are final verification. T008/T009 and T011/T013 may be developed independently after fixtures, but their final benchmark is sequential on one immutable candidate. If T015 does not meet 2× on a comparable boundary, the report must say so and T019 cannot claim the target.
