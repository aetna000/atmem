# AtMem Code: dependency-ordered tasks

**Status:** Implementation checklist, 2026-10-14. Completed tasks have executable verification; unchecked tasks have explicit remaining gates in [implementation-status.md](implementation-status.md). Phase 9 remains deferred.
**Governing artifacts:** [spec.md](spec.md), [plan.md](plan.md), [market-research.md](market-research.md), `.specify/memory/constitution.md`.
**Release target:** AtMem Code after the published 2.3.8 baseline; a new candidate must not reuse or move the historical `v2.3.9b1` Laya tag.

**Pending expansion:** T043–T060 implement FR-017–FR-028 / SC-008–SC-013.
The historical phase 0–8 completion evidence excludes these tasks. New
completion annotations name separate 2026-10-17 verification; unchecked runtime,
installed-platform and human-study gates remain open.

The owner requested implementation of phases 0–8, including provider routing and graph. These remain opt-in user features, not omitted development phases. Phase 9 benchmark and release work is deferred by the owner's later instruction. A named agent target is not an automatic integration until its installed-version probe passes.

## Phase 0 — Resolve the contract and freeze evaluation

- [x] [T001] Record decisions on full-fidelity default, protected secret evidence, external-provider authority, cross-machine sharing and the meaning of “governance off” in `specs/042-atmem-code/clarifications.md`; amend `spec.md` and `plan.md` to remove remaining constitutional conflicts before runtime work.
- [x] [T002] Add a Constitution Check and a requirement-to-gate crosswalk in `specs/042-atmem-code/plan.md`, including the release-blocking versus experimental subset and the exact supported-host claim rules.
- [x] [T003] Define per-host event, injection, acknowledgement, trust, version and OS capabilities for Muse Code, Claude Code, Grok CLI, GitHub Copilot CLI and Codex in `specs/042-atmem-code/host-capabilities.md`; assess Copilot editor/cloud separately.
- [x] [T004] Define the VibeMemBench protocol, source-availability gate, chronological boundary, baselines, budget, repetition policy and raw-result schema in `specs/042-atmem-code/benchmark-protocol.md`; defer exact corpus license, task IDs and hashes until upstream artifacts exist, and prohibit oracle-experience injection into product arms.
- [x] [T005] Correct the 2.3.8 publication baseline, AtMem Code track and historical Laya prerelease treatment in `docs/release-roadmap.md`; leave release version constants unchanged until preparation.

## Phase 1 — Safe memory intake foundation

- [x] [T006] Reproduce the raw-episode-before-screening and `interpreted_fact` bypasses with fake credentials in `tests/test_memory_secret_boundary.py` against the 2.3.8 `atmem/memory.py` path.
- [x] [T007] Repair pre-write screening at the `atmem/memory.py` semantic admission boundary so recognized secrets do not reach raw episodes or canonical memory; preserve the separate constitution-compliant encrypted flight-evidence service and document residual coverage in `specs/042-atmem-code/phase1-security-report.md`.
- [x] [T008] Add Hermes, existing `remember()`, false-positive/false-negative fixture disclosure and disk-persistence regression gates in `tests/test_memory_secret_boundary.py` and `tests/test_hermes_install.py`; verify existing protected evidence and disclose untested export/egress surfaces in `specs/042-atmem-code/phase1-security-report.md` for later phase gates.

## Phase 2 — One host-neutral Code service and scope

- [x] [T009] Specify versioned observation, formation, context, exposure, deletion and error contracts in `atmem/code/contracts.py`, with matching schema and compatibility tests in `tests/test_code_contracts.py`.
- [x] [T010] Implement authenticated local intake, session binding, idempotency and bounded queues in `atmem/code/service.py`; reject unauthenticated or cross-scope events in `tests/test_code_service.py`.
- [x] [T011] Implement stable project identity, explicit clone/remote rebinding, profile/agent-private lanes and migration in `atmem/code/identity.py` and `atmem/store/sqlite.py`; test identity collision and scope isolation in `tests/test_code_identity.py`.
- [x] [T012] Implement safe coding-memory formation from observed user intent, task outcomes, source and Git revision in `atmem/code/formation.py`; distinguish supported project facts from transient summaries and test correction/supersession in `tests/test_code_formation.py`. Task outcomes remain evidence-only without independent attestation; this is a deliberate non-promotion result, not a positive formation claim.

## Phase 3 — Guided setup and agent adapters

- [x] [T013] Add Code as a flavour of normal AtMem onboarding, plus `atmem code setup/status/doctor/enable/disable/uninstall`, in `atmem/cli.py` and `atmem/code/install.py`; installed package alone must remain non-influencing. Disable pauses only automatic capture/injection; uninstall alone restores host configuration. `atmem init --flavour code` only directs the user to the non-influencing host preview; host-specific automatic enablement remains gated by T015–T020.
- [x] [T014] Implement a host-adapter interface and reversible configuration snapshot/probe contract in `atmem/code/adapters/base.py`; test failed install, exact restore and host upgrades in `tests/test_code_install.py` and `tests/test_code_adapter_base.py`.
- [ ] [T015] Implement and installed-version test the Muse Code adapter in `atmem/code/adapters/muse.py` and `tests/test_code_muse.py`.
- [x] [T016] Implement and installed-version test the Claude Code adapter in `atmem/code/adapters/claude.py` and `tests/test_code_claude.py`.
- [ ] [T017] Implement and installed-version test the Grok CLI adapter in `atmem/code/adapters/grok.py` and `tests/test_code_grok.py`.
- [x] [T018] Implement and installed-version test the GitHub Copilot CLI adapter in `atmem/code/adapters/copilot.py` and `tests/test_code_copilot.py`; qualified for CLI 1.0.98 on macOS and Windows 11. Native executable/arguments, Windows npm launcher and environment support, bounded journal-backed invocation identity, normal offline activation, new/resumed-session recall, pause/resume and exact owner-hook restoration pass; see `copilot-cli-probe.md`. Windows shared/exclusive process locks and migration exclusion are regression-tested. No editor/cloud or full-fidelity evidence claim.
- [ ] [T019] Implement and installed-version test the Codex adapter in `atmem/code/adapters/codex.py` and `tests/test_code_codex.py`.
- [x] [T020] Publish tested host/OS/version support and manual-only fallbacks in `specs/042-atmem-code/host-capabilities.md`; require the actual hook and context-submission probe before an automatic label.

## Phase 4 — Automatic formation, recall and cross-agent use

- [x] [T021] Wire enabled host-turn events to one formation path in `atmem/code/service.py`; prove no agent-initiated `remember` call is needed in `tests/test_code_automatic.py`.
- [x] [T022] Build bounded, source-linked, scope-authorized context packs in `atmem/code/context.py`; test stale-state exclusion, truncation and timeout behavior in `tests/test_code_context.py`.
- [x] [T023] Record submitted bytes, host acknowledgement and independently observed model input as distinct assurance levels in `atmem/code/receipts.py`; test no overclaim of model delivery in `tests/test_code_receipts.py`.
- [x] [T024] Run paired new-session and cross-agent handoffs for supported hosts, including private-lane isolation and idempotent replay. `tests/test_code_copilot.py` now verifies normal Copilot/Claude onboarding and bidirectional capture → actual model-boundary recall on macOS, without activation bypasses. Shared-boundary private-lane/replay tests remain in `tests/integration/test_code_handoff.py` and `tests/test_code_copilot_events.py`. Other hosts remain unqualified under their own adapter tasks.

  Actual installed Codex capture → Claude model-boundary recall is additionally tested in `tests/test_code_codex.py`. Codex uses an isolated, explicitly vetted fixture trust flag in this test; this does not close normal Codex onboarding T019. Private-lane and replay checks use the shared production hook boundary in the integration tests.

- [ ] [T042] Close the full-fidelity default evidence acceptance gate (FR-003/FR-008) for a host that exposes all required boundaries. Current Code hooks explicitly report partial coverage and `not_reconstructable`; they do not provide complete model/tool/media flight recording. Blocked B05; do not inherit the separate Agent Black Box claim.

## Phase 5 — Search, settings and scoped clearing

- [x] [T025] Add `atmem code search`, inspect, correct, forget, config and clear/preview commands in `atmem/cli.py`, with machine-readable output and authorization tests in `tests/test_code_cli.py`.
- [x] [T026] Add one Coding Memory dashboard view and the same supported settings in `atmem/control/assets/` and `atmem/control/web.py`; test CLI/dashboard state parity, source inspection and access control in `tests/test_code_dashboard.py`.
- [x] [T027] Implement exact project/profile/agent deletion preview and verification across canonical and registered derived stores in `atmem/code/deletion.py`; test adjacent-scope preservation and partial remote-provider outcomes in `tests/test_code_deletion.py`.

## Phase 6 — External context providers

- [x] [T028] Specify route selection, query authorization, external egress, provider authority mode, response validation and failure policy in `atmem/code/providers.py` and `specs/042-atmem-code/provider-contract.md`.
- [x] [T029] Wire configured local RAG and Mem0 routes through the existing delegated-context boundary in `atmem/code/providers.py`; test native fallback, withholding, provenance and no unintended egress in `tests/test_code_providers.py`.
- [x] [T030] Expose route configuration and provider status in both `atmem/cli.py` and `atmem/control/assets/`; test that a request tag cannot grant scope or network authority in `tests/test_code_provider_settings.py`.

## Phase 7 — Optional code graph

- [x] [T031] Build an optional, encrypted-at-rest derived symbol/import/reference index with versioned source links in `atmem/code/graph.py`; keep canonical memory independent of the parser.
- [x] [T032] Invalidate or rebuild graph slices after edits, branch changes and imports in `atmem/code/graph.py`; test unsupported-language fallback and stale-result labelling in `tests/test_code_graph.py`.
- [ ] [T033] Compare graph nomination against ordinary file exploration and a strong repository-map control in `specs/042-atmem-code/benchmark-protocol.md`; measure complete agent tokens, quality and indexing overhead, not query bytes alone.

  Blocked B06 by the owner's exclusion of phase 9 task-outcome evaluation. Structure, freshness and automatic nomination are tested; no token-saving or task-quality claim is made.

## Phase 8 — Project portability and product parity

- [x] [T034] Implement an encrypted, integrity-checked, project-scoped export manifest and bundle in `atmem/code/portable.py`; exclude machine credentials and host hook configuration.
- [x] [T035] Implement authorized import preview, explicit identity rebinding, collision handling and derived-index rebuild in `atmem/code/portable.py`; test fresh-install search/lifecycle parity and cross-scope denial in `tests/test_code_portable.py`.
- [x] [T036] Run installed-wheel onboarding, CLI/dashboard parity and bundle round-trip journeys on macOS, Windows and Linux where supported in `tests/integration/test_code_product_journey.py`; record untested host/OS combinations as unsupported.

## Phase 9 — Independent task evaluation and release gate (deferred; do not run in this request)

- [ ] [T037] Implement VibeMemBench and unfiltered real-issue adapters in `research/atmem_code_bench/` with frozen manifests, separate development and held-out runs, chronological leakage checks and preserved grader outputs.
- [ ] [T038] Run matched memory-off, native, AtMem memory, graph and combined arms plus technically comparable competing-memory/structural controls in `research/atmem_code_bench/`; keep host/model versions, prior histories and budgets fixed and report results per host.
- [ ] [T039] Publish raw receipts and a report of executable resolution, paired uncertainty, total tokens/cost, p50/p95 latency, throughput, errors, stale/wrong-context harm, capture and indexing overhead in `research/atmem_code_bench/results/`; mark partial or unverified runs as non-production evidence.
- [ ] [T040] Perform SpecKit consistency analysis, constitution check, security, migration, installed-artifact and cross-platform gates in `specs/042-atmem-code/`; close or explicitly defer every release-blocking task before preparation.
- [ ] [T041] Prepare the actual release candidate under `docs/release-coordination.md`: choose an unused version, align all package/bridge pins, add `docs/releases/v<VERSION>.md`, update `docs/website/manifest.json`, check website docs and prepare the separate owner-reviewed website PR. Do not tag until clean gates pass; verify workflows, registries and live-website state separately.

## Pending CK expansion — contracts and upstream incorporation

- [x] [T043] Freeze a source/capability/license register in `specs/042-atmem-code/knowledge-capabilities.md`, including pinned Cognee/Enola revisions, supported cells, upstream tests, reuse decisions and retained notices; no unqualified parity claim. FR-017; SC-008. Register and reproducible source import verified 2026-10-17; dependency SBOM/platform clearance remain explicit later gates.
- [x] [T044] Implement versioned snapshot, structural object/relation, coding-attempt proposal, execution-receipt, applicability and capability-receipt contracts in `atmem/knowledge/contracts.py`; map into existing authority without a second admission service. Depends T043. FR-017, FR-021–FR-023, FR-027–FR-028; SC-009, SC-010, SC-013. Closed round trips, malformed identities, bounds and Python 3.10 grammar tests pass; proposals use existing typed admission, not a new canonical authority.
- [ ] [T045] Incorporate/adapt the audited extractor and upstream loader/mapping tests into `atmem/knowledge/code/extractor.py` and `mapping.py`, retaining license/modification records under `third_party/`; preserve the limited AST fallback label. Depends T043, T044. FR-017, FR-018; SC-008.
- [ ] [T046] Implement bounded authorized worker/job handling in `atmem/knowledge/worker.py` and extraction determinism/source/secret/path/egress tests in `tests/test_knowledge_extraction.py`. Depends T045. FR-018, FR-026; SC-008, SC-012.
- [ ] [T047] Implement encrypted admitted-source projections, idempotent outbox, atomic generations and invalidation in `atmem/knowledge/projections.py` and `lifecycle.py`; test crash, edit/rename/dependency/delete/restore boundaries in `tests/test_knowledge_lifecycle.py`. Depends T044, T046. FR-019, FR-026; SC-008, SC-012.

## Pending CK expansion — real experience and applicability

- [x] [T048] Add a coding-attempt proposal path to `atmem/code/formation.py`, preserving user assertions separately and routing eligible attributed lessons through existing admission; no model/tool authority or automatic global success inference. Depends T044 and existing T012. FR-021; SC-009. `CodeExperience` validates attributed observations and uses the existing source capture/typed proposal commit; ordinary adapters are not thereby outcome-qualified.
- [x] [T049] Validate authorized producer-bound command/source/environment/result receipts and reject forged, mismatched, unsupported or cross-scope experience in `tests/test_code_experience.py`; include observed failed/unknown attempts. Depends T048. FR-021, FR-026; SC-009, SC-012. Signatures, scope/source/result/environment binding, identity conflicts and pass/failure/unknown checks pass; assurance is an authenticated producer report, not independent verification or a general verified fix. Installed/runtime producer qualification remains T051/T059.
- [ ] [T050] Implement graph-independent anchored applicability in `atmem/knowledge/code/applicability.py` and wire `atmem/code/context.py` through it; validate sanitized source identity mappings, dependency/config changes, worktrees and final-delivery races without weakening defaults. Depends T044 and existing T022. FR-022, FR-023; SC-010, SC-012.
- [ ] [T051] Run disjoint authentic coding-attempt formation and later-revision recall/withholding diagnostics through product services in `tests/integration/test_code_experience_journey.py`; record candidate-to-delivery counts and unmet gates in `specs/042-atmem-code/experience-readiness.md`, never seed oracle lessons. Depends T049, T050. FR-021, FR-022, FR-028; SC-009, SC-010, SC-013.

## Pending CK expansion — structural queries and shared context

- [ ] [T052] Adapt upstream component/dependency/path/impact/architecture/diff query algorithms in `atmem/knowledge/code/queries.py` behind existing `CodeGraph` compatibility facade; use bounded authorized traversal, no LLM requirement. Depends T047. FR-017, FR-020; SC-008.
- [ ] [T053] Add pinned-upstream differential queries and independent anchor/coverage/forbidden-intermediate-node tests in `tests/test_knowledge_queries.py`; record every unsupported cell without narrowing the frozen baseline. Depends T052. FR-017, FR-020; SC-008, SC-012.
- [ ] [T054] Wire one memory-plus-structure planner into `atmem/code/runtime.py` with source revalidation, shared budgets and truthful exposure; test experience-only/structure-only/combined behavior in `tests/test_code_knowledge_context.py`. Depends T050, T053 and existing T023. FR-023; SC-010, SC-012, SC-013.

## Pending CK expansion — transparent user experience and lifecycle

- [ ] [T055] Expose shared search/browse/source/history/related/use/withhold/preview actions in `atmem/code/application.py`, `cli.py` and the existing MCP boundary with authorized pagination and no secret/count leaks. Depends T049, T050, T052. FR-024, FR-026; SC-011, SC-012.
- [ ] [T056] Build the unified Memory Explorer in `atmem/control/assets/` and `atmem/code/dashboard.py`, preserving existing navigation and truthful partial evidence; add keyboard/focus/responsive browser journeys in `tests/test_code_explorer.py`. Depends T055. FR-024, FR-025; SC-011.
- [ ] [T057] Freeze and conduct the five-user formative Explorer study in `specs/042-atmem-code/explorer-usability.md`, recording baseline-relative results and all failures separately from the replicated investigation claim protocol. Depends T056. FR-025; SC-011.
- [ ] [T058] Extend encrypted scoped bundles, migration, deletion and permission epochs to knowledge/experience in `atmem/code/portable.py` and `deletion.py`; verify no resurrection or plaintext auxiliary copies in `tests/test_knowledge_portable.py`. Depends T047, T049, T050. FR-026; SC-012.

## Pending CK expansion — installed qualification and readiness

- [ ] [T059] Run installed-artifact/macOS/Windows/Linux compatibility and explicit host qualification tiers; record source/extractor/crypto/host coverage in `specs/042-atmem-code/knowledge-qualification.md`. Depends T046, T049, T050, T053, T054, T056, T058. FR-027; SC-008, SC-010, SC-012, SC-013.
- [ ] [T060] Produce versioned product capability receipts from `atmem/code/application.py` and `specs/042-atmem-code/knowledge-qualification.md` for Spec 043: B needs T049–T051 plus its installed host/storage proof; C needs T046/T047/T053 and its installed delivery proof; D needs both plus T054. Permit honest partial receipts without closing this task until T057/T059 and all claimed cells pass. No paid pilot is authorized by this task. Depends T044, T051; full completion also T057, T059. FR-028; SC-013.

## Owner-requested structural efficiency loop

- [x] [T061] Improve task-focused structural context to replace redundant exploration with bounded, source-backed evidence; test generic ranking, readable references, excerpt completeness, byte budgets, corruption, scope and freshness. FR-020/FR-023; do not rewrite upstream extraction or weaken authority. `atmem/knowledge/code/packing.py` and the existing projection context boundary; 131 regression checks pass, including compact identifiers and attributed static cleanup sites. Installed local previews are separately pinned; no cross-platform or measured token-saving claim follows from these tests alone.
- [ ] [T062] Qualify a new installed preview artifact and run the explicitly bounded optimization loop in Spec 043 `structure-improvement-loop.md`; target 50% fewer total input tokens, fallback 20%, only with equal-or-better functional task passes. Preserve prior runs and separate tuning from transfer evaluation; no release claim.

  First 40-session loop completed and archived: C3 tuning 32.28% fewer input
  tokens with 4/5 versus 4/5, but stricter 5/5 gate fails. New-task transfer
  uses 3.61% more input tokens (3/5 versus 2/5). Target remains unmet; do not
  mark acceptance complete or claim 20% savings from the tuning result alone.

- [x] [T063] Close the transfer-discovered implementation-localization defect: executable declarations and explicitly named symbols must not be displaced by headings/import aliases; require a disjoint positive localization diagnostic before further solver dispatch. Preserve all first-loop artifacts and choose a new transfer set for any subsequent protocol. FR-020/FR-023, SC-013; no retrospective grade changes. Real installed/extractor CPython 3.12.12 logging probe localized 3/3 requested implementations, withheld changed source and refused stale submission, with zero model calls. Artifact SHA-256 `0dae1b754b43786b26cae8ae067dc62306476ec83e7b7a489ff24f9163cb2ac1`; performance acceptance remains open in T062, and new transfer selection is required by the second-loop protocol.

- [x] [T064] Add bounded related implementation assembly using incorporated call traversal, compact class navigation plus relevant method bodies, and import-bound helper source nomination. FR-020/FR-023; preserve authority and freshness. Third-loop installed artifact `eb05005cab32bbacf7b125a706ab5d797f26692c2446a49f8b0adb6c3809787e` passes disjoint logging/callee/source-change qualification; 34 focused regression checks pass. No performance acceptance: P2 lost quality; P3 completed with 14.55% fewer input tokens but 3/5 versus native 5/5 passes under Spec 043 `call-path-loop-v3.md`. External hypotheses recorded in `RandD/2026-10-17-code-context-research-clues.md`; T062 stays open.

- [x] [T065] Qualify bounded current-source behavioral examples alongside structural implementations, then evaluate under Spec 043 `source-usage-loop-v4.md`. FR-020/FR-023, SC-013. Source checks preserved; disjoint installed CPython/public test qualification and 37 focused checks pass. Candidate `f769e0b2e572cd4c6623c682fb832e0beeef46b75bfacbffb88b690a72aaf6d5` completed ten attempts: 5/5 functional passes each, native 5/5 versus structure 4/5 all-cap passes; one over-tool-cap structure turn has unknown usage. No token acceptance, transfer not dispatched; T062 remains open. Exact-event encrypted archives and fresh-process recovery verified.

- [x] [T066] Add project-bound read-only progressive Code knowledge MCP queries using existing transport/source/traversal boundaries; qualify scope, source-change refusal, compact response bounds and actual ephemeral host integration before the bounded Spec 043 `progressive-retrieval-loop-v5.md` comparison. FR-020/FR-023, SC-013. No owner configuration changes, broad memory tools, scope overrides or evaluator access; token/quality acceptance remains in T062.

  Implemented and qualified installed MCP transport plus actual Luna client
  source-response/scope-refusal controls on CPython logging; source edits are
  withheld at the transport boundary. The independent native shell-read probe
  passes, but the model's claimed native canary attempt is unverified in partial
  CLI events. P5 replacement ten-attempt scoring completed negatively: 4/5 each,
  unknown C usage and only 3/5 verified source exposures. T062 remains open.
  Local artifact `aecce2d4ea8a91ed073d261a512d17723cdeb53a26942d264952db18761ac9d9`;
  33 focused combined checks and 17 follow-up harness checks pass. No remote
  CI, normal owner-host install or cross-platform claim.

- [ ] [T067] Add one-request focused current-source MCP retrieval and safe actionable parameter errors; evaluate 4096-byte proactive source plus on-demand context under Spec 043 `focused-context-loop-v6.md`, preserving scope/source/receipt checks and all prior negative results. FR-020/FR-023, SC-013. Qualify the actual installed tool/host before any new scoring; no token acceptance until the full paired tuning/conditional transfer gates pass.

  One-request endpoint, safe limit errors and proactive 4096-byte runtime request
  are implemented. Fifty focused checks pass; installed disjoint transport,
  safe-error, stale-source and actual four-tool Luna host/source-byte audits
  pass. P6 ten-attempt scoring completed: 4/5 functional/policy passes each,
  unknown native total usage after a hard tool stop, no valid paired token
  saving. All eleven archives recovered in a fresh process. No transfer
  dispatched; tuning/conditional-transfer acceptance and T062 remain open.

- [x] [T068] Correct exact-symbol/getter conflation, compact repeated class navigation, and preserve caller priority over inferred import helpers; qualify and evaluate one installed candidate under Spec 043 `compact-navigation-loop-v7.md`. FR-020/FR-023, SC-013. Preserve all prior negative results and fixed quality/token gates; source-unit success is not performance acceptance.

  Implemented; 160 combined regression checks pass. Installed actual CPython
  extraction/source/freshness and real Luna four-tool MCP responses are qualified;
  two encrypted diagnostic archives recovered in a fresh process. Ten-attempt
  scoring completed under manifest `5d18142541eaa424a5b0730f62baed90fa77ece1f0875cfd62b770515fc0d723`:
  4/5 each, 38 versus 54 tools, native total usage unknown after hard stop,
  no valid paired total saving. Eleven cohort archives recovered independently.
  T062 acceptance remains open; no transfer or release claim.

- [x] [T069] Fit the highest-ranked existing behavioral source within its actual UTF-8 budget rather than silently substituting lower-ranked examples; preserve exact source lines, omission and execution-assurance labels, scope/currentness and all fixed evaluation gates. Qualify and measure one artifact under Spec 043 `budgeted-usage-loop-v8.md`. FR-020/FR-023, SC-013. No independent field-flow or token-benefit claim from this fix.

  Implemented; 164 combined checks pass. Installed CPython extraction and real
  Luna focused-MCP/source-byte/freshness controls pass; two qualification archives
  recovered independently. Frozen ten-attempt scoring completed under manifest
  `9fb791ef2e7223998beef669397ea8e10dcb2f8425a121a275fa7e195b5fd8a5`.
  Result: 3/5 each, 69 versus 59 tools, unknown C total usage after hard stop.
  Eleven cohort archives recovered independently; no accepted saving, transfer
  or release claim. Improved example fitting displaced a relevant implementation
  in task 3; joint source-budget prioritization remains required before promotion.

- [x] [T070] Correct joint source-budget priority inversion so behavioral previews and incidental navigation cannot evict higher-priority connected implementations merely through preallocation. Preserve source/currentness/scope, run disjoint installed and actual host qualification, then measure one artifact under Spec 043 `joint-source-budget-loop-v9.md`. FR-020/FR-023, SC-013. Keep all prior failures, unknowns, quality/token gates and separate confirmation.

  Implemented; 165 combined checks pass. Installed real CPython extraction and
  actual Luna focused-MCP/source-byte/currentness controls pass; two qualification
  archives recovered independently. Ten-attempt frozen scoring completed under
  manifest `2491042c943ba247109a1dda8e4a20f39dc829edaa0125c8e345e28ee3c58c2f`.
  Result: 5/5 functional each, known usage throughout, 19.551447% input reduction.
  Below the fixed 20% gate; no rounding or transfer. All-cap passes 4/5 native,
  5/5 structure; median measured path 23.755s versus 33.670s. Eleven cohort
  archives recovered independently. T062 acceptance remains open.

- [x] [T071] Remove redundant inline graph notes only for fully included implementation targets, retaining missing/partial-target navigation and identical selected source, anchors, usage and conservative allocation. Run golden/source/authority gates and installed qualification before one Spec 043 `covered-navigation-loop-v10.md` comparison. FR-020/FR-023, SC-013. Keep the exact 20% fallback and separate confirmation despite P9's near-threshold result.

  Implemented; 169 combined checks pass. All five retained P9 numbered-source/
  header comparisons match, with metadata-only byte reductions. Installed CPython
  and actual Luna host/source-byte/currentness controls pass; two qualification
  archives recovered independently. Frozen ten-attempt scoring completed under
  manifest `a77202b242f21247f5d9db086742648117452ac7f721c9c56bccc964406232e1`.
  Actual delivered source equivalence passes all five. Functional passes 5/5
  each; all-cap passes native 3/5 versus structure 5/5. Native hard-stop usage
  remains unknown, so no valid saving or confirmation. Eleven cohort archives
  recovered independently; T062 acceptance remains open.

- [ ] [T072] Qualify a bounded, disjoint incremental-usage/cancellation transport diagnostic under Spec 043 `usage-transport-diagnostic.md`, beginning with a zero-inference configuration and actual sandbox-read control. Preserve errors and partial counters without imputing historical usage; require new matched transport qualification before any scored cohort. FR-023, SC-013. This diagnostic does not satisfy T062 or authorize relaxing token/quality gates.

  Zero-model actual read/denial control passed. One disjoint Luna-low turn
  retained a usage update before an interrupted terminal. Twenty local checks
  pass. Full interrupted usage completeness and scored transport equivalence
  remain unproven; no historical receipts backfilled or scored runner changed.

- [x] [T073] Keep bounded behavioral excerpts' assertions together with their same-block simple call-producing assignment, preserving exact source and conservative assurance. Test scope/byte/multiline boundaries and qualify a new installed artifact before one Spec 043 `producer-linked-usage-loop-v11.md` comparison. FR-020/FR-023, SC-013. No authority, scorer, complete-usage or exact 20% gate changes.

  Implemented; 157 expanded local checks pass plus 12 overlapping progressive/
  inventory checks. Corrected explicit image-binding qualification passes on
  installed CPython sources; the first malformed-argument failure is retained.
  Actual Luna host returns five MCP calls with exact source/pack response audit.
  Ten frozen P11 attempts completed: native 5/5 functional versus structure 2/5,
  unknown structure total usage after task-2 hard stop; no accepted benefit.
  Eleven cohort archives verified and independently recovered; no confirmation.
  T062 remains open. A raw infrastructure flag is corroborated as candidate
  syntax failure, not grounds for excluding the failed row.

- [x] [T074] Audit retained failure attribution and progressive tool uptake without regrading, excluding rows or imputing usage. FR-023, SC-013. Keep raw grader flags distinct from corroborated candidate syntax failures and tool-output byte counts distinct from model tokens.

  Fifteen focused audit checks pass. Sixty retained P6–P11 attempts audited;
  all thirty C attempts have zero completed AtMem MCP calls. P11 C task 3's
  changed source syntax error is corroborated by its grader output. Historical
  scores and five-task denominators remain unchanged. Evidence retained under
  `efficiency-tool-use-audit-p6-p11-20261017`.

- [ ] [T075] Add fixed operator-authored Code MCP usage guidance through the standard initialize instructions field, separate from untrusted source. Preserve generic AtMem MCP behavior, read-only scope/currentness and native fallback. Qualify a bounded, two-arm, disjoint uptake diagnostic before any new scored comparison under Spec 043 `guided-retrieval-diagnostic.md`. FR-020/FR-023, SC-013. Uptake is not evidence of task or token benefit.

  Code-only initialize guidance and operator disable profile implemented; 70
  local MCP/packing/audit checks pass. The unrun one-pair diagnostic is held
  after the requested Claude review, not silently executed or retried. Exposure
  and repository-diverse diagnostics now follow the cross-repository plan.
  No performance or automatic host-consumption claim.

- [x] [T076] Obtain the requested Claude Opus 5.5 medium read-only CLI review, inspect primary-source alternative task repositories/harnesses, record adoption/corrections, and retire further familiar Click tuning without rewriting historical outcomes. FR-023, SC-013.

  Returned metadata confirms `claude-opus-5-5`; subscription CLI, tools disabled,
  no fallback. Verbatim review, input provenance and adoption decisions retained.
  Official benchmark/task catalog and candidate repository metadata inspected;
  no external gold patches, hidden test patches or hints opened. Prospective
  repository-disjoint plan recorded; no external tasks claimed runnable yet.

- [ ] [T077] Execute `cross-repository-evaluation-plan.md` preflight: pin eligible authentic task/environment metadata, replace Click-specific source/grader assumptions, verify exposure and complete usage, then freeze a bounded repository-disjoint validation/confirmation design before model repair scoring. FR-020/FR-023, SC-013. No goal completion from preflight, model review, uptake or selected tuning outcomes; no relaxed quality or token gates.

  Progress snapshots below are chronological; later outcomes supersede earlier
  pending-state descriptions without erasing the recorded failures or stops.

  Identity-only metadata preflight completed for six fixed external tasks; all
  Git blob/recipe checks pass and six immutable amd64 image descriptors resolve.
  One pinned image passes constrained amd64 shell/Python 3.9.21 execution on
  the ARM worker. No test/gold/hint/problem-statement fetch or model solve.
  Neutral source-only snapshot merge and distinct MCP protocol prepared/written
  receipts implemented; 208 local checks pass. Actual filesystem/worker/grader
  integration, parent/reference, exposure and complete-usage gates remain open.
  Resource guard prevents blindly pulling more images with about 8.6 GiB free.

  Subsequent parent/reference v1 preparation retained the first task's pinned
  private evaluator material and upstream parser/grading sources internally.
  Six qualification-adapter fixture checks pass. Both dispatches stopped before
  execution at the 8 GiB host-space guard (about 7.2 GiB free); neither has test
  results. No solver ran and no task was replaced. Retain this resource stop;
  a future same-task control must use a new recorded version, not overwrite v1.

  POSIX stopped-workspace capture now uses descriptor-relative no-follow reads,
  bounded regular files and mutation checks; eleven capture fixture cases and
  fourteen source-policy tests pass. Caller-owned process quiescence and actual
  external solver/grader wiring remain open; this does not close T077.

  Retired scratch recovery now verifies 300 encrypted archives in fresh processes;
  exact-source/open-handle checks preceded removal of the 300 archived directories.
  They remain recoverable on MEM with keys internal. Free host space rose to
  about 8.10 GiB. Explicit same-task parent/reference v2 is dispatched, not yet
  outcome-qualified; no solver or new scored tuning. 236 local checks pass.

  V2 subsequently qualifies the first Marshmallow parent/reference environment:
  parent fails 8/8 target checks, reference passes 8/8; both pass all 61 regression
  checks with no skips or cleanup failure. Other environments, solver integration,
  exposure/full-usage and matched efficacy remain open. Solver calls stay zero.

  Source boundary v1 now passes actual unchanged/reference-through-assembler
  controls (0/8 versus 8/8 targets, 61/61 regression each). Verified public
  source export contains 76 files/718,790 bytes, excluding six image-only files
  and all Git history. Public-proposal comparison preserves those runtime files;
  both reconstructed assemblies match the actual graded predecessor bytes.
  This is zero-model integration evidence, not new model or token benefit.
  See `RandD/2026-10-17-external-source-boundary.md`; T077 remains open.

  Combined local checks: 261 passed. Five encrypted bundles recover 19 events
  without the original vault, with source/assembly byte validation. No remote
  CI, model scoring, native development-test access or goal acceptance claim.

  Public development-test worker and role-separated request construction now
  have fourteen local fixture checks; the combined replay/MCP/packing suite
  passed 275 checks. Public-test fixtures are included in the CI definition
  (remote execution not claimed). Actual public-test v1 stopped before container
  execution at the unchanged 8 GiB host-free-space guard; its terminal summary
  is retained with zero solver calls. Public test access remains unqualified.
  Owner subsequently prohibited cleanup/moves without approval; no disk cleanup
  is authorized. Do not overwrite v1, silently retry or lower the guard. T077
  and the token/quality acceptance in T062 remain open.

  Owner-authorized Windows migration on 2026-10-18 now executes unchanged
  public tests successfully: 908 passed, one warning in 1.80s; controller
  elapsed 3.183s on native-amd64 Ubuntu WSL2. The same public-worker bootstrap
  and immutable image are verified; the unchanged 8 GiB guard now checks both
  WSL and physical Windows free space. Zero solver calls. Exact inputs, code
  and output are retained under `external-windows-public-base-v1-20261018`.
  No Mac files moved/deleted. See
  `RandD/2026-10-18-windows-benchmark-worker.md`. Solver isolation, exposure,
  usage, hidden-grader migration and matched benefit remain open; T077 stays
  unchecked. Do not pool Windows timings with earlier Mac measurements.

  Windows now also qualifies unchanged/reference-through-assembly hidden grading
  (0/8 versus 8/8 targets, 61/61 regression each), actual shell read/network
  isolation, an installed-source-identical AtMem preview, native amd64 extraction,
  governed context preparation and stale-source withholding. One native and one
  explicitly instructed MCP discovery turn complete with full normal-terminal
  usage; both MCP source responses match the frozen indexed bytes. These are
  diagnostics, not a matched token comparison or issue repairs. Missing native
  rg was installed before scoring; sandbox tool scratch is prospectively
  separated from source, not retroactively exempted. Candidate-proposal grading,
  matched batch manifests, remaining environments, interruption completeness
  and efficacy/confirmation remain open. No benefit or T062/T077 completion.

  Evaluator-only public solver proposals now traverse the existing decoder,
  scoped source assembler and official grader. Exact base membership/modes/blob
  bytes, frozen tests and image-only runtime retention are checked. The actual
  Windows unchanged/reference proposal controls reproduce 0/8 versus 8/8 target
  passes and 61/61 regressions, with byte-identical prior assembled digests and
  zero solver calls. A pre-execution wrapper failure is retained as v1; the
  explicit v2 fixes only double JSON consumption, with unchanged worker bytes.
  Fifteen proposal/Windows transport fixtures pass; no remote CI claim.
  Matched model manifest, common public-test access, candidate lifecycle/usage
  binding, remaining task environments and efficacy/confirmation remain open.

  Common public-test access is implemented using existing AtMem MCP transport,
  scoped protected evidence and the pinned public worker. It evaluates a supplied
  patch against the public base, never claims a live worktree is frozen, and
  exposes no private-grading or generic-execution tool. Actual Windows unchanged/
  comment-only patch controls pass with exact candidate binding; ordinary-user
  stdio execution, unauthorized-root refusal, encrypted/full evidence recovery,
  native denial of direct privileged-broker execution and cleared-environment
  startup all pass. The initial namespace-denial probe failure remains retained.
  Combined regression suite: 304 passed. No model repair comparison yet; matched
  manifests, lifecycle/usage binding, other environments and confirmation remain
  open. See `common-public-tests-v1.md` and the Windows worker RandD report.

  The first frozen Windows repair pair subsequently completes with full usage,
  stopped candidate binding and private grading: native and AtMem each pass 4/8
  target checks and 61/61 regressions, neither solves the issue. AtMem uses
  286,923 total input tokens versus native 219,942 (30.453938% more), with zero
  completed Code MCP calls. Two explicitly corrected pre-inference ownership
  failures remain retained; no model retries or missing usage rows. See
  `RandD/2026-10-18-first-windows-repair-comparison.md`. Other environments,
  the broader matched batch and independent confirmation remain open. Neither
  this integration pair nor its negative result completes T062/T077.

  The remaining five fixed task images are now staged at their pinned identities
  on Windows. All five constrained shell/isolated-Python/image-identity controls
  pass, with no new solver calls or task-script execution. Exact runtime
  containers are confirmed removed; images remain cached. Parent/reference and
  source/solver qualification on those tasks remain open. Evidence:
  `external-windows-remaining-images-v1-20261018`.

  Generic qualification now binds all six selected task/base/parser identities;
  the original single-task proposal default stays restricted. The expanded suite
  passes 311 checks. Actual Windows parent/reference controls qualify four more
  tasks (Marshmallow-1810, Requests-1327, Astroid-934/1616), with complete target
  and regression statuses and no skips. Requests-4356 stops before tests because
  a tracked 2,189,478-byte logo exceeds the 1 MB per-file source bound; both
  failures and a read-only diagnostic are retained, with no guard change, retry
  or replacement. Evidence: `external-windows-remaining-reference-v1-20261018`.
  Source/export/public-test/solver qualification beyond the first task, the
  asset-boundary correction and the broader model batch remain open.

  The explicit v2 asset resource profile is implemented consistently across
  capture, snapshot validation, public decode/export and the standalone grader:
  recognized assets up to 4 MB, source/text still 1 MB, whole snapshot 40 MB,
  unchanged authority and byte verification. Actual Requests-4356 v2 passes
  source verification but remains unqualified: parent collection error with
  missing target statuses, reference only 111/115 target passes. Full outputs
  retained under `external-windows-requests4356-asset-v2-20261018`; no network
  relaxation, removed tests, task replacement or model calls. Source/solver
  integration on the other newly qualified tasks can proceed; matched cohort
  and goal acceptance remain open.

  Source assembly and verified public exports now pass for Marshmallow-1810
  and Astroid-934/1616. Requests-1327 v1 stops at the unchanged snapshot cap
  because of a 52 MB untracked `.eggs` runtime cache. Explicit v2 excludes only
  that cache after proving no tracked-source overlap, leaves it untouched and
  passes 0/1 versus 1/1 target and 31/31 regression controls. Default capture
  and v1 stay strict. All four public exports match pinned Git bytes/modes and
  tracked fingerprints; no history/untracked/evaluator data is exported. Exact
  raw streams are retained in bounded evidence chunks. The combined suite
  passes 324 checks. See `RandD/2026-10-18-selected-repository-source-controls.md`.
  Public-test/proposal adapters, actual cross-repository solver cohort and
  confirmation remain open; no token-saving or T062/T077 completion claim.

  Configured public-proposal grading now qualifies all four new tasks through
  exact public Git validation, frozen-source assembly and their pinned upstream
  parsers: all unchanged target failures, all reference target passes, and full
  regressions without skips. Public-runtime probes also verify candidate-source
  imports and removed Git/private-evaluator boundaries for each task; these are
  harness fixtures, not repair-quality results. Task/layout/runtime/image-extra
  settings are embedded by the operator, never accepted in model request fields.
  Root `test_requests.py` selection is restricted to Requests-1327. Full suite:
  329 passed. Evidence: `external-windows-selected-proposals-v1-20261018` and
  `external-windows-selected-public-runtime-v1-20261018`. Host staging/cohort
  execution and confirmation remain open; no accepted performance benefit.

  The 36-slot Windows validation manifest is frozen (30 feasible attempts,
  six explicit Requests-4356 environment attrition slots). V1 stages its first
  triplet but stops on an Astroid dependency-directory mapping refusal before
  any model inference. Raw failure, artifacts and diagnostic setup errors are
  retained. The generic typed upstream module-rollup correction is qualified
  below; V2 must restage every feasible slot using the new preview, with the
  same task/order/caps and no outcome-driven model retries. See
  `windows-selected-validation-v1.md` and `windows-selected-validation-v2.md`.

- [x] [T078] Preserve authorization while supporting upstream derived module-edge dependency facts that name an authorized package directory rather than a source file. Require typed symbol-rollup metadata and matching module-edge naming, retain writer identities without invented file/line anchors, and keep unknown directory/symbol/untyped claims rejected. FR-020/FR-023, SC-013.

  Subsequent validation: all 30 eligible Windows attempts and private grades are
  complete with full usage and stopped-source binding. Native/pack/tools solve
  4/10 each; tools uses 24.817175% fewer total input tokens, pack 17.395380%
  more. Target checks are 12/24, 8/24 and 4/24 respectively; every declared
  regression check passes. Only one Code MCP call completes. This passes only
  the aggregate 20% validation gate, not 50% or independent confirmation. Cold
  component-sum latency is higher. See the completed Windows cohort RandD
  report; T062/T077 remain open, with no broad quality/causality claim.

  Negative and positive fixtures pass; full related suite: 440 checks. Replaying
  the actual 2,104 Astroid facts maps 2,059 objects and 4,961 relations against
  verified source bytes, without an anchor for the directory dependency.
  A separately built, source-identical installed Windows preview
  `1287625d5efff66ebfd31dac7a7eb471ecc964b2c149aee76201b6d782a27509`
  passes real indexing and independent-scope equal-pack qualification (3,964
  bytes each). No model call, token benefit or T062/T077 completion follows.
  New cohort fixtures and mapper tests are included in CI configuration;
  remote CI is not claimed.

- [ ] [T079] Lock the selected validation candidate and execute the separate
  repository-disjoint confirmation under `windows-confirmation-v1.md`, retaining
  every original identity, resource/environment failure and complete paired
  evidence. Depends T077/T078. FR-020/FR-023, SC-013. No product retuning on
  confirmation grades, missing-as-zero usage, task substitution or relaxed
  quality/input thresholds. Include independent protected archive recovery.

  Metadata-only preflight selects 20 identities across the five prospectively
  named new repositories, four each, using fixed seed and pinned catalog.
  Selection SHA-256:
  `8d1c769642903a84419231543ec1bff37d3b5dc1727d6760117a7cb252711d9f`.
  All 20 metadata/blob checks pass; no confirmation solver has run. Separate
  fixed base/parser/source-layout bindings and strict parent/reference fixtures
  are added without changing the original six-task validation manifest.
  Windows registry/runtime qualification is live; inaccessible declared image
  tags remain failures, not replacements. Its initial Docker image-ID checker
  expects only config IDs, whereas this Docker 29 store returns manifest IDs.
  The correction verifies both identities against the retained pinned manifest
  and exact raw transport without rerunning or rewriting original controls;
  it must be explicitly recorded before reference qualification. Model/product
  bytes and budgets remain locked. All broader acceptance gates remain open.

- [ ] [T080] Align rich source capture with the existing graph's explicit
  oversized-file rejection: exclude an oversized regular file without reading
  above the existing cap, retain visible exclusion counts, reject symlink/race/
  aggregate-budget faults and invalidate when covered files or omission counts
  change. FR-018/FR-019/FR-023, SC-008/SC-010/SC-012. This is a new candidate,
  not a modification of the frozen Windows validation/confirmation artifact.
  Require local boundary tests, installed-artifact qualification and a new
  unexposed confirmation pool before making benefit claims. Preserve all
  failed preflight evidence and the prior candidate lock.

  Local implementation now uses a typed per-file-budget refusal after
  descriptor-relative no-follow regular-file validation. It omits only that
  over-budget file, preserves the 262,144-byte default and aggregate limits,
  and exposes `file_budget` counts in index, context and Code MCP metadata.
  Covered-source and omission-count changes invalidate cache/publication;
  ignored hidden-file behavior remains compatible. 180 related checks pass
  before the final additive context metadata check. Installed artifact and
  fresh-pool efficacy remain unverified, so T080 stays open. No changed build
  is substituted into the frozen Windows results.

  Subsequent caller audit keeps strict execution capture as the default and
  makes omissions explicit for graph projections only. The initial omission
  build is superseded before model inference. Corrected wheel
  `9900aa70371a1ec911b7215532711cbdc83da726198ca0eacf85bbf6054146c8`
  passes installed-source/dependency equality and real-source Windows/WSL
  extraction, exact-source, omission metadata, strict execution, symlink,
  freshness and audit controls. The full structure-only turn bridge also
  passes without inventing execution identities or task memory. 189 related
  local checks and a separate overlapping 23-check group pass. See
  `RandD/2026-10-18-explicit-source-omissions-candidate.md`; efficacy remains
  unverified and the old cohort remains unchanged.

- [ ] [T081] Execute `windows-confirmation-v2.md` for the locked explicit-graph-
  omissions candidate using the prospectively frozen, wholly new repository
  eligibility pool. Depends T080. FR-020/FR-023, SC-013. Retain all eligibility
  failures, freeze the final nineteen model-task identities/order before
  inference, prohibit model-outcome selection and preserve fixed input/quality,
  authority, full-usage, uncertainty and archive gates. Insufficient eligibility
  is incomplete; do not silently shrink or expand the design.

  Owner-approved pre-inference amendment: three PyVista tasks, four each for
  Flask, Seaborn, Xarray and Pylint, nineteen tasks / 76 solver attempts. All
  forty original eligibility candidates and failures remain in the report.
  No grade, source, input, quality or usage gate is relaxed by the amendment.

- [ ] [T082] Implement and qualify the benchmark-only source/runtime projection
  and bounded lossless worker-result transport specified in
  `source-runtime-projection-v2.md`. Depends T080; blocks the affected T081
  source/public/proposal qualification stages, not its completed inventory.
  Preserve all original candidate identities and failures, strict test/network
  grading, frozen product and source/context limits. Require adversarial local
  controls and actual Windows image controls before model inference. Runtime
  fixtures are immutable verified evidence, not editable source or context.

- [ ] [T083] Qualify the fixed PyVista runtime compatibility correction in
  windows-pyvista-runtime-compatibility-v1.md after the recorded dependency
  diagnosis. Depends T082's inventory boundary; blocks PyVista's T081 runtime
  qualification. Use the same VTK 9.3.1 choice for all eight original tasks,
  verified derived-image/package/source identities and offline setup with
  unchanged tests/gates. Preserve original-image failures; no version sweep,
  task substitution or model-outcome-based dependency selection.

  Windows-local no-model controls are terminal: seven of eight image builds
  qualify, and 4315 retains its original-version refusal. The terminal-pool
  prerequisite correction is explicit in the compatibility protocol, without
  changing tests or final cohort size. Seven inventories pass; fourteen
  parent/reference executions qualify only 4311, 4329 and 4853. Six source-
  assembly executions then qualify only 4311 and 4329. Four are mandatory for
  the final PyVista stratum; T081 cannot freeze its twenty-task manifest and
  no confirmation model inference has run. All failures remain retained.
  Local code-replay suite: 388 passed. T083/T081 remain open, not accepted.

  Subsequent diagnosis proves 4853's two source-assembly failures were complete
  result-emission overflows, not known negative grades. The explicit bounded
  lossless XZ response repair preserves caps/full JSON and exact hashes. Its
  initial program-equivalence guard stops before any worker; the corrected
  guard has a full-bootstrap equality regression test and a separate explicit
  zero-worker resume. Both rerun control phases pass unchanged tests: 1/1
  parent target failure, 1/1 reference target pass, 23/23 regression passes in
  both. Four complete successful phase records for 4311/4329 are reused.
  All three now pass source assembly. Source export, public/proposal and final
  installed cohort qualification still remain before the amended 76 attempts.

  Subsequent source/public/proposal controls now pass for all 23 eligible
  candidates. Explicit pre-Docker argv-size corrections preserve the original
  programs, payloads, limits and failed receipts; completed controls are reused,
  not retried. The nineteen first-qualifying identities and 38 balanced blocks
  are locked in prospective manifest a153ad38ae0439bc42804a422c99b8f6541d020c6693885498ee2730d7520a28.
  Fresh installed staging is live; the first seven paired blocks succeed with
  the frozen wheel and 4,096-byte pack. Actual common public patch/MCP bridge,
  sandbox readiness, scoring, full usage/latency analysis and independent
  archive recovery remain required. No model inference or token acceptance
  follows from staging. Local code-replay suite: 411 passed; new fixture groups
  are in CI configuration, with no remote CI claim.

  Staging subsequently terminates at 28 successful / ten failed paired blocks.
  Four Pylint identities fail both repeats on valid non-UTF-8 fixtures;
  PyVista-4853 fails both repeats at the unchanged 16 MB generation-row limit.
  These product compatibility failures remain blockers, not omitted tasks.
  Actual public MCP readiness terminates; fourteen native checks qualify and
  fourteen tools checks stop before Code MCP startup at a root-only benchmark
  runtime directory. A protected, exact-directory root:1000 0710 traversal
  repair preserves installed source/metadata/interpreter bytes. Code-only
  resumption then qualifies all fourteen tools checks as the ordinary user,
  recovering their completed public receipts without new public executions.
  No confirmation model calls have run. See the Windows runtime RandD report;
  T062/T080/T081 remain open and the full nineteen-task design is not ready.

- [x] [T084] Correct rich-source text decoding consistently across capture,
  worker secret screening, structural packing and source presentation under
  `source-text-compatibility-v1.md`. Depends T080. FR-018/019/023;
  SC-008/010/012. Preserve original byte identities and strict authority,
  reject malformed/unknown encodings without replacement, and require local
  secret/byte/freshness gates plus a separately pinned installed preview and
  real failed-source replay. Do not change the frozen wheel, drop failed
  tasks, weaken strict capture or claim the nineteen-task confirmation ready.

  Local implementation now uses one strict decoder for capture, worker
  screening, packing, source inspection and encrypted bundle validation. A
  versioned rich capture policy retains original bytes/hashes, honors declared
  Python encodings and text BOMs, and rejects malformed encodings. Boundary
  tests cover encoded-secret exclusion, exact worker archives, source/pack
  parity, bundle byte preservation and stale-source withholding. The expanded
  replay/knowledge suite passed 615 checks before the final bundle-validator
  change; the subsequent source/bundle/MCP group passed 52 checks. These groups
  overlap and are not added together. New gates are in CI configuration only;
  installed preview and real failed-source replay are still open. T084 stays
  unchecked. The frozen confirmation installation is unchanged.

  Actual protected source-text diagnostic v1 evaluates 9,159 eligible original
  files across the four selected Pylint source exports. Declared Latin-1 now
  decodes, but each tree contains an unknown Python codec and two BOM fixtures
  that fail strict decoding. Graph-only invalid-text exclusions are therefore
  explicit, counted and revalidated; strict capture still rejects. No guessed
  decoding or silent partial execution identity. This is uninstalled source
  compatibility evidence, not new model scoring or installed qualification.

  Latest full replay/knowledge suite after that graph-only omission change:
  616 passed in 48.17 seconds; eight spec-task inventory fixtures pass.
  Installed preview and actual capture/extractor qualification remain open.

- [x] [T085] Implement and qualify bounded, lossless large-generation storage
  under `generation-storage-compatibility-v1.md`. Depends T047/T080; FR-019/026,
  SC-012. Keep the 16 MB physical row limit, complete original artifacts and
  encrypted authorized storage; bound logical decode, verify scope/identity,
  size/hash/stream boundaries, preserve small/legacy rows, atomic publication,
  deletion and full encrypted portability. Require adversarial local gates and
  a new installed real-source PyVista replay. Do not alter the frozen candidate
  or select a smaller success-only confirmation cohort.

  Local implementation preserves the physical cap with a bounded, identity-
  bound lossless codec and complete logical reads. The large bundle gate first
  exposed the signing binding's message-size bound; a product-owned adaptation
  of the exercised authenticated-chunk protocol preserves original encryption,
  signature verification, full artifacts and legacy small exports. Forty-seven
  focused codec/transport gates pass, including real SQLCipher reopen and large
  encrypted bundle restore/clear. Broader replay/knowledge/Code/encryption group:
  696 passed, one platform-specific test skipped on macOS. Groups overlap.
  Independent preview e8d98dadfa98554ba38311096a7b90dac815bbbe03c6c35dae430bed54ee7bf6
  verifies complete installed source, eleven unchanged distributions and uid
  1000 startup. Five failed-source installed controls are live. T085 remains
  open until terminal qualification, not completed by the build alone.

  Subsequent terminal qualification closes the bounded T084/T085 correction:
  all five real-source controls pass on the independently installed preview,
  retaining source/artifact bytes, 4,096-byte context, exact encrypted bundle
  recovery, freshness withholding, valid audit and uid/gid 1000 Code MCP.
  Pylint's four logical generations are 13,000,853–15,343,204 bytes; PyVista's
  16,349,856-byte generation now publishes within the unchanged physical row
  bound. Run external-windows-source-storage-qualification-v1-20261018 is
  terminal with zero model calls. This closes these compatibility tasks only;
  T062/T080/T081/T086 efficacy/full-cohort gates remain open. No broader
  extraction/platform parity, remote CI, published release or token benefit
  follows. Earlier open/live annotations above are chronological checkpoints.

- [x] [T086] Execute the explicitly disclosed compatibility-only amendment in
  `windows-confirmation-v3.md` after T084/T085. FR-020/023/026; SC-012/013.
  Preserve all nineteen task identities/order and forty eligibility results,
  freeze the exact new candidate and full execution manifest before inference,
  stage all 76 fresh cases and qualify their real MCP/sandbox boundaries. Then
  run the unchanged paired token/full-task quality/partial harm/latency/usage/
  uncertainty and independent archive gates. No v2 partial-state pooling,
  success-only cohort, model-outcome retry or release claim.

  Fresh v3 staging is dispatched under
  external-windows-confirmation-v3-staging-v1-20261018 with the independently
  installed e8d98dad preview, the exact old nineteen identities / 38 balanced
  blocks, two preparation workers and no solver calls. Only observer timing
  instrumentation changes the retained staging program; a reversible equality
  fixture verifies the delta. Full original streams remain in protected chunks.
  The first twelve blocks qualify, with no failures at that checkpoint.
  The full 76-case MCP readiness driver is prepared, not dispatched; its worker
  differs from the prior actual control only in the exact v3 root check.
  Three v3 staging/readiness fixtures pass and enter CI configuration. The
  terminal staging result, actual MCP/sandbox controls, final execution lock,
  model comparison and archive acceptance are still required. T086 stays open.

  Staging is now terminal: all 38 paired blocks / 76 cases qualify, with zero
  failures, exclusions, retries or model calls. The separate actual 76-case
  stdio MCP readiness run is live under
  external-windows-confirmation-v3-mcp-readiness-v1-20261018. Its terminal
  results, sandbox controls, final execution lock, model comparison and archive
  remain pending. The latest overlapping codec/transport/v3 fixture group
  passes 50 checks; eleven inventory/v3 fixtures pass. No efficacy acceptance.

  Subsequent readiness is terminal: all 76 actual MCP and all 76 pinned-CLI
  sandbox cases qualify. The original sandbox expectation failure is retained;
  the corrected probe recognizes hidden-view FileNotFoundError as denial after
  an outside positive control, without changing permissions. Root-owned cgroup
  containment/termination qualifies with a detached-child escape-negative
  control. The execution lock verifies all 76 full initial sources and binds
  all nineteen exact qualified private graders. Nine lock/grading fixtures pass.
  Scored inference is dispatched under
  external-windows-confirmation-v3-models-v1-20261018, first cell slot 0 native.
  All private grading waits for all 76 attempts. T086 remains open until full
  matched scoring, usage, uncertainty and independent archive acceptance.

  First seven scored attempts are captured without a supervisor stop; no
  private grades have been inspected. The separate postprocessor is live,
  waiting for the full 76-attempt terminal before exact private grading,
  original-transport matched accounting and actual public-log/audit recovery.
  It has no model-launch or retry path. Local regression group: 726 passed,
  one platform-specific skip; five focused report/finish checks overlap four
  report checks in that group. Python 3.10 grammar checks pass for the four
  new postprocessing modules. Independent archive acceptance stays separate.

  Subsequently eighteen model attempts are captured. Full per-run encrypted
  archive collection/recovery is implemented, preserving all scored cells,
  source exports, grader material, readiness failures and prior staging.
  Six focused archive checks pass, including existing cryptographic round-trip
  checks. An archive waiter records its complete implementation and waits for
  terminal postprocessing before export. A read-only rsync listing verifies
  the authorized Windows-to-Mac transfer path. Actual MEM transfer and separate
  fresh-process archive recovery remain required; T086 stays open.

  Before private grading starts, unchanged-source request sizing exposes three
  PyVista dispatches above the 16 MB protected-event limit. The zero-phase waiter
  is explicitly paused/terminated, while models continue. The bounded lossless
  retention-only amendment in windows-confirmation-v3-grading-retention.md is
  guarded against any grader/test/budget change and records the full new source
  before resuming the wait. Seventeen focused fixtures pass. The actual journal
  has initial plan, pause and amendment only; no private grade was retried.
  Fifty-five model attempts are captured. All efficacy/archive gates remain open.

  The model process subsequently exits zero with all 76 fixed attempts captured,
  without a supervisor stop, replacement or model replay. The amended
  postprocessor has started private grading only after that terminal cohort.
  Complete usage, scored quality, uncertainty and independent MEM archive
  recovery remain unverified; T062/T086 are not complete.

  Subsequent terminal evidence completes execution/report/recovery, NOT target
  acceptance: all 76 attempts/grades and normal usage are present; measured TOTAL
  saving is 5.299941045%, full tasks 13/38 versus native 12/38, and the 20% gate
  fails. All 590 runs recover independently from MEM (3,033 events, 304 full
  streams, 76 candidates/grades/public vaults); all 76 original requests,
  including twelve chunked dispatches, bind to the frozen grader and candidate.
  No model or grade outcome is retried. This execution task is complete with a
  negative efficacy result; T062 and the overall goal remain open unchanged.

- [x] [T087] Diagnose the completed v3 confirmation's failed token target before
  changing the candidate. FR-020/026; SC-012/013. Preserve the measured 5.299941045%
  TOTAL-input saving and 12/38 native versus 13/38 AtMem full passes, all repository
  regressions, uncertainty and the original build. Audit every original trace,
  query binding and initial pack; replay all nineteen retained generations with
  the frozen installed packer and inspect generic lexical/graph nomination.
  Distinguish observed evidence from causal hypotheses. No model/grade replay,
  success-only filtering, repository/issue-specific fix or new confirmation
  claim. Existing archive/recovery work continues independently. Any candidate
  informed by this cohort must treat it as reused development evidence and
  requires separately disclosed confirmation before meeting T062.

  Actual terminal evidence: all 76 traces audited; all 38 query/issue bindings
  match; installed packer hash equals the inspected local source; all nineteen
  frozen packs reproduce byte for byte, with no model or grading replay. The
  lexical inspection exposes `proper`/`rated` substring promotion into unrelated
  property/decorator names. Low Code MCP uptake and irrelevant initial source
  are observed; their causal contribution to the token result is not established.
  The failed target and all repository regressions remain reported and archived.

- [x] [T088] Correct generic compound-identifier nomination under
  `strict-identifier-ranking-v1.md`. Depends T087; FR-020/026, SC-012/013.
  Require complete bounded segmentation of compact name parts, not multiple
  arbitrary substrings; preserve exact/underscore/camel matches, source/scope/
  freshness/budget/receipt checks and frozen v3 evidence. Add positive/negative
  and no-spurious-context fixtures, run relevant regressions, and inspect packs
  on the explicitly reused corpus before a separately frozen model comparison.
  Do not claim the 20% objective from static tests or an old-candidate rerun.

  Full counterfactual replay is terminal: all nineteen original packs reproduce;
  five corrective packs change. Thirty-five focused and 208 relevant regression
  checks pass (overlapping groups). Property/decorator substring promotion is
  removed, but some resulting roots remain irrelevant. No token or quality gain
  is established and the installed scored baseline is unchanged.

- [x] [T089] Enforce symbol ownership of syntax definitions under
  `typed-query-nomination-v1.md`. Depends T088; FR-020/026, SC-012/013.
  File/module/reference facts anchored at a definition line must not acquire
  executable/class status or explicit-symbol priority. Preserve their graph
  presence and truthful source anchors, complete-generation validation, scope,
  source integrity and budgets. Add a filename/class collision regression and
  run existing packing/context gates; no benchmark-name special cases.

  Only CodeSymbol facts bind syntax definitions or explicit-symbol priority.
  Non-symbol facts remain queryable and may emit source-anchor labels. Thirty-
  five packing/context gates pass, including the new filename/class collision
  and existing source/scope/byte-budget checks. This is not a token-saving result.

- [x] [T090] Recognize observed, unambiguous Python query import aliases under
  `typed-query-nomination-v1.md`. Depends T089; FR-020/026, SC-012/013.
  Parse supported query code as data, preserve ordinary references, avoid guessed
  aliases and reject conflicts/rebindings. Add positive, doctest, conflicting,
  reassignment and non-execution fixtures. Inspect the combined candidate on all
  nineteen reused generations before any separately frozen model comparison.
  No source, model, test or outcome from the frozen v3 run may be overwritten.

  Forty-four focused and 217 relevant regression checks pass (overlapping).
  Combined pack-only replay completes all nineteen identities, reproducing the
  frozen baseline and changing eight candidate packs. An observed module alias
  now nominates ParametricEllipsoid rather than an environment-report helper;
  this is localization evidence, not a token/quality result. The corrective
  packer hash is 159e4b0f1c52c3bd0752d38ddaa5e2764927b4daa39adc400baeaeddb2d85042.

- [x] [T091] Build and qualify the separate single-file corrective preview under
  `corrective-development-screen-v1.md`. Depends T090; FR-020/026, SC-012/013.
  Bind the complete e8d98dad source manifest; allow only packing.py to change,
  retain all dependency/builder identities, verify installed bytes and ordinary
  user startup, and run the real source/scope/freshness qualification. No owner
  upgrade, old-wheel replacement, model call or release claim.

  Separate wheel f1f92fe34f2d4c5ed2413ad6445cfdeb54fbb616cdba7f91777487189dcab7a2
  verifies the exact single-file delta, installed bytes, eleven unchanged
  distributions and ordinary-user startup. Terminal real-source qualification
  external-windows-typed-query-qualification-v1-20261018-owned-state-continuation
  passes all five identities with zero model calls: foreign-scope denial,
  exact encrypted bundle recovery, freshness withholding, valid audit and
  uid/gid 1000 Code MCP. Original transport, helper-import and Git-ownership
  setup failures remain recorded. Continuations reuse verified existing source
  and extraction state; no model/grade outcome is retried or old build changed.
  Broader replay/knowledge suite passes 710 checks; subsequent overlapping
  corrective/spec fixtures pass 31. This closes qualification, not efficacy.

- [x] [T092] Freeze and execute CD1's fresh matched 38-attempt development screen
  after T091, preserving every declared issue and unchanged caps/tests/source
  authority. Record full streams/candidates, grade only after all attempts,
  retain full requests with bounded chunks, and report all metrics and failures.
  This is reused-data development, not independent confirmation or T062
  acceptance; a selected candidate still requires fresh confirmation.

  Full prospective preparation, execution-lock/model and postprocessing
  controllers are now retained and dispatched under the corrective-development
  run prefix. Installed qualification is terminal and positive; fresh staging
  has five of nineteen paired blocks qualified at the current checkpoint.
  Thirty-eight actual MCP/sandbox checks, descendant containment and the exact
  execution lock still gate inference. No model or private grade is complete
  at this checkpoint. All stage/model/grader programs retain the previous
  source, authority, tools and budgets; only the declared fresh scope/count/
  schedule and corrective wheel differ. T092 stays open pending full results
  and independent recovery, regardless of development efficacy.

  Preparation subsequently finishes with all nineteen blocks, all 38 MCP and
  all 38 sandbox controls qualified. Descendant containment qualifies on its
  distinct scope. The exact pre-inference lock is frozen and inference is
  live under external-windows-corrective-development-models-v1-20261018;
  thirteen of 38 attempts are captured at this checkpoint. An explicit
  read-only usage audit verifies all first twelve retained model results have
  normal receipts, with no private grades inspected or model repeats. Archive
  and separate-Mac transfer/recovery are queued, not verified. T092 stays open.

  CD1 inference subsequently terminates zero with all 38 fixed attempts captured,
  no supervisor stop, outcome retry or schedule change. Private grading begins
  only after that terminal cohort; its first four attempts return without a
  harness exception. This is not a task-pass count. Full matched accounting,
  latency/uncertainty, actual public-log recovery and standalone MEM request
  verification remain required. No token-target or T062 acceptance follows.

  All 38 private results and usage receipts are subsequently verified. SSH loss
  leaves fourteen parent summaries missing; exact retained dispatch/controller
  recovery appends those only, preserving the existing 24 and invoking no model
  or grader. Report/public recovery completes: TOTAL input 3,914,549 native versus
  3,549,824 corrective, 9.317165272% lower, full passes 6/19 each. The exact 20%
  gate fails, and Xarray regresses. Full latency/uncertainty accounting is in
  RandD/2026-10-18-corrective-development-comparison.md. Original archive setup
  stops with empty destinations; guarded retained-helper export recovery is
  underway. T092 remains open for independent recovery; T062 stays open for
  efficacy and fresh confirmation. No model/private-grade outcome is repeated.

  Terminal independent recovery now closes this execution task with a negative
  efficiency result: 332 runs, 1,660 events, 152 complete streams, all 38
  candidates/private grades/public vaults. All 38 original requests verify,
  including six chunked requests and 401,072,102 canonical dispatch bytes;
  original vault access is disabled and no model/private grade is repeated.
  Collection digest c46f9d9cf5cf792882b92c6533deb50815cff75ba5943629db403a2b6938c6d7.
  MEM archive is corrective-development-protected-20261018; keys remain internal.
  T062 and the overall objective remain open: 9.317165272% is below 20%, and
  reused development evidence cannot satisfy fresh confirmation.

- [x] [T093] Audit every retained CD1 model trace against its frozen initial
  context before selecting another candidate. Depends T092; FR-020/023/026,
  SC-012/013. Read only the independently recovered archives in a fresh process
  with original-vault access denied. Verify all 38 issue/arm/usage bindings;
  report native exploration, Code MCP uptake, exact repeated outputs and
  nontrivial initial-source-text overlap as descriptive byte proxies, never
  model attention, causal attribution or tool-level token accounting. Preserve
  all failures and the 9.317165272% negative target result. No new inference,
  grader execution, product change, subset selection or confirmation claim.

  Fresh-process archive-only audit completes all 38 original cells and validates
  each normal CLI usage receipt against the unchanged comparison. Shell-command
  counts are 141 native versus 120 tools; returned bytes 601,343 versus 419,303;
  exact repeated output >=1 KB is 9,795 versus 5,602 bytes. Tools make one Code
  MCP call. Nine tools attempts return nontrivial text also present in their
  initial pack (7,175 summed per-attempt distinct line bytes). Those are byte
  proxies, not attention, same-file redundancy or token attribution. No model,
  grade or product change occurs. Eleven overlapping audit/inventory fixtures
  pass; full derived case rows remain protected under the CD1 trace-audit run.

- [x] [T094] Correct layout-derived query nomination under
  `query-layout-ranking-v1.md`. Depends T093; FR-020/023/026, SC-012/013.
  Preserve the frozen CD1 source before editing; downweight only subsection-
  heading-only terms when substantive body text exists, retaining literal
  fenced code, titles, standalone headings and existing explicit references.
  Require exact bounded source delta, parser/ranking/authority fixtures and
  an archive-only all-nineteen baseline/counterfactual replay. Keep every pack
  and failure, no model/grader call, task-name rule or efficacy claim. Any
  further installed/model experiment requires its separate prospective gate.

  The unchanged CD1 source and protocol are retained before editing. The exact
  helper/query-weight-only delta passes. Archive-only replay reproduces all
  nineteen old packs byte for byte and retains all counterfactuals: four packs
  change, all in Pylint, but several roots remain unrelated. No model comparison
  is justified by this correction alone. Seventy-one focused gates and the
  broader 704-check replay/knowledge group pass (overlapping). The scored wheel
  is unchanged; no token, task or installed-preview benefit is claimed.

- [x] [T095] Eliminate prose-as-function-call promotion under
  `query-reference-ranking-v1.md`. Depends T094; FR-020/023/026, SC-012/013.
  Preserve explicit underscore/dotted references, immediate call notation and
  parsed actual spaced calls in whole-query/inline/fenced Python and doctests.
  Prose-parenthesis whitespace must not alone create maximum-priority symbols.
  Parse only; execute no query code. Capture the complete source ancestry before
  editing and run the same all-nineteen archive-only baseline/counterfactual
  replay through a reusable guarded runner. No benchmark-name rules, model or
  grader call, installed qualification or efficacy claim follows.

  Completed archive-only source-chain replay reproduces all nineteen original
  CD1 packs. Five combined counterfactual packs change and all fit 4,096 bytes;
  the false `name` call is removed, although the replacement lexical root is
  still not the constructor. This is not sufficient localization evidence by
  itself. All original scores remain unchanged. Eighty-four focused and 709
  broader replay/knowledge checks pass (overlapping); Python 3.10 grammar
  passes. No new solver, grader or installed-preview call is made.

- [x] [T096] Nominate existing authorized symbols from explicit source-URL
  line hints under `query-source-location-v1.md`. Depends T095; FR-020/023/026,
  SC-012/013. Parse hints without network I/O; bind only exact authorized
  source-path suffixes and in-range lines, prefer the innermost existing syntax
  symbol, and reject traversal, credentials, malformed or unmatched hints.
  Preserve source/authority/freshness and distinguish a query hint from proof
  about a revision. Record the complete source chain and all nineteen static
  counterfactuals with the reusable diagnostic runner. No model, grader,
  download, installation or efficacy claim is authorized by this task.

  Terminal archive-only replay reproduces all nineteen original CD1 packs;
  six combined counterfactuals change and every candidate fits 4,096 bytes.
  The original Pylint-7277 URL now nominates the existing modify_sys_path
  definition at pylint/__init__.py:80–105 instead of a configuration loader.
  This is source-localization evidence, not measured benefit. Ninety-eight
  focused and 723 broader gates pass (overlapping). Candidate source is
  004a4ff9f66843206456f28d2bd08b59c09196ecee16c88a25b51dc85fa62020.
  The recorded runner reuses explicit profiles and bounded stdin transport;
  no original vault, solver or grader is used in the fresh reader.

- [x] [T097] Build and qualify the separate query-nomination preview under
  `query-nomination-development-screen-v1.md` after T096. FR-020/023/026;
  SC-012/013. Reuse the frozen full-source builder, replace only the recorded
  packer, verify all installed bytes/dependencies/ordinary-user behavior and
  replay the actual candidate packs in the installed Windows environment.
  Run fresh real-source scope/freshness/audit/encrypted-bundle/MCP controls;
  preserve failures, no owner install or old-wheel replacement. Distinguish
  Mac-produced static evidence from independently executed Windows controls.

  Separate Windows-hosted WSL preview build is terminal and source-qualified:
  wheel c3e6bb211082b6f962869ed4a60945cb3c90d99c784ce7629d423045b8190326,
  packer 004a4ff9f66843206456f28d2bd08b59c09196ecee16c88a25b51dc85fa62020.
  The frozen-source builder verifies all installed source bytes, the same eleven
  distributions and uid/gid 1000 helper execution. Full Mac static evidence is
  retained with its actual origin, not reported as a Windows rerun. Fourteen
  preview/build/source-guard/inventory fixtures pass (overlapping prior groups).
  No owner install or old wheel is changed; zero models run. T097 stays open
  until actual installed real-source replay and fresh scope/freshness/audit/
  encrypted-bundle/MCP controls are terminal.

  Those remaining gates subsequently complete positively: actual installed WSL
  packing.py produces all nineteen recorded candidate packs byte for byte;
  all five fresh repository controls pass foreign-scope denial, original source
  presentation, unchanged extraction reuse, exact encrypted generation-bundle
  recovery, stale-source withholding/restoration, valid audit and uid/gid 1000
  MCP. No model is called and no owner installation is changed. Protected roots:
  external-windows-query-nomination-installed-replay-v1-20261018 and
  external-windows-query-nomination-qualification-v1-20261018. The 759-check
  broader regression group passes; subsequent focused profile/controller
  fixtures also pass and overlap prior checks. This closes qualification only,
  not efficacy. Fresh all-case MCP/sandbox/secret-file and descendant controls
  remain prerequisites of the separately locked CD2 scoring run.

- [x] [T098] Execute CD2 only after T097, under the prospective fixed 38-attempt
  matched protocol and unchanged model/tools/test/budget/authority gates.
  FR-020/023/026; SC-012/013. Freeze all exact sources and bindings before
  inference, preserve every scheduled case, grade after all model captures,
  report full paired quality/token/latency/harm/uncertainty accounting, and
  independently recover all full requests and evidence from MEM. This is reused
  development selection; T062 still requires untouched confirmation.

  Fresh CD2 preparation is dispatched under
  external-windows-query-nomination-development-preparation-v1-20261018.
  Exercised CD1 stage/readiness/sandbox/process/lock programs are reused with
  declared fresh run/storage identities, prospective seeds and the qualified
  candidate build. Installed qualification and all nineteen installed pack
  matches gate entry. The controller stops before inference and checks each
  terminal phase; no prior native score or candidate outcome is reused.
  Model scoring, comparison and independent archive recovery remain open.

  Subsequent actual observer verifies all nineteen paired blocks, all 38 MCP
  controls and all 38 sandbox controls qualified; descendant containment also
  completes positively. Exact private-grader and initial-source locking is in
  progress. Broader replay/knowledge regression: 765 passed in 58.05 seconds.
  No model outcome or efficiency improvement is claimed at this checkpoint.

  Preparation subsequently exits zero: all five phases terminal, all nineteen
  private graders and all 38 initial sources locked. Separate execution is
  submitted under external-windows-query-nomination-development-execution-v1-20261018.
  It uses only the exact retained model/support/postprocessing sources from
  preparation, never regenerates the scored candidate or reuses prior scores.
  No scored result is claimed yet; T098 remains open for full execution,
  comparison and independent recovery, and T062 for untouched confirmation.

  The original model execution subsequently reaches its terminal 38/38 captured
  attempts, with no stopped terminal and no model replay. Private postprocessing
  now follows that full-cohort terminal. A separate archive waiter retains its
  full implementation before waiting for comparison/public recovery; exact-path
  MEM transfer and a fresh archive-only full-request reader are implemented and
  fixture-tested but not yet executed. No token/pass result or target acceptance
  is claimed until the full report. The candidate hash remains unchanged.

  Full comparison/public recovery subsequently completes: TOTAL input 5,110,437
  native versus 3,769,879 candidate (26.231768438% lower), but full-task passes
  are 8/19 versus 7/19. The quality condition fails, so the combined 20% fallback
  is not accepted. All 38 normal usage receipts and grades are present; no
  model/grade outcome is rerun. All 310 required runs export, encrypted MEM and
  internal-key copies finish, and the fresh Mac archive-only reader is live.
  T098 remains open until that reader verifies the complete cohort and all
  original requests. The full negative result and latency/uncertainty tables are
  in RandD/2026-10-18-query-nomination-development-comparison.md.

  Independent Mac recovery subsequently completes all 310 runs, 1,597 events,
  152 full streams and 38 candidates/private grades/public vaults. All 38
  original requests verify, including six chunked requests and 401,073,882
  canonical dispatch bytes, with original-vault access denied and zero outcome
  retries. Collection digest:
  6462f65d591f2b8a186e6d743bfb67aa676836de2856e13ec55f09d86842e247.
  Encrypted archive is query-nomination-development-protected-20261018 on MEM;
  keys remain internal. This closes execution with a negative combined result,
  not the efficiency goal. T062 stays open: quality fails and fresh confirmation
  is absent. T099 may now inspect the independently recovered cohort.

- [x] [T099] Diagnose CD2's failed combined gate only after T098's independent
  recovery. FR-020/023/026; SC-012/013. Reuse the all-38-case archive-only trace
  audit with exact original usage bindings, source-pack overlap, native commands
  and Code MCP counts; retain the full reader and every derived case. Inspect
  the five discordant pairs and check any proposed mechanism across the rest
  of the cohort, not only a favorable subset. Distinguish source localization,
  patch behavior, policy refusal and stochastic variation; byte proxies and
  scores alone cannot establish causality. Preserve the 26.231768438% saving /
  7-versus-8 quality failure. No model/test rerun, product edit, denominator or
  threshold change follows from this diagnostic. Any next candidate requires
  a generic evidenced defect, separate prospective gate and fresh confirmation.

  The unchanged all-case descriptive audit subsequently completes all 38 traces
  from MEM with operational-vault access denied and every normal usage receipt
  bound to the original comparison. Shell commands are 165 native versus 134
  candidate; returned bytes 621,432 versus 454,990; exactly repeated output
  >=1 KB is 9,332 versus zero; Code MCP calls are zero in both arms. Ten candidate
  attempts return source text matching their initial packs (7,961 distinct bytes
  summed per attempt). Those are proxies, not causal attribution. All five
  discordant pairs pass source authority and preservation checks; the three
  candidate-only losses are target-fix failures, not governance refusals. T099
  stays open for direct trace/patch inspection and cross-cohort mechanism checks.

  Direct archive-only review subsequently covers all 38 repairs and retains
  complete original events and actual source diffs for all five discordant
  pairs. The two Pylint losses edit the wrong parsing/filtering layer despite
  finding relevant files; Seaborn uses the requested function but implements
  incorrect bounds. Flask's successful candidate uses iterative public-test
  feedback; Xarray's successful candidate fixes a different layer from its
  initial pack. These observations do not isolate a memory-caused effect.
  A distinct all-case feedback audit verifies 39 public calls: 11 execute,
  19 fail request validation and nine return unavailable. Exact original
  selector replay identifies a generic defect: both legitimate Xarray-3812
  nested-root selectors are rejected. Seventeen source-path selectors are
  correctly rejected. Preserve all scores; T100 repairs only the real defect.

- [x] [T100] Repair registered public-test directory ancestry under
  public-feedback-selector-v1.md after T099. FR-020/023/026; SC-012/013.
  Accept canonical descendants of any registered public-test directory while
  keeping explicit .py roots exact-only. Preserve every path/node/command/
  source/private-data and resource boundary. Test nested roots, sibling-prefix
  attacks, traversal, file-as-directory attempts and existing worker bootstrap.
  Do not modify a frozen worker or rerun an outcome. Any future runtime/study
  must separately freeze and qualify the corrected public worker. This does not
  complete the efficiency goal or replace the required product relevance work.

  The bounded source repair and 46 public-worker/bootstrap/review/inventory
  checks pass. Replaying all 39 original selectors through the old and corrected
  pure validators changes exactly the two legitimate Xarray-3812 requests from
  rejected to accepted; seventeen source-path mistakes stay rejected, and no
  prior acceptance is lost. Both validator sources and all original selector
  results are protected. No old worker or model/private grade is run or replaced.
  This closes the source-level repair only; future runtime/study qualification
  must explicitly include the corrected helper in both server and worker.

- [x] [T101] Correct static literal anchoring and named-target precedence under
  query-literal-anchors-v1.md after T100. FR-020/023/026; SC-012/013. Freeze the
  complete CD2 source before editing. Nominate only existing authorized symbol
  targets from bounded explicit literal keys, direct same-module callable
  registries and immediate class declarations; reject dynamic/unresolved/
  rebound or overly ambiguous mappings. Do not let revision-unverified URL
  lines outrank a different explicit current symbol in the same file. Preserve
  scope, source truth, typed facts, budgets and graph authority. Require exact
  bounded source delta, unrelated positive/negative fixtures and all nineteen
  original/counterfactual archive-only pack replays. No model/test execution or
  efficacy claim; installed/scored work requires another prospective gate.

  Complete source/protocol is retained before editing; exact helper/bindings-only
  delta verifies against 004a4ff9. All nineteen original CD2 packs reproduce byte
  for byte from MEM, three counterfactuals change, and all stay within 4,096 bytes
  (maximum 4,091). New Pylint roots identify the option-owning class and registered
  transformer; Flask's explicit current symbol outranks a conflicting stale
  line hint. Source-only result, not repair/token benefit. Broader suite passes
  785 checks in 82.24 seconds; focused checks overlap. Historical guard fixture
  is scoped to its original contract while still rejecting the new binding;
  the original guard and old evidence are unchanged. Candidate SHA-256 is
  2d8b53e65f4b3c06628e191bb083ba95064f9fd51d5578c915ba424d68938a97.
  Full details: RandD/2026-10-18-literal-anchor-correction.md. No new installed
  candidate, inference, private grade, owner installation or release is claimed.

- [x] [T102] Build and qualify the separate literal-anchor preview under
  literal-anchor-preview-v1.md after T101. FR-020/023/026; SC-012/013. Reuse the
  frozen full-source builder with the exact single-file candidate, verify all
  installed bytes/dependencies and ordinary-user literal-helper execution,
  reproduce all nineteen packs in the actual installed runtime, and run fresh
  real-source scope/source/freshness/audit/encrypted-bundle/MCP controls. Preserve
  prior artifacts and failures; no owner upgrade, model/private-test call or
  release. Explicitly separate the benchmark-only public-selector repair and
  its future server/worker qualification from product-wheel qualification.
  New scored work requires its own fixed matched protocol and untouched
  confirmation remains required before the full goal can be accepted.

  Terminal installed qualification is positive: separate wheel
  3b56928a20c07fdbddcca64167ad19efdb80db396e41637d5e837b9e9958ad65
  verifies the exact single-file source delta, unchanged dependencies and
  ordinary-user literal-helper execution. The installed package reproduces all
  nineteen candidate packs byte for byte. All five fresh real-source controls
  qualify, including scope denial, source/freshness, encrypted bundle, audit and
  ordinary-user MCP. Both original control submissions exit zero; no inference,
  private grading, owner installation or publication occurs. Protected roots:
  external-windows-literal-anchor-installed-replay-v1-20261018 and
  external-windows-literal-anchor-qualification-v1-20261018. This proves product
  qualification only, not improved task quality or token savings.

- [x] [T103] Qualify the repaired public-selector profile against every retained
  CD2 server/worker template, then in fresh public-test runtime controls before
  any further scoring. Depends T100/T102; FR-020/023/026; SC-012/013. Require an
  exact validator-only delta in both roles, preserving outer programs, unrelated
  modules, private graders, budgets and original evidence. Check actual nested
  roots/node selectors, source/traversal rejection and unchanged/candidate
  public-test behavior. Archive-only template validation is not runtime proof;
  retain both separately. No old model/grade outcome is retried, and subsequent
  matched scoring needs its own prospective fixed protocol.

  Archive-only template validation subsequently passes all nineteen identities
  and 38 programs. Complete original/corrected programs and exact hashes are
  protected under external-windows-public-selector-template-audit-v1-20261018.
  No archived template executes and no original outcome is repeated. Runtime
  controls remain open. Fresh staged readiness will exercise nested Xarray
  roots with node selectors plus source-path/traversal rejection in both arms.

  Subsequent runtime qualification is terminal and positive. All 38 fresh MCP
  cases pass public candidate tests and source/traversal rejection; Xarray's
  cases use nested registered roots with explicit node selectors. A separate
  fresh unchanged/candidate control runs the original Xarray-3812 selector:
  xarray/tests/test_options.py returns 16 passed, one expected failure, exit 0;
  the supplied nested canary patch returns three passed, exit 0. Both host and
  sandbox use the exact corrected programs, original staged files are unchanged,
  and no model/private grader runs. Protected supplementary run:
  external-windows-literal-anchor-development-public-selector-runtime-v1-20261018.

- [x] [T104] Execute the separately frozen CD3 matched study under
  literal-anchor-development-screen-v1.md after T102 and T103 runtime gates.
  FR-020/023/026; SC-012/013. Stage all nineteen reused issues in fresh scopes,
  qualify all 38 MCP/sandbox cases and containment, freeze exact source/grader/
  schedule bindings, run each of 38 attempts once, then grade/report/recover
  complete encrypted evidence independently from MEM. Preparation may stage
  and qualify T103 before any inference; a failed gate stops model execution.
  Preserve 50%/exact 20% plus equal-or-better full-task quality and governance.
  This is development selection, not untouched confirmation or T062 completion.

  Fresh preparation subsequently exits zero: all nineteen paired stages,
  38 actual MCP controls, 38 sandbox controls and descendant containment
  qualify. All 38 initial sources and nineteen frozen private graders are
  locked. Separate execution is submitted under
  external-windows-literal-anchor-development-execution-v1-20261018 and reads
  the exact retained model/support/postprocessing sources from preparation.
  No prior native outcome is substituted; scoring and independent recovery
  remain open. T104/T062 are not complete.

  A subsequent read-only observer verifies the original execution is in its
  models phase, with the first native/candidate pair captured and no supervisor
  stop. The separately submitted archive waiter retains its full source and
  waits for complete comparison/public recovery; it has no model/grader launch
  path. No partial efficacy result is inspected or claimed. All 27 focused
  preview/profile/selector/archive/inventory checks pass (overlapping the
  broader suite); actual archive export, MEM transfer and independent recovery
  remain required after the original cohort terminates.

  Subsequent complete comparison is negative: all 38 normal receipts/private
  grades and public recoveries are present, with zero supervisor stops. Native
  uses 4,081,577 TOTAL input versus candidate 5,138,670 (25.899131635% MORE),
  and full-task passes are 8/19 versus 5/19. Both input and quality gates fail;
  no candidate promotion or confirmation is authorized. Original execution
  exits zero, without outcome retries. Full latency/repository/partial/harm/
  uncertainty accounting is in
  RandD/2026-10-18-literal-anchor-development-comparison.md. Independent archive
  recovery remains open before T104 can close; T062 remains unachieved.

  Owner subsequently requests stopping after the current evidence collection.
  Finish only the existing MEM copy and independent verification, record the
  proof, then pause the goal. Do not proceed to diagnosis, product changes,
  training or another scored study. Goal acceptance remains unachieved.

  Independent recovery subsequently completes: 311 runs, 1,601 events, 152
  full streams, 38 candidates/private grades/public vaults. All 38 original
  requests verify, including six chunked requests and 401,072,082 canonical
  dispatch bytes; original-vault access is denied and no model/grade outcome
  is repeated. Collection SHA-256:
  714efebda0662caf0f0cce730de4ec57d8494185679ff2d72e5f4df9cd78dbbc.
  Encrypted MEM archive is literal-anchor-development-protected-20261018;
  keys remain internal. T104 closes as completed execution with a negative
  combined result, not goal achievement. Stop here under the owner's instruction;
  no diagnostic, product change or next benchmark is dispatched.

- [x] [T105] Freeze and verify the forty identity-only feasibility candidates
  in unexposed-confirmation-pool-v4.md before inspecting CD3 quality/token
  outcomes. FR-020/023/026; SC-012/013. Reuse pinned catalog/blob validation,
  exclude all thirteen previously exposed repository groups, retain every
  selected task/recipe and metadata failure in protected evidence. No gold,
  test, hint, problem-statement, image or solver fetch/execution in this task.
  Metadata success is not environment eligibility or confirmation. Subsequent
  confirmation requires terminal positive CD3, independent recovery, all forty
  qualification outcomes and a separate exact twenty-issue execution lock.

  Terminal metadata-only preflight verifies all forty selected task/recipe
  records, with zero environments qualified and zero model calls. Only
  Dockerfile/task.yaml content is opened; all thirteen prior repository groups
  are excluded. Selection digest:
  81a5d3a6357ed68c6a804ef3f0b38211abebcaa9360782ab18cffe5f35250235.
  Protected run external-unexposed-confirmation-pool-v4-preflight-20261018
  retains the complete catalog, frozen ordering, exact blobs and every result.
  Three selection/refusal fixtures and eight overlapping inventory checks pass.
  Metadata completion is not confirmation, environment eligibility or T062
  acceptance. CD3's original execution continues unchanged.

- [ ] [T106] Only after positive complete T104 plus independent recovery,
  qualify all forty frozen T105 feasibility candidates under
  unexposed-confirmation-pool-v4.md. FR-020/023/026; SC-012/013. Pin registry,
  source/base/parser and dependency identities; use explicit operator-owned
  source/public-test registrations. Preserve every image/resource/source/
  parent/reference/public/proposal/authority failure and old evidence. Select
  only the first four fully qualified candidates per repository; require all
  twenty identities. No new product tuning, model outcomes, favorable subset,
  relaxed caps, owner installation or disk cleanup. Eligibility alone is not
  task success or confirmation.

- [ ] [T107] After T106, freeze the exact selected candidate, twenty tasks,
  two repeats, eighty native/candidate cells, schedule/cluster seeds, complete
  source/model/helper/grader/configuration bindings and actual scope/MCP/
  sandbox/containment gates before inference. FR-020/023/026; SC-012/013.
  Execute once with unchanged model, resource, authority and quality/token
  gates; grade only after all eighty captures. Report complete paired totals,
  full/partial/harm/latency/uncertainty and independently recover every original
  request/stream/candidate/grade/public record from encrypted MEM archives.
  Never retry until passing. T062 is achieved only if this untouched cohort
  satisfies >=50% TOTAL-input saving or exact >=20% fallback, equal-or-better
  full-task passes, governance and full evidence; incomplete/failed confirmation
  must remain explicitly incomplete/failed.

## Phase 10: Convergence

Owner request 2026-10-18: close pinned upstream indexing and coding-MCP depth
gaps. This is product implementation, not resumption of the paused efficiency
goal or authorization for a release or another scored benchmark.

- [x] [T108] Expose all eight pinned structural operations through additive typed `code_search` MCP arguments in `atmem/knowledge/code/mcp.py`, preserving legacy compact search, bounded full-result traversal, scope and delivery freshness. FR-020, FR-024; SC-008, SC-012 (partial). 54 focused MCP/query tests pass; installed-platform and extraction coverage are separate gates.
- [x] [T109] Expand the richer source policy to upstream language/manifest inputs and incorporate pinned insight projection without plaintext extraction in `atmem/knowledge/projections.py`, `atmem/knowledge/code/extractor.py` and `tools/import_code_knowledge.py`; retain unsupported and secret exclusions. FR-017–FR-019; SC-008, SC-012 (partial). Installed v4 control admits 77 upstream source files and materializes 35 findings; Ruby/PHP virtual coupling and Ansible directory-role regressions pass. Frozen failures retained; no blanket language/framework claim.
- [x] [T110] Publish repository receipt and exact generation-delta metadata for real `delta` queries in `atmem/knowledge/projections.py` and `atmem/knowledge/code/queries.py`, preserving encrypted atomic publication and old generation reads. FR-019, FR-020, FR-026; SC-008, SC-012 (partial). Actual edit/reindex/rename reaches generations 1/2/3 with zero old-path hits; unchanged and restricted/legacy-read controls pass. Source-bound count semantics are documented.
- [x] [T111] Verify upstream/AtMem extraction and all eight MCP operations with real pinned worker outputs, source edits, multilingual source inputs and security/compatibility regression tests; update `docs/atmem-code.md` and the capability register with exact remaining gaps rather than blanket parity. FR-017, FR-018, FR-020, FR-027; SC-008, SC-012, SC-013 (partial). Installed macOS CPython 3.12.12 + Linux/aarch64 worker: 422 objects / 646 relationships, all eight pinned query differentials and all eight independent stdio calls pass. Broad suite 316 passed; final overlapping focused suite 100 passed, including five-hop traversal. Native Windows, exhaustive framework, source/binary/SBOM, normal host automation and broader CK gates remain open in `RandD/2026-10-18-code-index-mcp-depth.md`; no release or efficacy claim.

## Phase 11: Convergence

Owner request 2026-10-19: assess the five user benefits, complete bounded missing
product paths, and package an installable preview. This does not resume benchmark
optimization or authorize registry publication. Scoped review: FR-017–FR-028,
SC-008–SC-013, three CK scenarios, six integration/packaging decisions and eight
constitution principles; five high-severity partial gaps below. Broader open
host/platform, dependency/SBOM, full reconstruction and human usability gates
remain open rather than being duplicated or marked complete.

- [x] [T112] Package pinned extractor build resources and add authorized persistent local-image configuration plus portable read-only MCP configuration generation; preserve explicit build/network/enablement and no worker dependency in the base install. FR-018/020/027, SC-008/012 (partial). Resources and notices verified in wheel/installed bytes; actual configured worker and generated MCP pass on public Click. No full platform/worker provenance claim.
- [x] [T113] Add a product-owned explicit command producer using existing signed execution/experience contracts, bounded outputs/deadlines, secret screening, source/environment checks and existing governed admission. Record failures/unknown outcomes without claiming a verified fix; do not execute model-supplied commands through read-only MCP. FR-021/028, SC-009/012/013 (partial). Eleven producer/inspection/delivery controls and actual installed CLI formation pass; normal per-host automatic outcome capture remains unqualified.
- [x] [T114] Expose authorized bounded experience browsing and current applicability/withhold reasons through shared CLI/dashboard and a read-only Code MCP view; keep private lanes, evidence privilege, source links and existing correction/deletion semantics. FR-022/024/026, SC-010/011/012 (partial). Shared services, explicit audited output inspection, scoped MCP and installed forget control pass; browser/accessibility and human usability gates are not closed.
- [x] [T115] Revalidate graph-bearing replay packages against current source before returning them; test stale replay, disabled behavior, shared-agent experience recall and changed-anchor withholding with the product producer and shared budget. FR-019/022/023, SC-010/012 (partial). Graph-only stale retry now returns empty context with withheld assurance; installed shared-scope handoff/anchor controls pass, not a real multi-CLI model trial.
- [x] [T116] Build wheel/sdist, verify packaged resources/notices and a fresh installed command-to-experience-to-recall/inspection journey, and record artifact hashes, actual platform coverage and remaining blockers in the user guide and readiness report. Do not publish or imply full parity/benefit/host qualification. FR-026/027/028, SC-012/013 (partial). Private preview built/installed with eight packages total; 346 package files verified, 1348 objects/2526 relations and eleven installed MCP replies. See product-readiness-20261019.md; metadata remains 2.3.8, no registry publication.

## SWE-bench preparation correction and three-provider investigation

Owner request 2026-10-19; see `swebench-preparation-corrections-20261019.md`.
This does not resume the old paused Click optimization campaign.

- [x] [T117] Align bounded source/artifact/storage/query envelopes, root rollup mapping and index-time work; qualify all five selected repository families through an installed product and actual MCP, retaining remaining failures. Five public snapshots pass actual installed MCP context/architecture checks; 358 affected tests pass. This is preparation qualification, not a new solver score; see RandD/2026-10-19-swebench-preparation-and-cognee.md.
- [x] [T118] Add a separately pinned automatic-context benchmark mode with integrity/budget checks, prompt retention and separate delivered-context/tool-call accounting; preserve original pilot outcomes. Implementation and contract/tool checks complete; actual comparative model dispatch remains under T120.
- [x] [T119] Prepare actual pinned upstream Cognee for the same benchmark executor and retain a fair no-memory/AtMem/Cognee comparison, with provider/delivery configuration explicit. The frozen five-task equal-optional study completes: native/AtMem 5/5; Cognee 4/4 graded plus one preparation deadline. Four common pairs have complete receipts; neither graph is queried. AtMem uses more input than native, while measured setup is substantially faster than Cognee. All six runs/fourteen model streams recover independently from encrypted MEM archives, with original-vault access denied. See RandD/2026-10-19-swebench-threeway-optional-results.md; this is not retrieved-knowledge benefit or untouched confirmation.
- [x] [T120] Iterate on a designated validation cohort and freeze before a separate paired confirmation; report task completion, complete usage, cold/warm latency and all regressions. The owner subsequently authorized benchmark cleanup and full three-provider execution under `swebench-threeway-20261019.md`; preserve earlier stops and the 48 GiB guard. Five capability claims require their separate installed evidence, not inference from cold-start scores. Both repetitions complete: native/AtMem 10/10; Cognee 8/8 graded plus two preparation timeouts; all 28 streams independently recover. Complete common-task input is 103065/178321/115087, so the token-saving goal fails. Separate first/warm query controls retain all four matched sources and identical old/new AtMem results. See RandD/2026-10-19-swebench-confirmation-results.md; completing this bounded study does not complete SC-013 or the broader efficiency/release goals.
- [x] [T121] [P] Remove redundant normalization/serialization of shared extraction metadata during one authorized query-snapshot construction, without retaining a cache across calls or removing any metadata/filter indexes. Keep the pinned incorporation reproducible and notices intact; require all-eight-operation byte equivalence, metadata-filter/mutation/exception/isolation regressions, installed qualification and separate query timings before a performance claim. FR-020/027, SC-008/012 (partial). Independent of T120's running immutable wheels; no substitution into its frozen coding comparison and no extra coding candidate under that protocol. All eight installed Click query results match the previous wheel; twelve normalization/isolation regressions pass. Mac installed qualification and all four actual Windows/WSL old/new architecture differentials pass, with identical bytes for all three requests per source. First/warm service medians improve roughly 12–14%; Cognee remains much faster warm. Full responses and zero-model query archive independently recover. See RandD/2026-10-19-swebench-confirmation-results.md; no end-to-end coding benefit is inferred.

- [x] [T122] Add an explicit compact on-demand MCP interface routing to unchanged services, expose its selection in generated CLI configuration, and verify advertised-interface reduction plus all-operation, scope, stale-delivery and default compatibility controls. FR-020/024/026, SC-008/012 (partial). Preserve T120 results; any new coding screen needs a separately frozen installation/protocol and reused-task disclosure. Interface bytes alone do not establish end-to-end token or latency savings. Actual installed catalog is 69.2% smaller and twelve operation responses match. Fresh ten-attempt reused-task screen: both 5/5, but 109969 versus 74890 total input (46.84% more), zero natural provider calls. All ten streams independently recover. Negative efficiency result retained; expanded remains default. See RandD/2026-10-19-compact-code-interface.md.

- [x] [T123] Correct the automatic-context adapter's lossy 1000-byte issue-prefix input through an explicit full-query path and an additive 4000-byte Code context bound. Preserve legacy replay defaults; oversized full requests refuse rather than silently truncate. Require UTF-8/limit/late-reference tests and actual installed qualification on every original validation query before any separately declared fresh paired screen. No ranking, output budget, solver/grader, task-selection or authority change; no prior confirmation is relabelled held out. FR-020/023/026; SC-008/012/013 (partial). Five actual full/prefix qualifications pass, preserving all prior prefix hashes. Both fresh arms pass 5/5; AtMem uses 142326 versus 96527 total input, so the efficiency target fails. Agent-only median is lower but context-inclusive time is higher. All ten original streams recover independently after the disclosed transport recovery; see RandD/2026-10-19-full-query-context-correction.md. Broader efficiency/SC-013 remain unmet.

- [x] [T124] Repair Windows SSH/WSL job EOF framing under `stdin-transport-recovery-20261019.md`; preserve the stopped snapshot and all original captures, require exact transport-only controller changes and unchanged evaluator/helper sources, recover the unavailable grade from the captured patch, and continue only the two unstarted cells. No model retry, task replacement, bad-grade retry, budget relaxation or release. Retain the complete stop/recovery/continuation record and separately verify the final archive. The eight-stream stopped snapshot and ten-stream final archive both recover independently. Exact source-delta, live Windows inherited-EOF and real child-with-open-stdin controls pass. The captured native Django patch passes the unchanged official grader; no model is rerun. Three scoped stranded readers are terminated without deleting data or owner processes.

## Context curation extension

- [x] [T125] Define closed contracts, budgets, compatibility and future efficacy protocol in `specs/042-atmem-code/context-curation-v1.md`; analyze FR-029–034/SC-014–018 coverage before code. Six requirements and five criteria mapped to T126–T132; no blocking extension issues; no modification of earlier negative benchmark outcomes.
- [x] [T126] Implement authorized ranked experience index and exact fetch in `atmem/code/curation.py`; no automatic narratives or raw output. FR-029/030/034. Focused index, private/secret/forget and exact-fetch controls pass.
- [x] [T127] Implement ranked code discovery, bounded goal-directed source expansion and final freshness validation in `atmem/code/curation.py`. FR-030/034. Exact lines, omissions, stale delivery and foreign-scope/source-integrity controls pass; ranking is deterministic, not a learned confidence estimate.
- [x] [T128] Add bounded process-local delivered-version/session/epoch ledger in `atmem/code/evidence_ledger.py`; explicit reference opt-in, restart/full-fetch safety. FR-031. Includes concurrent equal-result receipt binding and bounded eviction controls.
- [x] [T129] Wire curated MCP profile, stream revalidation and encrypted evidence, shared CLI/dashboard dispatch and settings/new-setup runtime index presentation in existing `atmem/code` and `atmem/knowledge/code/mcp.py`. FR-029/032/034. Full response/wire evidence and bundle v3 preserve encrypted portability; legacy settings/bundles remain readable. Installed Claude local-endpoint index delivery passes, not universal host qualification.
- [x] [T130] Implement reversible prompt-owner masking in `atmem/code/history.py`, unsupported native/learned capability declarations, preserving original history and tool pairs. FR-033. Requires an explicit retention callback; native CLI history mutation and pretrained pruning stay unavailable by design.
- [x] [T131] Add regression/stream/role/compatibility tests and zero-model qualification in `tests/test_code_curation.py` and `tools/qualify_code_curation.py`; run existing Code/knowledge gates. FR-029–034, SC-014–018. Broad 1099 passed/1 skipped/2 expected failures/1 deselected; separate installed final-wheel 40 passed. Separate host and owned-cleanup gates pass; see contract verification for overlaps, fixture corrections and artifact identity. No new coding efficacy result.
- [x] [T132] Document exact setup, mode switching, discovery/fetch/index behavior, remaining host/model limitations and measured verification in `docs/atmem-code.md` and `specs/042-atmem-code/context-curation-v1.md`; no efficiency/release claim. FR-032/034. No version change, owner environment install, commit/push or publication.
