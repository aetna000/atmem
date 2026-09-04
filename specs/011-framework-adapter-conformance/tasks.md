# Tasks: Framework Adapter Conformance

**Input**: Design documents from `specs/011-framework-adapter-conformance/`

**Prerequisites**: Spec 007 plus the feature plan

**Organization**: Foundational work precedes independently testable user-story phases; release evidence and documentation finish the feature.

## Phase 1 — Foundational

- [ ] [T001] Extend Spec 007's adapter identity/lifecycle and authoritative `capabilities()` rows in `atmem/adapters/base.py` and `atmem/contracts/versions.py`; add the reusable framework conformance kit in `tests/adapter_conformance.py` without creating a parallel protocol or registry (FR-001–FR-006)

## Phase 2 — User Story 1 - Integrate a supported framework (Priority: P1)

- [ ] [T002] [US1] Implement OpenAI Agents SDK and Microsoft Agent Framework optional adapters in `atmem/adapters/openai_agents.py` and `atmem/adapters/microsoft_agent.py`
- [ ] [T003] [US1] Implement Google ADK and Hugging Face smolagents optional adapters in `atmem/adapters/google_adk.py` and `atmem/adapters/smolagents.py`
- [ ] [T004] [US1] Implement CrewAI adapter and verified Hermes/generic recipe in `atmem/adapters/crewai.py` and `docs/generic-adapter.md`
- [ ] [T005] [US1] Exercise exact injection/exposure, I/O, tools, terminal, failure, cancellation, retry, and multi-agent cases in `tests/test_framework_adapter_conformance.py` (FR-001–FR-006)

## Phase 3 — User Story 2 - Compare capabilities and recover (Priority: P2)

- [ ] [T006] [US2] Extend Spec 007's capability-gated CLI/dashboard setup/status/doctor/activation/rollback in `atmem/cli.py`, `atmem/control/server.py`, and `atmem/control/assets/app.js`, consuming only the authoritative runtime response and preserving `docs/dashboard-design-language.md` ownership rules (FR-007)

## Phase 4 — Verification and Release Evidence

- [ ] [T007] Verify and document MCP tool-only fallback and proof limits in `tests/test_mcp.py` and `docs/framework-adapters.md` (FR-008)
- [ ] [T008] Add optional-dependency/version matrix in `pyproject.toml` and `.github/workflows/framework-adapters.yml`; publish reports in `docs/framework-adapters.md` (FR-009, SC-001–SC-004)
- [ ] [T009] [P] Verify Python 3.10–3.13 for applicable adapters, Apache-2.0-compatible enterprise licensing for every framework SDK/transitive dependency, and a clean base install without extras in `pyproject.toml`, `.github/workflows/framework-adapters.yml`, and `tests/test_framework_adapter_packaging.py` (FR-010, SC-005)

## Dependencies and Execution Order

**Cross-spec dependency**: Spec 007.
**Task dependencies**: T001 → all; T002–T004 → T005/T006/T008; T005 → T008; T009 gates release.
