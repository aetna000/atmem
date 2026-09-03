# Tasks: Delegated Context Provider

## Phase 1: Contract and Validation Foundation

- [x] T001 Add the maintained Ed25519 verification dependency and `atmem/delegated` package exports in `pyproject.toml` and `atmem/delegated/__init__.py` (FR-003, FR-005, FR-007, FR-017)
- [x] T002 Implement frozen provider-neutral binding, request, trust, result, and decision types in `atmem/delegated/contracts.py` and `atmem/delegated/config.py` (FR-003, FR-015)
- [x] T003 Implement restricted canonical JSON, signing input, result digest, key fingerprint, and idempotency calculation in `atmem/delegated/canonical.py` (FR-003, FR-007)
- [x] T004 Implement duplicate-key rejecting parsing, closed structural/semantic validation, exact bytes, time, binding, trust, and Ed25519 verification in `atmem/delegated/validation.py` (FR-003, FR-005–FR-007)
- [x] T005 Run all PR positive and negative/stateful fixtures against production Python validation in `tests/test_delegated_context.py` (SC-002)

## Phase 2: Safe Configuration and Transport

- [x] T006 Implement symlink-safe, mode-0600, atomic delegated registration storage with disabled-by-default activation and safe status projection in `atmem/delegated/config.py` (FR-001, FR-002, FR-005, FR-011)
- [x] T007 Implement bounded no-redirect loopback HTTP transport and the closed request-v1 shape in `atmem/delegated/client.py` (FR-004, FR-015)
- [x] T008 Add configuration and transport tests for scope ambiguity, malformed keys, remote endpoints, timeout/size limits, redirect rejection, and secret-safe output in `tests/test_delegated_context.py` (FR-004, FR-005, SC-007)

## Phase 3: Durable Acceptance and Evidence

- [x] T009 Add additive schema-v5 delegated acceptance/replay and content-free delivery tables and indexes to `atmem/control/store.py` without reusing native context-persisting previews (FR-008, FR-012, FR-012a, FR-016)
- [x] T010 Implement atomic accept/idempotent retry/conflicting-turn/nonce/idempotency reservation APIs without persisting query or context bytes in `atmem/control/store.py` (FR-008, FR-012)
- [x] T011 Add schema-4 upgrade, concurrency, restart replay, backup/restore, removal, and content-minimization tests in `tests/test_delegated_context.py` and `tests/test_delegated_control.py` (FR-008, FR-012, FR-016, SC-004, SC-006)
- [x] T012 Implement provider-neutral delegated orchestration and evidence projections in `atmem/delegated/service.py` (FR-007–FR-012, FR-015)

## Phase 4: Exclusive Control-Plane Routing

- [x] T013 Extend `control_prepare` inputs and `ControlManager.prepare()` with turn/user/workspace bindings while preserving older callers in `atmem/control/server.py` and `atmem/control/manager.py` (FR-001, FR-006, FR-015)
- [x] T014 Route matching enabled scopes through delegated orchestration before all native candidate retrieval and context preparation in `atmem/control/manager.py` (FR-008–FR-011)
- [x] T015 Return additive authority, decision, exact context, location, receipt, acceptance, provider, and delegated exposure fields while persisting only content-free delivery state in `atmem/control/manager.py` (FR-009–FR-012a)
- [x] T016 Add manager spies and integration cases proving native default, valid inject, valid withhold, default failure, explicit native fallback, late output, exact retry, and zero native-plus-delegated double injection in `tests/test_delegated_control.py` (FR-001, FR-009–FR-013, SC-003–SC-005)

## Phase 5: CLI and Dashboard Product Experience

- [x] T017 Add discoverable `atmem delegated register|enable|disable|status|doctor|self-test|remove` commands with examples, JSON output, safe next actions, and confirmation semantics in `atmem/cli.py` (FR-002, FR-014)
- [x] T018 Add delegated configuration/status/doctor/self-test/remove APIs to `atmem/control/web.py` using the same service layer as CLI (FR-014)
- [x] T019 Add a collapsed Settings “Context authority” experience showing native default and optional delegated-provider trust/scope/failure configuration in `atmem/control/assets/app.js` and `app.css` (FR-002, FR-014, SC-007)
- [x] T020 Add CLI, API, dashboard, CSRF, no-key-leakage, and disabled-default tests in `tests/test_delegated_control.py`, `tests/test_cli.py`, and `tests/test_control_plane.py` (FR-001, FR-002, FR-014, SC-007)

## Phase 6: OpenClaw Exact-Delivery Adapter

- [x] T021 Add optional authenticated owner/user mapping—without a second authority enable switch—to `integrations/openclaw/openclaw.plugin.json`, `src/types.ts`, and `index.ts` (FR-001, FR-002, FR-002a, FR-006)
- [x] T022 Implement exclusive delegated `prependContext` insertion with stable turn binding, no suffix/normalization, and no native candidate/persona injection in `integrations/openclaw/index.ts` (FR-009, FR-010, FR-013)
- [x] T023 Retain exact delegated context only in bounded process memory, record separate provider-authorization/delivery/compatible disposition events, confirm one exact inserted segment at `llm_input`, and erase transient bytes immediately in `integrations/openclaw/index.ts` (FR-012, FR-012a, FR-013)
- [x] T024 Extend OpenClaw tests for exact emoji/CRLF bytes, one context contribution, inject/withhold/reject/fallback, missing identity, owner enforcement, receipt correlation, and native regression in `integrations/openclaw/test/hooks.mjs` and `delegated-context-contract.mjs` (FR-006, FR-009–FR-013, SC-003–SC-005)

## Phase 7: Documentation, Compatibility, and Beta Release

- [x] T025 Update the contract status and request contract, README quick start, generic/OpenClaw guides, dashboard language, current status, release notes, and `todo.md` with native-default and opt-in authority wording (FR-001, FR-002, FR-014, FR-018)
- [x] T026 Run native deterministic, AtBot, semantic, Pydantic AI, LangGraph, multi-agent, restore, dashboard, and Agent Black Box regressions with delegated mode absent/disabled (FR-001, FR-016, SC-001)
- [x] T027 Run all Python and OpenClaw typecheck/build/test/smoke suites and the deterministic release gate; record exact results here (SC-001–SC-005)
- [x] T028 Bump Python to `2.2.6b1` and OpenClaw npm to `2.2.6-beta.1`, add release notes, and verify version consistency without changing AtBot independently in `pyproject.toml`, package metadata, and adapter metadata (FR-018)
- [x] T029 Build and inspect isolated wheel/sdist/npm artifacts, verify licenses and contents, install clean, upgrade from AtMem 2.2.5, and rerun native plus delegated installed-artifact smoke tests (FR-016–FR-018, SC-006, SC-008)
- [x] T030 Commit and push the feature branch, publish the verified `2.2.6b1` Python prerelease and npm beta only when their respective tested artifacts changed, tag consistently, and verify public installation metadata (FR-018, SC-008)

## Verification evidence

- 2026-09-04: full Python source suite passed: 385 tests, one third-party
  Pydantic AI deprecation warning.
- 2026-09-04: delegated integration review passed: 87 tests before final
  hardening; final focused contract/control/documentation runs passed 52 and
  43 tests respectively.
- 2026-09-04: OpenClaw `prepack` passed build, typecheck, setup, hooks, all 3
  positive and 20 negative/stateful delegated vectors, and smoke tests.
- 2026-09-04: the deterministic 16-case benchmark passed every quality and
  safety threshold with zero privacy leaks, poisoning successes, or incorrect
  injections.
- 2026-09-04: final wheel, sdist, and npm tarball built with the intended beta
  versions and licenses; Twine checks, dependency checks, native installed-wheel
  smoke, delegated installed-wheel smoke, and a real 2.2.5-to-2.2.6b1 schema-v5
  upgrade smoke passed on Python 3.12.
- 2026-09-04: protected CI passed Python 3.10–3.13, current framework,
  OpenClaw, artifact, installed-wheel, and persisted-data upgrade gates. Public
  metadata was verified for PyPI `atmem==2.2.6b1`, npm
  `openclaw-memory-atmem@2.2.6-beta.1`, and GitHub prerelease tag `v2.2.6b1`.
