# Tasks: Retrieval Quality and Benchmark Release Gate

**Input**: [spec.md](spec.md), [research.md](research.md), [plan.md](plan.md)
**Release target**: AtMem 2.3.8 final; prereleases may remain integration betas
**Rule**: The benchmark is an inert consumer of public product APIs. No task may
add benchmark-only retrieval, memory formation, answer hints, or recovery logic.

## Phase 1 — Freeze the scientific protocol

- [ ] [T001] Commit a salted-hash domain-by-ability question-ID split with every inspected dev10 ID in development, then record dataset commits, exact reader/provider revision and routing, reader/judge prompts, matched comparator settings, hardware, random seeds, external artifact root, one primary confirmation arm, operating points, repetitions and the 20-run ceiling/eight-run target in `benchmarks/retrieval_quality/protocols/2.3.8.yaml` before typed or paid runs (FR-029–FR-036, SC-005–SC-006).
- [x] [T002] Add a claim vocabulary distinguishing local fixture pass, unseen-question confirmation, complete official score, Medium scale result, Pareto result and leaderboard submission in `benchmarks/retrieval_quality/README.md` (FR-029, FR-043, SC-009–SC-010).
- [ ] [T003] Freeze benchmark-neutral formation/retrieval fixtures from at least two ordinary product domains per promoted type, with queries, distractors, scopes, exact gold source IDs/ranges and digest-backed matching rules covering exact values, UI labels, negation, corrections, historical/current transitions, multi-episode procedures, rules, conflicts, multi-hop evidence, media references and scope attacks under `tests/fixtures/retrieval-quality/` before tuning (FR-005–FR-026, SC-001–SC-002).
- [x] [T004] Define machine-readable stage metrics and failure labels for formation, nomination, expansion, sufficiency, packing and reader use in `atmem/schemas/v1/retrieval-stage-event.json` and `benchmarks/retrieval_quality/protocols/failure-taxonomy.yaml` (FR-027, SC-006).
- [x] [T005] Add protocol validation tests that reject missing pins, overlapping development/confirmation splits, unregistered retries, benchmark-root violations and unapproved paid configurations in `tests/test_retrieval_quality_protocol.py` (FR-029–FR-036, SC-005–SC-008).

## Phase 2 — Add host-neutral typed contracts

- [x] [T006] Extend `atmem/extract/models.py` additively with typed payloads for atomic facts, durable rules, environment state, state transitions, procedures, failure gotchas and premise constraints while preserving the existing ExtractionProposal v2 admission path (FR-005–FR-010).
- [x] [T007] Add entity, relation/action, value, polarity, event/observation/valid time, scope, exact source, confidence, lifecycle and formation identity fields exactly once across the common typed-unit envelope and kind payloads in `atmem/extract/models.py` (FR-001–FR-009).
- [x] [T008] Add versioned lossless episode-ingest, formation receipt, information need, evidence neighborhood, sufficiency decision, Context Package V2 and byte-stable V1 projection models in `atmem/contracts/models.py` and JSON schemas under `atmem/schemas/v1/` and `atmem/schemas/v2/` (FR-003, FR-012–FR-025, FR-051–FR-052).
- [x] [T009] Add schema round-trip, malformed payload and forward-compatible unknown-field tests in `tests/test_retrieval_quality_contracts.py` (FR-003, FR-024, FR-038).
- [x] [T010] Add property tests for stable unit identity, polarity, temporal ordering, procedure ordering and deterministic serialization in `tests/test_retrieval_quality_contracts.py` (FR-006–FR-011).
- [ ] [T072] Add a versioned per-stage budget envelope contract and enforce source bytes, proposals, concurrency, deadlines, candidates, graph visits, neighbor depth and context bytes with visible loss/partial receipts in formation and retrieval services (FR-004, FR-012, FR-019, FR-025, FR-047).
- [x] [T079] Add a runtime vocabulary architecture test that rejects benchmark repository imports, official ability/application labels and split strata names anywhere under `atmem/` product runtime modules (FR-028, FR-033, FR-044).

## Phase 3 — Persist one source and rebuildable derived views

- [ ] [T011] Extend SQLite and PostgreSQL through their existing migration registries with persistent exact/FTS lookup, bounded canonical reloads, additive formation receipts, source adjacency and typed-link generations in `atmem/store/sqlite.py` and `atmem/store/postgres.py`; legacy records remain queryable before typed activation (FR-002, FR-010–FR-012, FR-038–FR-039, FR-047–FR-048).
- [ ] [T012] Store full source bytes once in protected evidence and reference them from canonical units and derived indexes by stable protected IDs in `atmem/store/` (FR-002, FR-010, FR-036).
- [ ] [T013] Add encrypted semantic metadata handling so plaintext database inspection cannot reveal typed payloads, entities, relations or source text in `atmem/store/` (FR-001–FR-002, FR-037).
- [ ] [T014] Add per-category storage accounting and bounded per-source/per-scope proposal quotas with explicit withholding receipts by extending the existing extraction/application service and `atmem/control/manager.py` (FR-004, FR-012, FR-040).
- [ ] [T015] Implement an interruption-safe, generation-based migration in the existing `atmem/store/sqlite.py` migration registry and PostgreSQL `_migrate` path that inventories legacy records, builds typed state, verifies source links/counts and atomically activates without inventing unavailable structure (FR-038–FR-039).
- [ ] [T016] Add SQLite/PostgreSQL migration, interruption, rollback, rebuild, upgrade and cross-version fixture tests in `tests/test_retrieval_migration.py` (FR-038–FR-039, SC-007).
- [ ] [T017] Add deletion tests spanning canonical units, source links, lexical/vector/graph views, caches, backups and exports in `tests/test_retrieval_derivative_deletion.py` (FR-001–FR-002, FR-038).
- [ ] [T018] Add storage-growth tests proving source text is not duplicated across canonical, graph, lexical, vector and benchmark tables in `tests/test_retrieval_storage_bounds.py` (FR-010, FR-036, SC-008).

## Phase 4 — Build governed memory formation

- [x] [T019] Implement the deterministic structure/event proposal producer by extending `atmem/extract/validation.py`, proposal models and the existing `atmem/memory.py` admission/application path without benchmark labels, application names, question IDs or expected answers (FR-003–FR-010, FR-033).
- [ ] [T020] Extend the existing bounded registered optional model proposal interface with typed proposals, explicit egress checks and fail-closed/unavailable receipts in `atmem/extract/` and the application service (FR-001, FR-003–FR-004, FR-023, FR-037).
- [x] [T021] Implement stable identity, exact duplicate, compatible update, conflict and supersession reconciliation as an additive step in the existing extraction/admission pipeline (FR-011).
- [ ] [T022] Extend `source-capture-v1`, media observation, `EvidenceService.capture`, proposal validation and existing authority admission with immutable ordered source linking and loss/coverage receipts; do not create a second formation, ingest or evidence authority service (FR-001–FR-004, FR-012, FR-051).
- [ ] [T023] Add formation tests proving preservation of exact labels/numbers, negative evidence, invalid premises, before/action/after transitions, ordered conditional procedures and original media/source references in `tests/test_memory_formation.py` (FR-005–FR-012, SC-001).
- [ ] [T024] Add tests proving optional extractor outage preserves canonical evidence, does not create structure, and produces an observable receipt in `tests/test_memory_formation.py` (FR-002–FR-004, FR-012).
- [ ] [T025] Add authority tests proving denied source material cannot influence proposal counts, identities, links, telemetry or future retrieval in `tests/test_memory_formation_authority.py` (FR-001, FR-023).

## Phase 5 — Retrieve by information need

- [x] [T026] Implement deterministic information-need routing for the canonical `exact_fact`, `current_state`, `state_change`, `ordered_task`, `exception_risk`, `rule_application`, `assumption_check` and `relational_synthesis` product needs in `atmem/retrieve/intent.py` (FR-013).
- [x] [T027] Implement bounded subquery decomposition with preserved parent identity and evidence requirements in `atmem/retrieve/intent.py` (FR-014).
- [x] [T028] Implement four product-derived information-need profiles and independent quotas for exact, lexical, semantic, temporal and typed graph nomination in `atmem/retrieve/profiles.py`; runtime code contains no benchmark ability/application labels (FR-005, FR-015–FR-018, FR-033).
- [x] [T029] Replace per-query whole-corpus loading and temporary FTS in `atmem/retrieve/hybrid.py` with persistent store-backed exact/fact/FTS nomination and bounded canonical reloads, then nominate typed units while preserving channel reasons and legacy compatibility (FR-015–FR-018, FR-027, FR-039, FR-047–FR-048, SC-013).
- [x] [T030] Implement exact-value and identifier preservation so fusion cannot discard an otherwise eligible unique exact hit in `atmem/retrieve/hybrid.py` (FR-016).
- [ ] [T031] Implement typed source-linked graph nomination that cannot create standalone factual authority in `atmem/retrieve/hybrid.py` and graph adapters (FR-001, FR-017).
- [ ] [T032] Implement event, observation and validity-time filtering plus current/superseded state selection in `atmem/retrieve/hybrid.py` (FR-018).
- [ ] [T033] Add routing and nomination tests, including conflicting channels, low semantic similarity exact hits and time-corrected facts, in `tests/test_retrieval_intent.py` (FR-013–FR-018).
- [ ] [T034] Add isolation tests proving inaccessible records do not affect channel counts, rankings, timing labels or graph paths in `tests/test_retrieval_authority.py` (FR-001, FR-015–FR-018).

## Phase 6 — Expand evidence and decide sufficiency

- [ ] [T035] Implement bounded adjacency expansion for source neighbors, transitions, procedure branches, rule conditions/exceptions, conflicts and supersession lineage in `atmem/retrieve/expand.py` (FR-019).
- [ ] [T036] Revalidate authority/lifecycle for every traversed and selected node, and record seed/path/budget/reason without leaking rejected paths in `atmem/retrieve/expand.py` (FR-001, FR-019).
- [ ] [T037] Implement complementary source selection and duplicate-paraphrase suppression in `atmem/retrieve/expand.py` (FR-020).
- [x] [T038] Implement deterministic slot coverage for entity, relation/action, polarity, time, transition completeness, ordered steps, applicability, conflicts and freshness in `atmem/retrieve/sufficiency.py` (FR-021).
- [x] [T039] Implement `sufficient`, `partial`, `contradictory`, `stale` and `unsupported` outcomes with evidence IDs, missing slots and safe answer guidance plus the non-strengthening mapping to existing SupportClass values in `atmem/retrieve/sufficiency.py` (FR-022, FR-052).
- [ ] [T040] Add the optional model-assisted sufficiency/reranking proposal interface with authorized candidates only and deterministic evidence revalidation in `atmem/retrieve/sufficiency.py` (FR-023, FR-037).
- [ ] [T041] Add expansion and sufficiency tests for transitions, multi-step procedures, rules/exceptions, conflicts, missing premises and scope attacks in `tests/test_evidence_expansion.py` and `tests/test_retrieval_sufficiency.py` (FR-019–FR-023, SC-002).

## Phase 7 — Assemble and deliver answerable context

- [ ] [T042] Implement Context Package V2 assembly maximizing required-slot coverage, exact-field preservation and source diversity per byte/token while penalizing duplicate paraphrases; preserve authorized original media references and emit structured rule applicability and required/prohibited action constraints in `atmem/retrieve/assemble.py` (FR-024–FR-026, FR-046).
- [ ] [T043] Preserve provenance, chronology, conflicts, uncertainty and insufficiency instructions in the package rather than flattening evidence into an unqualified prose summary in `atmem/retrieve/assemble.py` (FR-024–FR-026).
- [ ] [T044] Add deterministic packing and adversarial reader-use tests in `tests/test_context_assembler_v2.py`, including evidence-present-but-answer-unusable failures (FR-024–FR-027, SC-002).
- [ ] [T045] Extend supported OpenClaw, Hermes, MCP, Pydantic AI and LangChain/LangGraph adapters to serialize the same compact package and action constraints without re-ranking or changing authority in their existing adapter modules (FR-028, FR-041, FR-044, FR-046).
- [ ] [T046] Add golden contract tests proving identical selected IDs, provenance, sufficiency, action constraints and profile identity across MCP and supported hosts in `tests/test_retrieval_adapter_conformance.py` (FR-028, FR-041, FR-044, FR-046, SC-007, SC-015).

## Phase 8 — Shadow activation, diagnostics and rollback

- [ ] [T047] Add one application-service boundary for form, recall, explain, profile and rollback plus disabled-by-default, sampled and budgeted legacy/candidate shadow execution, scoped activation and instant rollback in `atmem/control/manager.py` and `atmem/service/application.py` (FR-039, FR-044, FR-053, SC-007).
- [ ] [T048] Persist content-free stage outcomes, selected IDs/context hashes, latency and optional usage through `retrieval-stage-event-v1`; ensure AtFlows is observational and retrieval works when it is absent in `atmem/control/manager.py` (FR-027, FR-037).
- [ ] [T049] Add guided `retrieval setup/status/explain/activate/rollback` CLI commands with preview, a real product-API verification round trip, plain-language output, machine-readable parity and storage by category in the existing CLI modules (FR-012, FR-027, FR-039–FR-040, FR-045, FR-050).
- [ ] [T050] Extend the AtMem dashboard with active profile, typed formation health, keyset-paginated stage funnel, sufficiency, provenance, storage categories, shadow comparison and rollback controls; serve cached bounded aggregates without whole-store scans in the existing dashboard UI (FR-027, FR-039–FR-040, FR-048, FR-050).
- [ ] [T051] Add browser, CLI and MCP parity tests showing identical authority/profile state, selected IDs, sufficiency, sources, action constraints, rollback and truthful missing-stage evidence in dashboard and MCP test suites (FR-040, FR-044–FR-046, FR-050, SC-007, SC-015).
- [ ] [T052] Add installed OpenClaw and MCP shadow/activate/restart/rollback acceptance tests on Linux, macOS and Windows plus Hermes native tests on Linux/macOS and WSL tests on Windows, including paths with spaces/non-ASCII characters, lock contention, optional services absent and benchmark packages removed in `tests/installed/` (FR-028, FR-041–FR-045, FR-049, SC-007–SC-008, SC-012).
- [ ] [T073] Add bounded-load tests proving quota exhaustion, optional timeouts and retry pressure cannot create unbounded CPU/memory/storage work or silently claim complete formation/support in `tests/test_retrieval_resource_bounds.py` (FR-047, SC-013–SC-014).
- [ ] [T074] Add keyset pagination, aggregate-cache identity/invalidation and query-plan tests for status, explain and dashboard read models in `tests/test_retrieval_diagnostics_performance.py` (FR-048, SC-013).
- [ ] [T075] Add storage-accounting, single-source-copy, idempotent reingestion and per-category growth tests in `tests/test_retrieval_storage_bounds.py` (FR-010, FR-036, FR-047–FR-048, SC-014).
- [ ] [T076] Add an import/dependency gate proving runtime formation/retrieval, CLI, MCP and adapters work from installed artifacts after benchmark modules and corpora are removed in `tests/installed/` (FR-028, FR-044, SC-008, SC-012).
- [ ] [T077] [OPTIONAL COMPANION] Extend AtFlows to ingest `retrieval-stage-event-v1` without memory content and render bounded, paginated aggregates by agent, profile, information need and stage; this work may proceed in parallel and is not on the AtMem retrieval or benchmark critical path. AtFlows failure must not change AtMem behavior (`../atflow` server/dashboard/tests) (FR-027, FR-037, FR-048).
- [ ] [T078] Add mandatory AtFlows-absence tests proving formation, retrieval, explanation and rollback succeed unchanged with AtFlows stopped or incompatible. Put optional cross-repository stage-count/duration/limit/cost compatibility tests under T077; neither path may send protected content (FR-001, FR-027, FR-037, SC-013, SC-015).

## Phase 9 — Add inert benchmark orchestration and analysis

- [x] [T053] Implement the AtMem orchestration client in `research/production_benchmarks/longmemeval_v2.py` and a thin registered adapter in the pinned official checkout's `memory_modules/atmem.py`; the adapter may only losslessly map native ordered episodes into `episode-ingest-v1` and call public product APIs. Add a lint/architecture test rejecting chunking, accessibility-tree filtering, direct store/index access, false source kinds, answer/question metadata and benchmark-specific retrieval branches (FR-028, FR-031, FR-033, FR-044, FR-051). Evidence: pinned checkout `2cc8c5…` registers the copied adapter; `tests/test_official_benchmark_adapters.py` verifies full structured-state and original-media preservation through ordinary product APIs.
- [x] [T054] Implement a product-API-only DolphinBench adapter in `research/production_benchmarks/dolphinbench.py` with three independent persona scopes, ordered history ingestion, formation checkpoint and read-only task phase (FR-028, FR-032–FR-033). Evidence: official five-method contract implemented for alex/morgan/riley with encrypted persona households, immutable checkpoint hashes, durable cost ledger and read-only test-phase behavior.
- [ ] [T055] Implement paired bootstrap/repetition intervals, LAFS, stage attribution, cost, latency and Pareto analysis in `research/production_benchmarks/quality_analysis.py` (FR-027, FR-034–FR-035, SC-003–SC-005, SC-009–SC-011).
- [ ] [T056] Add validators that reject incomplete tiers/personas, mismatched configurations, changed official scorers, post-freeze tuning, missing cases, missing costs/retries, bad hashes and benchmark-local compensation in `atmem/benchmark/contracts.py` and `tests/test_retrieval_quality_gate.py` (FR-028–FR-035, SC-003–SC-008).
- [ ] [T057] Add external-root enforcement and portability tests for Windows, macOS and Linux paths in `tests/test_retrieval_benchmark_storage.py` (FR-036, SC-008).
- [ ] [T058] Run frozen local formation/retrieval fixtures and the pinned Spec 035 LoCoMo legacy/candidate no-regression arm; record BEAM applicability, retain per-case formation, retrieval, sufficiency and reader-use outcomes under the configured external root, and version only the signed summary manifest in `benchmarks/retrieval_quality/manifests/` (FR-054, SC-001–SC-002, SC-006, SC-016).

## Phase 10 — LongMemEval-V2 qualification

- [ ] [T059] Run official Small web/enterprise matched arms for the precommitted development question IDs, using no retrieval, locally rerun official `rag_query_to_slice_notes`, legacy AtMem and typed AtMem with the frozen Qwen3.5-9B reader and GPT-5.2 judge; retain raw external evidence and keep confirmation answers inaccessible (FR-030–FR-031, FR-035, SC-003, SC-005–SC-006).
- [ ] [T060] Run predeclared typed-formation, intent-routing, neighborhood, sufficiency, graph, semantic, lexical and reranking ablations without changing held-out thresholds (FR-034–FR-035, SC-011).
- [ ] [T061] Freeze the selected operating point, run unseen confirmation question IDs on Small, report complete official Small results separately, then run the same confirmation IDs on Medium as a scale test; never call Medium an independent held-out question set (FR-031, FR-035, SC-003, SC-005–SC-006, SC-009).
- [ ] [T062] Produce a stage-attributed LongMemEval report separating not represented, not nominated, insufficient, badly packed, reader missed and judge disagreement in `benchmarks/retrieval_quality/reports/longmemeval-v2-2.3.8.md` (FR-027, FR-043, SC-003, SC-009, SC-011).

## Phase 11 — DolphinBench action qualification

- [ ] [T063] Run no-cost DolphinBench installation, dataset, provider, grader, persona-isolation and product-API plumbing checks without claiming accuracy (FR-028, FR-030, FR-032–FR-033).
- [ ] [T064] Run the complete 600-task matched built-in and AtMem arms using one pinned Hermes/model configuration, immutable memory checkpoints and complete tool/grader/cost/latency evidence (FR-030, FR-032, SC-004–SC-006).
- [ ] [T065] Repeat or bootstrap according to the frozen protocol and produce persona-level paired differences, action accuracy, task cost, latency, failure-stage attribution and Pareto analysis in `benchmarks/retrieval_quality/reports/dolphinbench-2.3.8.md` (SC-004–SC-006, SC-010–SC-011).
- [ ] [T066] Export an official submission package only if its complete validation passes; label anything else development evidence and do not claim leaderboard placement (FR-029–FR-035, FR-043, SC-010).

## Phase 12 — Qualify the installed 2.3.8 candidate

- [ ] [T067] Implement `atmem retrieval qualify --release 2.3.8 --package <path>` with explicit pass/fail/invalid criteria for mandatory SC-001–SC-003, SC-005–SC-008 and SC-012–SC-016, separate research-result reporting, and no implicit paid work in the CLI and `atmem/benchmark/contracts.py`.
- [ ] [T068] Build the exact candidate wheel and bridge artifacts, install them across the declared Linux/macOS/Windows and Python 3.10–3.13 matrix, and run unit, integration, migration, deletion, security, OpenClaw, MCP, build, metadata and deterministic cross-OS packing gates plus native Linux/macOS and Windows-WSL Hermes gates (FR-041–FR-042, FR-049, SC-007, SC-012–SC-016).
- [ ] [T069] Verify fresh install, upgrade from published 2.3.7 and current 2.3.8 beta stores, shadow activation, rollback and benchmark-independent operation from installed artifacts in `tests/installed/` (FR-038–FR-042, SC-007–SC-008).
- [ ] [T070] Update retrieval profile, dependency/egress, migration, storage, diagnostics, benchmark methodology and honest-limit documentation in `docs/` and prepare `docs/releases/v2.3.8.md` only when release preparation is authorized (FR-037–FR-043).
- [ ] [T071] Run the signed qualification index against the exact installed candidate; block final 2.3.8 if any mandatory SC-001–SC-003, SC-005–SC-008 or SC-012–SC-016 gate is missing, invalid or below threshold, and report DolphinBench SC-004 plus SC-009–SC-011 separately as research targets.

## Dependency order and parallel work

- T001–T005 freeze measurement before quality tuning.
- T006–T018 establish contracts and storage before formation or retrieval consumes them.
- T019–T025 establish formation quality before T026–T046 retrieval optimization.
- T026–T034 may proceed in parallel with T035–T041 after contract/storage completion; T042–T046 depend on both.
- T047–T052, T072–T076 and T078 depend on the complete product path and must pass without benchmark code before T053–T066 benchmark execution. T077 is optional companion work and may proceed in parallel; T078 validates absence as well as compatibility.
- T053–T058 begin only after the public product path works; T059–T066 consume that inert rig.
- T067–T071 consume all mandatory product and benchmark evidence. Release mechanics remain subject to `AGENTS.md` and separate release authorization.

## Readiness reconciliation — 2026-09-28

This table reconciles the six review findings with the checklist above. A
partial implementation is not marked complete merely because source exists.

| Finding | Status | Checklist/evidence | Remaining gate |
|---|---|---|---|
| R1 official inert adapters | complete | T053–T054; official LongMem registration plus architecture/product tests; the official state schema, accessibility tree, thought and original media references are preserved without answer metadata | Paid execution remains T059/T063 |
| R2 encrypted typed activation | complete for the benchmark pilot path | `atmem household init/migrate/status`; real SQLCipher bootstrap, canonical/vector encryption, integrity/count/atomic-resume and retained-backup reconciliation tests; Windows permission/fsync paths corrected; exact macOS installed wheel passed retrieval and encrypted-migration smokes; hosted CI run `36385760728` passed the installed encrypted path on Linux, macOS and Windows | PostgreSQL typed migration remains T015–T016 and is not required by either local pilot |
| R3 paid pins | route-qualified for two-arm development pilot; full claim still gated | separate official code/prompt/comparator hashes, DeepInfra reader, loopback-to-Scaleway embedding transport, dated OpenAI judge, sampling, zero retries in both official reader and judge modules, request/token ceilings, public token prices, exact Apple M2 runtime enforcement and $1 HF + $9 OpenAI / $10 total caps frozen in `2.3.8.yaml`; validator checks route evidence `778f3b…22d76`; LongMem uses a single-egress judge proxy, retains the worst-case reservation when provider usage is missing and requires a complete selected-data/media preflight before creating run output; all calls reserve cost durably before egress | HF providers do not attest the served weights commit; official RAG comparator remains paid-disabled until its indexing upper bound is measured; official DolphinBench Azure GPT-5.6 grader is not covered by the OpenAI balance |
| R4 Dolphin development split | complete | frozen 18/600 split: six tasks per official persona, 582 untouched; the development runner selects the allowed IDs before the official execute/grade path creates side-effect markers and labels its receipt as non-official | Complete official score remains T064 |
| R5 task status | reconciled for this milestone | this table distinguishes implemented, locally verified and externally pending work; the post-review local suite is 1,939 passed and 82 skipped; hosted CI run `36385760728` passed all 41 jobs; broader product/release tasks remain unchecked | Re-run the applicable gates after later implementation changes |
| R6 installed/cross-platform | complete for the R1–R6 readiness review | installed-wheel CI spans Python 3.10–3.13 on Linux/macOS/Windows; encrypted installed smoke exercises fresh init, migration and interrupted resume; exact reviewed macOS wheels passed build metadata, dependency, retrieval and encrypted-migration gates (`atmem` SHA-256 `653a21b6…e184`, AtBot SHA-256 `c3afe2a7…cbf6`); hosted CI run `36385760728` passed all 41 jobs, including installed encrypted Linux/macOS/Windows | Broader release qualification remains tracked by T067–T071 and is not claimed complete here |
