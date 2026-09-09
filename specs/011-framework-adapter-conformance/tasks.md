# Tasks: Framework Adapter Conformance

**Evidence policy**: Append verification to a new entry under `docs/implementation-evidence/011/` following `docs/implementation-evidence/README.md`. `docs/current-status.md` is a linked summary, not a raw test log; dated reviews are frozen. Task-ID suffixes are significant (see `specs/task-conventions.md`).

**Input**: Design documents from `specs/011-framework-adapter-conformance/`

**Prerequisites**: Spec 007 plus the feature plan

**Organization**: Foundational work precedes independently testable user-story phases; release evidence and documentation finish the feature.

## Phase 1 — Foundational

- [x] [T001] Extend Spec 007's adapter identity/lifecycle and authoritative `capabilities()` rows in `atmem/adapters/base.py` and `atmem/contracts/versions.py`; add the reusable framework conformance kit in `tests/adapter_conformance.py` without creating a parallel protocol or registry (FR-001–FR-006)

## Phase 2 — User Story 1 - Integrate a supported framework (Priority: P1)

- [x] [T002] [US1] Implement OpenAI Agents SDK and Microsoft Agent Framework optional adapters in `atmem/adapters/openai_agents.py` and `atmem/adapters/microsoft_agent.py`
- [x] [T003] [US1] Implement Google ADK and Hugging Face smolagents optional adapters in `atmem/adapters/google_adk.py` and `atmem/adapters/smolagents.py`
- [x] [T004] [US1] Implement CrewAI adapter and verified Hermes/generic recipe in `atmem/adapters/crewai.py` and `docs/generic-adapter.md`
- [x] [T005] [US1] Exercise exact injection/exposure, I/O, tools, terminal, failure, cancellation, retry, and multi-agent cases in `tests/test_framework_adapter_conformance.py` (FR-001–FR-006)

## Phase 3 — User Story 2 - Compare capabilities and recover (Priority: P2)

- [x] [T006] [US2] Extend Spec 007's capability-gated CLI/dashboard setup/status/doctor/activation/rollback in `atmem/cli.py`, `atmem/control/server.py`, and `atmem/control/assets/app.js`, consuming only the authoritative runtime response and preserving `docs/dashboard-design-language.md` ownership rules (FR-007)

## Phase 4 — Verification and Release Evidence

- [x] [T007] Verify and document MCP tool-only fallback and proof limits in `tests/test_mcp.py` and `docs/framework-adapters.md` (FR-008)
- [x] [T008] Add optional-dependency/version matrix in `pyproject.toml` and `.github/workflows/framework-adapters.yml`; publish reports in `docs/framework-adapters.md` (FR-009, SC-001–SC-004)
- [x] [T009] [P] Verify Python 3.10–3.13 for applicable adapters, Apache-2.0-compatible enterprise licensing for every framework SDK/transitive dependency, and a clean base install without extras in `pyproject.toml`, `.github/workflows/framework-adapters.yml`, and `tests/test_framework_adapter_packaging.py` (FR-010, SC-005)

## Dependencies and Execution Order

**Cross-spec dependencies**: Spec 007.
**Task dependencies**: T001 → all; T002–T004 → T005/T006/T008; T005 → T008; T009 gates release.


## Phase 5: Unified product integration

New work is unchecked. Existing task IDs and completion history remain intact. Contract prerequisites: Specs 019, 020; see the roadmap for foundation versus integration ordering.

- [ ] [T010] Define failing boundary fixtures for FR-011, FR-012, SC-006 using `tests/test_framework_adapter_conformance.py`; exercise authorized success, relevant failure, missing evidence and cross-scope refusal.
- [ ] [T011] Extend actual host hooks and negotiated evidence coverage without a second registry in `atmem/adapters/`, `atmem/contracts/versions.py` (FR-011, FR-012); depend on T010 and the published prerequisite contracts, preserving baseline behavior.
- [ ] [T012] Verify SC-006 through the affected public/host boundaries, run regression and applicable upgrade/privacy gates, and record exact tested versions, commands, unsupported configurations and results in `docs/implementation-evidence/011/` (new append-only entry; see `docs/implementation-evidence/README.md`); depend on T011 and do not mark completion from declarations alone.

## Phase 6: Public Host Conformance Kit

- [ ] [T013] Freeze FR-014 manifest schema in `atmem/schemas/v1/host-conformance-manifest.json` and independent validation fixtures in `tests/test_host_conformance_kit.py`, following `conformance-manifest.md`; coordinate 020 coverage and 007 capability authority (FR-014, SC-008).
- [ ] [T014] Package the standalone runner, adapter harness and fixture resources in `atmem/conformance/` with CLI entry points through Spec 012; include host restoration and offline profiles, then run an external adapter from a clean install (FR-013, FR-016, SC-007; depends on T013).
- [ ] [T015] Publish contributor instructions in `docs/host-conformance.md` and reviewed listing structure in `docs/compatibility/hosts.json`; implement validation and self-reported/reproduced/AtMem-verified projection rules with explicit maintainer review (FR-015–FR-016, SC-008; depends on T014).
- [ ] [T016] Run third-party submission, evidence-tamper, version-mismatch, secret-redaction, offline and installed-artifact checks in `tests/test_host_conformance_kit.py`; retain exact outcomes and limits in `docs/framework-adapters.md` before advertising the kit (SC-007–SC-008; depends on T015).

## Product-wide integration

- [ ] [T017] Define independent boundary fixtures for FR-017/SC-009 in `tests/test_host_conformance_kit.py` using `specs/product-requirements.md`, including private/shared scopes, readable feedback and timestamp provenance as applicable.
- [ ] [T018] Implement FR-017 through `atmem/conformance/` and the owning service contracts; preserve legacy scope behavior and authorize all displayed facts/actions (depends on T017).
- [ ] [T019] Verify SC-009 through the applicable public/host/UI boundary in `tests/test_host_conformance_kit.py`; retain versions, coverage, failures and usability evidence in a new entry under `docs/implementation-evidence/011/` and link changed capability status from `docs/current-status.md` before advertising the capability (depends on T018).
