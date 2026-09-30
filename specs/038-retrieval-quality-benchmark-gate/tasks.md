# Tasks: Retrieval Quality and Benchmark Release Gate

> **Historical task ledger.** Do not execute this list as a second 2.3.8 engine
> plan. Spec 040 is controlling; its alignment crosswalk preserves the required
> outcomes and records replacements.

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
- [ ] [T021] Implement stable identity, exact duplicate, compatible update, conflict and supersession reconciliation as an additive step in the existing extraction/admission pipeline; the initial implementation is reopened because retained checkpoints proved occurrence collapse and unrelated supersession (FR-011, FR-056).
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
- [ ] [T036] Implement the single shared authority/lifecycle/exclusion eligibility predicate before every candidate reload, adjacency/related traversal and global lookup plus final revalidation; prove ineligible content cannot affect selected evidence, sufficiency, paths, budgets, diagnostics or timing labels, and record authorized seed/path/budget/reason without leaking rejected paths in stores and `atmem/retrieve/expand.py` (FR-001, FR-019, FR-058).
- [ ] [T037] Implement complementary source selection and duplicate-paraphrase suppression in `atmem/retrieve/expand.py` (FR-020).
- [ ] [T038] Implement deterministic query-bound obligation coverage for entity, relation/action, polarity, time, transition completeness, ordered steps, applicability, conflicts and freshness in `atmem/retrieve/sufficiency.py`; the initial generic slot implementation is reopened because wrong-entity/wrong-relation evidence can pass (FR-021, FR-059).
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

- [ ] [T059] After the Phase 13 authority, formation, evidence and reader-finalization prerequisites pass, run official Small web/enterprise matched arms for the precommitted development question IDs, using no retrieval, locally rerun official `rag_query_to_slice_notes`, legacy AtMem and typed AtMem with the frozen Qwen3.5-9B reader and GPT-5.2 judge; retain raw external evidence and keep confirmation answers inaccessible (FR-030–FR-031, FR-035, FR-061, SC-003, SC-005–SC-006, SC-021).
- [ ] [T060] Run predeclared typed-formation, intent-routing, neighborhood, sufficiency, graph, semantic, lexical and reranking ablations without changing held-out thresholds (FR-034–FR-035, SC-011).
- [ ] [T061] After the Phase 13 authority, formation, evidence and reader-finalization prerequisites pass, freeze the selected operating point, run unseen confirmation question IDs on Small, report complete official Small results separately, then run the same confirmation IDs on Medium as a scale test; never call Medium an independent held-out question set (FR-031, FR-035, FR-061, SC-003, SC-005–SC-006, SC-009, SC-021).
- [ ] [T062] Produce a stage-attributed LongMemEval report separating not represented, not nominated, insufficient, badly packed, reader missed and judge disagreement in `benchmarks/retrieval_quality/reports/longmemeval-v2-2.3.8.md` (FR-027, FR-043, SC-003, SC-009, SC-011).

## Phase 11 — DolphinBench action qualification

- [ ] [T063] Run no-cost DolphinBench installation, dataset, provider, grader, persona-isolation and product-API plumbing checks without claiming accuracy (FR-028, FR-030, FR-032–FR-033).
- [ ] [T064] After the Dolphin-specific Phase 13 formation-readiness and reader/agent/grader finalization prerequisites pass, run the complete 600-task matched built-in and AtMem arms using one pinned Hermes/model configuration, immutable memory checkpoints and complete tool/grader/cost/latency evidence (FR-030, FR-032, FR-061, SC-004–SC-006, SC-021).
- [ ] [T065] Repeat or bootstrap according to the frozen protocol and produce persona-level paired differences, action accuracy, task cost, latency, failure-stage attribution and Pareto analysis in `benchmarks/retrieval_quality/reports/dolphinbench-2.3.8.md` (SC-004–SC-006, SC-010–SC-011).
- [ ] [T066] Export an official submission package only if its complete validation passes; label anything else development evidence and do not claim leaderboard placement (FR-029–FR-035, FR-043, SC-010).

## Phase 12 — Qualify the installed 2.3.8 candidate

- [ ] [T067] Implement `atmem retrieval qualify --release 2.3.8 --package <path>` with explicit pass/fail/invalid criteria for mandatory SC-001–SC-003, SC-005–SC-008 and SC-012–SC-021, separate research-result reporting, and no implicit paid work in the CLI and `atmem/benchmark/contracts.py`; reject missing, failing, stale or differently built evidence (FR-061).
- [ ] [T068] Build the exact candidate wheel and bridge artifacts, install them across the declared Linux/macOS/Windows and Python 3.10–3.13 matrix, and run unit, integration, migration, deletion, security, OpenClaw, MCP, build, metadata and deterministic cross-OS packing gates plus native Linux/macOS and Windows-WSL Hermes gates (FR-041–FR-042, FR-049, SC-007, SC-012–SC-016).
- [ ] [T069] Verify fresh install, upgrade from published 2.3.7 and current 2.3.8 beta stores, shadow activation, rollback and benchmark-independent operation from installed artifacts in `tests/installed/` (FR-038–FR-042, SC-007–SC-008).
- [ ] [T070] Update retrieval profile, dependency/egress, migration, storage, diagnostics, benchmark methodology and honest-limit documentation in `docs/` and prepare `docs/releases/v2.3.8.md` only when release preparation is authorized (FR-037–FR-043).
- [ ] [T071] Run the signed qualification index against the exact installed candidate; block final 2.3.8 if any mandatory SC-001–SC-003, SC-005–SC-008 or SC-012–SC-021 gate is missing, invalid, stale, built from another candidate or below threshold, and report DolphinBench SC-004 plus SC-009–SC-011 separately as research targets.

## Dependency order and parallel work

- T001–T005 freeze measurement before quality tuning.
- T006–T018 establish contracts and storage before formation or retrieval consumes them.
- T019–T025 establish formation quality before T026–T046 retrieval optimization.
- T026–T034 may proceed in parallel with T035–T041 after contract/storage completion; T042–T046 depend on both.
- T047–T052, T072–T076 and T078 depend on the complete product path and must pass without benchmark code before T053–T066 benchmark execution. T077 is optional companion work and may proceed in parallel; T078 validates absence as well as compatibility.
- T053–T058 begin only after the public product path works; T059–T066 consume that inert rig.
- T067–T071 consume all mandatory product and benchmark evidence. Release mechanics remain subject to `AGENTS.md` and separate release authorization.

## Phase 13 — Review-driven formation, identity and evidence repair

- [ ] [T080] Freeze the evaluator-owned development annotation schema and scoring code outside product/runtime imports, then add synthetic benchmark-neutral fixtures—copying no benchmark text, URL or screenshot bytes—for structured-snapshot negation rejection, cross-episode URL/state-key supersession, discriminator truncation, punctuation-only/C++-versus-C#, non-Latin and empty-after-normalization collisions, duplicate occurrence provenance loss, query-insensitive sufficiency, rank loss after typed reload, post-sufficiency overpacking and media outside the reader budget. Cover answerable, explicit-negative and unsupported/abstention cases, alternative sufficient sets, fixed coordinates and gold-change noninterference in `tests/fixtures/retrieval-quality/` and focused tests (FR-033, FR-055–FR-060, SC-017–SC-020).
- [ ] [T081] Change structured-state formation and validation to ground each proposal in its supporting field or bounded span so unrelated negation cannot reject or invert faithful state, while actual unsupported polarity still fails closed in `atmem/extract/formation.py` and `atmem/extract/validation.py` (FR-009, FR-055, SC-001, SC-017).
- [ ] [T082] Introduce versioned RFC-8785/NFC source and occurrence identity over authority scope/episode/event/part/fragment separately from durable-fact identity, remove lossy normalization/truncation, preserve repeated occurrence provenance without copying source bytes, and add encrypted old-to-new mappings that retain exclusions, tombstones, quarantine, deletion and ambiguous legacy state. Add published 2.3.x/beta upgrade fixtures, SQLCipher stolen-copy semantic scans, crash at every migration checkpoint, plaintext-safe rollback, scope-local dedup tests, forget-one-of-N/forget-last tests and cross-scope dedup refusal across contracts, `atmem/extract/`, SQLite/PostgreSQL and deletion/migration suites (FR-002, FR-011, FR-038, FR-056, SC-014, SC-017).
- [ ] [T083] Restrict reconciliation supersession to explicit compatible durable-fact corrections or temporal transitions; prevent URL, source-position, chunk-index and ingestion-order coincidence from superseding independent observations; never blanket-reactivate legacy rows; expose authorized/audited ambiguous-row review outcomes through product state; and add in-order/out-of-order correction, ambiguous-legacy, review and authorized historical-query tests in `atmem/memory.py`, CLI and dashboard contracts (FR-011, FR-018, FR-040, FR-056–FR-057, SC-017–SC-018).
- [ ] [T084] Make formation budget exhaustion resumable by exact source position, distinguish processing completion/representation coverage/retrieval readiness, persist receipt consumption, and prove order-independent resume. Cover oversized parts, mid-generation/admission exhaustion, crash before receipt persistence, budget changes, repeated resume, LongMem/Dolphin adapters and ordinary product callers refusing unfinished checkpoints in contracts, `atmem/memory.py` and stores (FR-012, FR-047, FR-057, SC-018).
- [ ] [T085] Remove per-proposal full active-record context loading by using bounded fact/identity lookups and record formation CPU, memory and deadline behavior in `atmem/extract/context.py`, `atmem/memory.py` and stores (FR-047–FR-048, FR-057, SC-013, SC-018).
- [ ] [T086] Define and propagate a versioned obligation contract with entity/relation/action, polarity, temporal target, applicability, alternatives and unresolved interpretation; preserve it with candidate rank, channel scores and occurrence/episode identity through public request contracts, intent routing, typed canonical reload and expansion in `atmem/contracts/`, `atmem/memory.py`, stores and retrieval (FR-014–FR-015, FR-019, FR-058–FR-059, SC-002, SC-019).
- [ ] [T087] Replace generic non-empty-slot sufficiency with obligation-bound entity/relation/polarity/time/applicability/order support and bounded conflict/current-validity checks; withhold unresolved language and test wrong-entity/relation, compound, historical/current and legitimate cross-episode cases in `atmem/retrieve/sufficiency.py` (FR-021–FR-022, FR-059, SC-002, SC-019).
- [ ] [T088] Verify the T036 shared eligibility predicate on adjacency, related-record and global escape paths, then make expansion requirement-driven and episode-coherent with a bounded global exact-evidence escape path that preserves alternatives and legitimate cross-episode support in stores and `atmem/retrieve/expand.py` (FR-001, FR-018–FR-020, FR-058–FR-059, SC-002, SC-019).
- [ ] [T089] Stop complementary packing only after query-conditioned sufficiency and conflict checks, preserve retrieval priority, and serialize all procedure prerequisites, conditions, completion evidence and failures in `atmem/retrieve/assemble.py` (FR-024–FR-026, FR-059–FR-060, SC-019–SC-020).
- [ ] [T090] After T012 and T022 retain protected original media, add a host-neutral total-input budget contract and enforce frozen 4K/8K/16K profiles across product packing, adapter serialization and final request validation. Pin tokenizer/processor, chat template, image policy, overhead and output allowance; deduplicate media by protected evidence identity; require encryption-at-rest, privilege-gated decryption, stolen-copy image-signature scanning and dead-agent reconstruction with the source directory removed; cover media-only, missing-source-directory, serialization expansion and required-set-too-large cases (FR-002, FR-025–FR-027, FR-060, SC-008, SC-020).
- [ ] [T091] After T080–T085, rebuild and independently migrate a copy of each retained development checkpoint in place; require the authorized historical/current sets to agree except for explicitly queued ambiguity. Gate formation availability at annotated answer-bearing spans for at least 13/14 development questions, occurrence/lifecycle correctness, zero complete receipts with unprocessed positions and receipt completeness before retrieval tuning; retain controlled original/admission/identity/combined comparison artifacts and checksum-backed diagnosis under the external root (FR-027, FR-036, FR-055–FR-057, SC-017–SC-019).
- [ ] [T092] After T086–T090, run evaluator-owned reader-free stage attribution for the frozen fourteen-question LongMemEval-V2 development set, including source representation, authorized availability, nomination, expansion and packed evidence coverage/precision. Reader use is excluded from this gate and annotations never enter product imports (FR-027–FR-035, SC-019–SC-020).
- [ ] [T093] Implement the frozen per-configuration finalization-gate manifests and validators, including candidate/checkpoint/provider/model/processor/prompt/proxy/concurrency/budget binding, stale/bypass/length-with-content/reasoning-only/malformed/missing-usage/cleanup-failure tests and cumulative cost authorization independent of a changing protocol digest. Then run focused authority/exclusion, protected-media disaster reconstruction, migration/rollback/deletion, performance, product-API and installed-artifact regression suites; prove gold annotation noninterference and record an explicit SC-017–SC-020 acceptance matrix under the external root (FR-001–FR-061, SC-017–SC-021).
- [ ] [T094] Only after T092 passes SC-019/SC-020, T093 passes its acceptance matrix and T108 completes the reference differential, obtain a post-implementation independent Claude review (or an equivalently capable independent reviewer if unavailable) of the diff, tests, migration, FR-061–FR-063 validators and evidence; resolve every critical/high correctness or constitutional finding and record reviewer identity, artifact hashes, disposition and accepted lower-severity limitations (FR-001–FR-063, SC-017–SC-022).
- [ ] [T095] Commit and push the exact reviewed candidate, then run the separately budgeted frozen twelve-call LongMemEval reader/judge finalization gate bound to that commit/checkpoint/provider/model/processor/prompt/proxy/configuration. Validate every scored response, cancel siblings immediately on failure, preserve durable cost/cleanup evidence and block T059 on stale or failed evidence (FR-061, SC-021).
- [ ] [T096] After T095 and SC-022 pass, run the frozen three-percent LongMemEval-V2 development sample through the official inert adapter and report accuracy, stage failures, p50/p95 latency, tokens, resource use and reconciled cost without release or leaderboard claims (FR-028–FR-036, FR-061–FR-063, SC-006, SC-021–SC-022).
- [ ] [T097] After SC-022 passes, independently preflight and authorize DolphinBench credentials/cost, run a frozen Hermes/model/grader finalization gate bound to the reviewed candidate and immutable persona checkpoints, then run the frozen 18/600 development sample only if that gate passes; report action score, persona/stage failures, p50/p95 latency, tokens, resource use and reconciled cost without release or leaderboard claims (FR-028–FR-036, FR-061–FR-063, SC-004, SC-006, SC-021–SC-022).
- [x] [T098] Resolve the 2026-09-30 Astra ultra adversarial review with
  regression coverage for all thirteen findings: trust-safe explicit
  supersession, exact polarity grounding, full-slot reconciliation,
  relation-complete routing, replay readiness, configuration-bound probe
  artifacts, installed-artifact hashing, completed Dolphin turns, end-to-end
  reader byte enforcement, temporal-first historical nomination and pre-read
  resumable-media budgets. Evidence: the focused formation/retrieval/
  adapter/protocol suite passes 128 tests; repository-wide and independent
  rereview gates must still pass before commit.

## Phase 14 — Reference parity and bounded source navigation

- [ ] [T099] Pin source revisions, licenses and configuration manifests for
  AgentRunbook-C/C V2, AgentRunbook-R and Mem0 under the external benchmark
  root; add small evaluator-only adapters and a neutral result contract under
  `research/reference_parity/` without importing reference code from `atmem/`
  runtime modules (FR-028, FR-033, FR-063).
- [ ] [T100] Implement the authority-checked `EvidenceNavigator` manifest,
  search, inspect, follow and submit operations in `atmem/retrieve/navigator.py`
  with one total-input/operation/time budget, exact inspection receipts and
  final canonical revalidation (FR-001–FR-002, FR-019, FR-025, FR-060, FR-062).
- [ ] [T101] Add governed `retrieval_hint` derivatives and lifecycle handling
  in `atmem/retrieve/hints.py`; prove hints can change a search plan but cannot
  satisfy sufficiency, enter direct-support context, cross scope or survive
  revocation/expiry (FR-001–FR-004, FR-021–FR-023, FR-038, FR-062).
- [ ] [T102] Add the three operating points `typed-fast`,
  `typed-navigate-deterministic` and `typed-navigate-agentic`, with explicit
  trigger reasons, limits, egress/model identity, fallback and per-stage
  latency/token/cost receipts in the public product service (FR-027, FR-037,
  FR-044, FR-053, FR-062).
- [ ] [T103] Freeze a benchmark-neutral reference-capability corpus and tests
  covering exact state, transition, ordered procedure, gotcha, invalid premise,
  personal/organizational action rule, correction, conflict, duplicate
  occurrence and private/shared-agent scope. Bind every expected result to
  source ranges and action-constraint fields, not prose answers (FR-033,
  FR-063, SC-001–SC-002, SC-022).
- [ ] [T104] Capture one pinned set of raw model outputs for the reference
  systems and AtMem, store heavy cassettes externally, and add deterministic
  replay tests. Clearly label replay as orchestration regression evidence, not
  a live quality score (FR-030, FR-036, FR-063).
- [ ] [T105] Implement reader-free differential scoring for source
  representation, minimal-evidence-set recall/precision, sufficiency
  calibration, exact action constraints, context bytes/tokens, p50/p95 latency,
  storage amplification and policy/scope errors. Report fast-only and
  fast-plus-navigation separately (FR-027, FR-034, FR-063, SC-022).
- [ ] [T106] Extend the frozen evaluator-owned Dolphin development annotations
  with memory-dependent rule, applicability, required/prohibited action and
  exact tool-argument obligations, without exposing them to runtime or adapter
  imports (FR-032–FR-033, FR-046, FR-063, SC-022).
- [ ] [T107] Run the no-model unit/cassette layers and reader-free LongMem and
  Dolphin preflight. Stop unless SC-001/SC-002/SC-019/SC-020 and the
  deterministic clauses of SC-022 pass; retain a signed failure-stage report
  rather than starting a live differential or paid sample (FR-063, SC-022).
- [ ] [T108] Run one small pinned model-backed differential development slice
  across AtMem and the applicable public reference paths, using deterministic
  evidence/action scoring and no answer judge by default. Only if this result is
  promising proceed to the separate finalization probes and 3% runs in
  T095–T097 (FR-030, FR-034, FR-063, SC-011, SC-022).

T080 plus T012/T022 freeze annotations and protected evidence. T081–T085 repair
formation/identity, then T091 must pass before T086–T090 retrieval work. T036
and its shared eligibility predicate are prerequisites of T086–T090. T092 and
T093 precede independent review; T094 precedes the reviewed commit/push and
configuration-specific finalization gate in T095. T096 and T097 are independent
scored development runs. A paid run
must stop immediately if the finalization gate, provider pin, immutable split,
cost reservation or official adapter validation fails.
T099–T106 may be built alongside the repair work after their contracts freeze.
T107 depends on T091–T093 and T099–T106. T108 depends on T107, completes SC-022
and precedes the independent review in T094. It is the final quality sanity
check before T095–T097 and does not replace configuration-specific serving
finalization.
Any code, prompt, processor or configuration change after T094 invalidates the
review and T095 evidence and requires a delta review plus a new finalization
gate before either scored sample.

## Readiness reconciliation — 2026-09-28

This table reconciles the six review findings with the checklist above. A
partial implementation is not marked complete merely because source exists.

| Finding | Status | Checklist/evidence | Remaining gate |
|---|---|---|---|
| R1 official inert adapters | complete | T053–T054; official LongMem registration plus architecture/product tests; the official state schema, accessibility tree, thought and original media references are preserved without answer metadata | Scored LongMem execution remains T059; scored Dolphin execution remains T064 |
| R2 encrypted typed activation | complete for the benchmark pilot path | `atmem household init/migrate/status`; real SQLCipher bootstrap, canonical/vector encryption, integrity/count/atomic-resume and retained-backup reconciliation tests; Windows permission/fsync paths corrected; the cutover now removes checkpointed plaintext WAL/SHM files before an encrypted database takes the destination name; exact installed-wheel suites passed locally and hosted CI run `36389994972` passed the installed encrypted path on Linux, macOS and Windows | PostgreSQL typed migration remains T015–T016 and is not required by either local pilot |
| R3 paid pins | implementation complete; incomplete development run retained | separate official code/prompt/comparator hashes; exact official runtime package versions; temporary authenticated Qwen3.5-9B Runpod Secure L40S at the pinned repository revision, loopback SSE-to-JSON reader facade, loopback-to-Scaleway embedding transport, dated OpenAI judge, sampling, zero provider-request retries, request/token ceilings, exact Apple M2 enforcement and $2.20 reader runtime + $8.50 OpenAI / $10.70 total caps frozen in `2.3.8.yaml`; validator checks route evidence `d1f9c0…cfe1`; the full official harness is imported before egress; the batch runner durably reserves pod runtime, gates OpenAI judging, automatically terminates the pod before judging and records a content-free runtime receipt | The 2026-09-28 run completed 7/14 paired questions before Qwen returned reasoning without final answer text; the harness rejected it, OpenAI judging remained at zero calls, and the pod was deleted. Partial typed/no-retrieval results were 1/7 and 0/7 and are explicitly non-comparable development evidence in `benchmarks/retrieval_quality/reports/longmemeval-v2-development-pilot-20260928.md`. Aggregate retained Runpod spend was $1.146824. No benchmark score is claimed until the complete 28-case pilot finishes. Configured revision is not served-weight attestation; official RAG remains disabled until its indexing upper bound is measured; official DolphinBench Azure GPT-5.6 grader is not covered by the OpenAI balance |
| R4 Dolphin development split | complete | frozen 18/600 split: six tasks per official persona, 582 untouched; the development runner selects the allowed IDs before the official execute/grade path creates side-effect markers and labels its receipt as non-official | Complete official score remains T064 |
| R5 task status | reconciled for this milestone | this table distinguishes implemented, locally verified and externally pending work; after the Runpod pilot changes the native macOS suite is 1,934 passed and 96 skipped, including the SSE facade and fail-fast cancellation tests; hosted CI run `36389994972` passed all 41 jobs before these later changes; stopped or incomplete paid attempts are recorded as development evidence rather than benchmark results; broader product/release tasks remain unchecked | Hosted CI must be rerun for the new commit; do not treat the earlier workflow as validation of these later changes |
| R6 installed/cross-platform | complete for the R1–R6 readiness review | installed-wheel CI spans Python 3.10–3.13 on Linux/macOS/Windows; encrypted installed smoke exercises fresh init, migration and interrupted resume; the final macOS AtMem wheel passed build metadata, dependency, retrieval and encrypted-migration gates (SHA-256 `57a70663…9740a4`); hosted CI run `36389994972` passed all 41 jobs, including installed encrypted Linux/macOS/Windows | Broader release qualification remains tracked by T067–T071 and is not claimed complete here |

### External evidence retained on MEM

- Final installed artifact and 68-package environment lock:
  `atmem-benchmarks/installed-artifacts/macos/r1-r6-20260928-final-1b35b07/`.
- Successful exact-request Together qualification (content-free receipt):
  `atmem-benchmarks/runs/provider-probes/qwen35-9b-together-20260928.json`.
- Dedicated endpoint qualification evidence and the disclosed receipt collision:
  `atmem-benchmarks/runs/provider-probes/qwen35-9b-dedicated-20260928.json`
  plus `provider-route-probe-v1.json`; paid batch outputs use unique directories.
- DeepInfra and Together stopped-run evidence, including durable reservations:
  `atmem-benchmarks/runs/longmem-3pct-28ea04f-20260928/` and
  `atmem-benchmarks/runs/longmem-3pct-1b35b07-20260928/`.
- Shared cost ledgers are retained below `atmem-benchmarks/runs/cost-ledgers/`;
  ambiguous reservations were not rewritten as zero-cost completions.
