# AtMem Code: dependency-ordered tasks

**Status:** Planning checklist; no task is complete merely because it appears here.
**Governing artifacts:** [spec.md](spec.md), [plan.md](plan.md), [market-research.md](market-research.md), `.specify/memory/constitution.md`.
**Release target:** AtMem Code after the published 2.3.8 baseline; a new candidate must not reuse or move the historical `v2.3.9b1` Laya tag.

The owner requested implementation of phases 0–8, including provider routing and graph. These remain opt-in user features, not omitted development phases. Phase 9 benchmark and release work is deferred by the owner's later instruction. A named agent target is not an automatic integration until its installed-version probe passes.

## Phase 0 — Resolve the contract and freeze evaluation

- [x] T001 Record decisions on full-fidelity default, protected secret evidence, external-provider authority, cross-machine sharing and the meaning of “governance off” in `specs/042-atmem-code/clarifications.md`; amend `spec.md` and `plan.md` to remove remaining constitutional conflicts before runtime work.
- [x] T002 Add a Constitution Check and a requirement-to-gate crosswalk in `specs/042-atmem-code/plan.md`, including the release-blocking versus experimental subset and the exact supported-host claim rules.
- [x] T003 Define per-host event, injection, acknowledgement, trust, version and OS capabilities for Muse Code, Claude Code, Grok CLI, GitHub Copilot CLI and Codex in `specs/042-atmem-code/host-capabilities.md`; assess Copilot editor/cloud separately.
- [x] T004 Define the VibeMemBench protocol, source-availability gate, chronological boundary, baselines, budget, repetition policy and raw-result schema in `specs/042-atmem-code/benchmark-protocol.md`; defer exact corpus license, task IDs and hashes until upstream artifacts exist, and prohibit oracle-experience injection into product arms.
- [x] T005 Correct the 2.3.8 publication baseline, AtMem Code track and historical Laya prerelease treatment in `docs/release-roadmap.md`; leave release version constants unchanged until preparation.

## Phase 1 — Safe memory intake foundation

- [x] T006 Reproduce the raw-episode-before-screening and `interpreted_fact` bypasses with fake credentials in `tests/test_memory_secret_boundary.py` against the 2.3.8 `atmem/memory.py` path.
- [x] T007 Repair pre-write screening at the `atmem/memory.py` semantic admission boundary so recognized secrets do not reach raw episodes or canonical memory; preserve the separate constitution-compliant encrypted flight-evidence service and document residual coverage in `specs/042-atmem-code/phase1-security-report.md`.
- [x] T008 Add Hermes, existing `remember()`, false-positive/false-negative fixture disclosure and disk-persistence regression gates in `tests/test_memory_secret_boundary.py` and `tests/test_hermes_install.py`; verify existing protected evidence and disclose untested export/egress surfaces in `specs/042-atmem-code/phase1-security-report.md` for later phase gates.

## Phase 2 — One host-neutral Code service and scope

- [x] T009 Specify versioned observation, formation, context, exposure, deletion and error contracts in `atmem/code/contracts.py`, with matching schema and compatibility tests in `tests/test_code_contracts.py`.
- [x] T010 Implement authenticated local intake, session binding, idempotency and bounded queues in `atmem/code/service.py`; reject unauthenticated or cross-scope events in `tests/test_code_service.py`.
- [x] T011 Implement stable project identity, explicit clone/remote rebinding, profile/agent-private lanes and migration in `atmem/code/identity.py` and `atmem/store/sqlite.py`; test identity collision and scope isolation in `tests/test_code_identity.py`.
- [x] T012 Implement safe coding-memory formation from observed user intent, task outcomes, source and Git revision in `atmem/code/formation.py`; distinguish supported project facts from transient summaries and test correction/supersession in `tests/test_code_formation.py`. Task outcomes remain evidence-only without independent attestation; this is a deliberate non-promotion result, not a positive formation claim.

## Phase 3 — Guided setup and agent adapters

- [ ] T013 Add Code as a flavour of normal AtMem onboarding, plus `atmem code setup/status/doctor/enable/disable/uninstall`, in `atmem/cli.py` and `atmem/code/install.py`; installed package alone must remain non-influencing. Disable pauses only automatic capture/injection; uninstall alone restores host configuration.
- [x] T014 Implement a host-adapter interface and reversible configuration snapshot/probe contract in `atmem/code/adapters/base.py`; test failed install, exact restore and host upgrades in `tests/test_code_install.py` and `tests/test_code_adapter_base.py`.
- [ ] T015 Implement and installed-version test the Muse Code adapter in `atmem/code/adapters/muse.py` and `tests/test_code_muse.py`.
- [ ] T016 Implement and installed-version test the Claude Code adapter in `atmem/code/adapters/claude.py` and `tests/test_code_claude.py`.
- [ ] T017 Implement and installed-version test the Grok CLI adapter in `atmem/code/adapters/grok.py` and `tests/test_code_grok.py`.
- [ ] T018 Implement and installed-version test the GitHub Copilot CLI adapter in `atmem/code/adapters/copilot.py` and `tests/test_code_copilot.py`; do not claim editor/cloud coverage from this test.
- [ ] T019 Implement and installed-version test the Codex adapter in `atmem/code/adapters/codex.py` and `tests/test_code_codex.py`.
- [ ] T020 Publish tested host/OS/version support and manual-only fallbacks in `specs/042-atmem-code/host-capabilities.md`; require the actual hook and context-submission probe before an automatic label.

## Phase 4 — Automatic formation, recall and cross-agent use

- [ ] T021 Wire enabled host-turn events to one formation path in `atmem/code/service.py`; prove no agent-initiated `remember` call is needed in `tests/test_code_automatic.py`.
- [ ] T022 Build bounded, source-linked, scope-authorized context packs in `atmem/code/context.py`; test stale-state exclusion, truncation and timeout behavior in `tests/test_code_context.py`.
- [ ] T023 Record submitted bytes, host acknowledgement and independently observed model input as distinct assurance levels in `atmem/code/receipts.py`; test no overclaim of model delivery in `tests/test_code_receipts.py`.
- [ ] T024 Run paired new-session and cross-agent handoffs for supported hosts in `tests/integration/test_code_handoff.py`, including private-lane isolation and idempotent replay.

## Phase 5 — Search, settings and scoped clearing

- [ ] T025 Add `atmem code search`, inspect, correct, forget, config and clear/preview commands in `atmem/cli.py`, with machine-readable output and authorization tests in `tests/test_code_cli.py`.
- [ ] T026 Add one Coding Memory dashboard view and the same supported settings in `atmem/dashboard/`; test CLI/dashboard state parity, source inspection and access control in `tests/test_code_dashboard.py`.
- [ ] T027 Implement exact project/profile/agent deletion preview and verification across canonical and registered derived stores in `atmem/code/deletion.py`; test adjacent-scope preservation and partial remote-provider outcomes in `tests/test_code_deletion.py`.

## Phase 6 — External context providers

- [ ] T028 Specify route selection, query authorization, external egress, provider authority mode, response validation and failure policy in `atmem/code/providers.py` and `specs/042-atmem-code/provider-contract.md`.
- [ ] T029 Wire configured local RAG and Mem0 routes through the existing delegated-context boundary in `atmem/code/providers.py`; test native fallback, withholding, provenance and no unintended egress in `tests/test_code_providers.py`.
- [ ] T030 Expose route configuration and provider status in both `atmem/cli.py` and `atmem/dashboard/`; test that a request tag cannot grant scope or network authority in `tests/test_code_provider_settings.py`.

## Phase 7 — Optional code graph

- [ ] T031 Build an optional, encrypted-at-rest derived symbol/import/reference index with versioned source links in `atmem/code/graph.py`; keep canonical memory independent of the parser.
- [ ] T032 Invalidate or rebuild graph slices after edits, branch changes and imports in `atmem/code/graph.py`; test unsupported-language fallback and stale-result labelling in `tests/test_code_graph.py`.
- [ ] T033 Compare graph nomination against ordinary file exploration and a strong repository-map control in `specs/042-atmem-code/benchmark-protocol.md`; measure complete agent tokens, quality and indexing overhead, not query bytes alone.

## Phase 8 — Project portability and product parity

- [ ] T034 Implement an encrypted, integrity-checked, project-scoped export manifest and bundle in `atmem/code/portable.py`; exclude machine credentials and host hook configuration.
- [ ] T035 Implement authorized import preview, explicit identity rebinding, collision handling and derived-index rebuild in `atmem/code/portable.py`; test fresh-install search/lifecycle parity and cross-scope denial in `tests/test_code_portable.py`.
- [ ] T036 Run installed-wheel onboarding, CLI/dashboard parity and bundle round-trip journeys on macOS, Windows and Linux where supported in `tests/integration/test_code_product_journey.py`; record untested host/OS combinations as unsupported.

## Phase 9 — Independent task evaluation and release gate (deferred; do not run in this request)

- [ ] T037 Implement VibeMemBench and unfiltered real-issue adapters in `research/atmem_code_bench/` with frozen manifests, separate development and held-out runs, chronological leakage checks and preserved grader outputs.
- [ ] T038 Run matched memory-off, native, AtMem memory, graph and combined arms plus technically comparable competing-memory/structural controls in `research/atmem_code_bench/`; keep host/model versions, prior histories and budgets fixed and report results per host.
- [ ] T039 Publish raw receipts and a report of executable resolution, paired uncertainty, total tokens/cost, p50/p95 latency, throughput, errors, stale/wrong-context harm, capture and indexing overhead in `research/atmem_code_bench/results/`; mark partial or unverified runs as non-production evidence.
- [ ] T040 Perform SpecKit consistency analysis, constitution check, security, migration, installed-artifact and cross-platform gates in `specs/042-atmem-code/`; close or explicitly defer every release-blocking task before preparation.
- [ ] T041 Prepare the actual release candidate under `docs/release-coordination.md`: choose an unused version, align all package/bridge pins, add `docs/releases/v<VERSION>.md`, update `docs/website/manifest.json`, check website docs and prepare the separate owner-reviewed website PR. Do not tag until clean gates pass; verify workflows, registries and live-website state separately.
