# Tasks: Delegated Context-Provider Adapters

## Phase 1 — Packaging and shared foundations

- [x] [T001] Add independent `mem0`, `langgraph-provider`, and `pydantic-provider` optional extras without changing base imports in `pyproject.toml`.
- [x] [T002] Create the provider-adapter package and public protocol-neutral exports in `atmem/provider_adapters/__init__.py`.
- [x] [T003] Implement closed request, context-item, proposal, attribution, and runtime-identity models with bounds and scope validation in `atmem/provider_adapters/models.py`.
- [x] [T004] Implement strict delegated request parsing, query-digest verification, deadline handling, deterministic whole-item context construction, and bounded source references in `atmem/provider_adapters/runtime.py`.
- [x] [T005] Implement owner-only Ed25519 key creation/loading plus canonical receipt and v1 result-envelope signing in `atmem/provider_adapters/signing.py`.
- [x] [T006] Add unit tests for closed parsing, stable bytes, byte limits, timestamps, receipts, signatures, nonce, idempotency, and withholding in `tests/test_provider_runtime.py`.

## Phase 2 — Provider runtime and lifecycle

- [x] [T007] Implement safe `module:attribute` factory loading without expression evaluation in `atmem/provider_adapters/loading.py`.
- [x] [T008] Implement the bounded numeric-loopback v1 HTTP endpoint and redacted health endpoint in `atmem/provider_adapters/server.py`.
- [x] [T009] Implement private instance configuration, foreground/background service control, PID validation, status, doctor, and removal in `atmem/provider_adapters/lifecycle.py` and `atmem/provider_adapters/worker.py`.
- [x] [T010] Add `atmem provider init|serve|start|stop|status|doctor|remove` with actionable inline help and a copyable delegated-registration command in `atmem/cli.py`.
- [x] [T011] Test HTTP restrictions, concurrent requests, timeout/failure behavior, safe files, PID handling, secret redaction, lifecycle, and CLI guidance in `tests/test_provider_server.py` and `tests/test_provider_cli.py`.

## Phase 3 — Mem0 provider adapter

- [x] [T012] Implement sync/async Mem0 search normalization with mandatory `user_id`, `agent_id`, and `app_id` filters in `atmem/provider_adapters/mem0.py`.
- [x] [T013] Reject malformed, duplicate, or contradictory-scope Mem0 results; never retry without filters; produce bounded source-linked proposals in `atmem/provider_adapters/mem0.py`.
- [x] [T014] Support explicit OSS and platform Mem0 client construction while keeping credentials out of configuration and status output in `atmem/provider_adapters/mem0.py` and `atmem/provider_adapters/lifecycle.py`.
- [x] [T015] Test Mem0 response variants, three-axis isolation, empty/malformed results, async clients, missing dependencies, credential failures, and signed AtMem verification in `tests/test_mem0_provider.py`.

## Phase 4 — LangGraph provider adapter

- [x] [T016] Implement fresh bound graph input/config and sync/async `invoke`, `ainvoke`, and callable execution in `atmem/provider_adapters/langgraph.py`.
- [x] [T017] Parse strict `context_decision` output including LangGraph v2 `.value`, and fail closed for interrupts, missing/extra fields, or altered binding in `atmem/provider_adapters/langgraph.py`.
- [x] [T018] Test input immutability, thread binding, invocation variants, v2 output, interrupts, invalid output, timeout, missing dependency, and signed AtMem verification in `tests/test_langgraph_provider.py`.

## Phase 5 — Pydantic AI provider adapter

- [x] [T019] Implement strict optional Pydantic output models and an agent-construction helper in `atmem/provider_adapters/pydantic_ai.py`.
- [x] [T020] Implement sync/async agent execution using only validated `result.output`, with bounded attribution and explicit local/hosted egress classification in `atmem/provider_adapters/pydantic_ai.py`.
- [x] [T021] Test deterministic structured output, sync/async agents, invalid output, attribution, missing dependency, timeout, and signed AtMem verification in `tests/test_pydantic_provider.py`.

## Phase 6 — Integration, security, and operability

- [x] [T022] Add integration tests proving all three adapters produce envelopes accepted by existing delegated verification and that scope, signature, context, replay, and double-injection violations fail closed in `tests/test_provider_integration.py`.
- [x] [T023] Add runtime performance coverage for 100 deterministic provider-independent requests with local p95 below 25 ms in `tests/test_provider_performance.py`.
- [x] [T024] Add clean-base and independent-extra import/metadata checks while preserving current host-adapter extras in `tests/test_packaging.py` and CI configuration.
- [x] [T025] Document setup, trust registration, explicit enablement, operation, rollback, privacy boundaries, and copyable Mem0/LangGraph/Pydantic AI examples in `docs/context-provider-adapters.md` and `docs/delegated-context-provider.md`.
- [x] [T026] Put provider-adapter discovery and quick starts front and center in `README.md`, and align `docs/capabilities.json`, `docs/current-status.md`, and documentation tests with implemented behavior.
- [x] [T027] Mark the completed Spec 004 ecosystem work and retain honest remaining framework-host work in `todo.md`.
- [x] [T028] Run targeted provider tests, delegated/native security tests, OpenClaw prepack tests, documentation checks, and the full regression suite; record exact commands and outcomes in this task file.

## Dependencies and execution order

- T001–T003 unblock all adapter modules.
- T004–T006 establish the signed contract boundary before any external SDK is called.
- T007–T011 establish the reusable service and CLI before provider-specific lifecycle wiring.
- T012–T015, T016–T018, and T019–T021 may proceed independently after T003–T005 and T007.
- T022–T024 require all provider implementations and runtime/lifecycle work.
- T025–T027 must describe only behavior proven by T022–T024.
- T028 is the release gate and runs last.

## Validation record

- `python -m pytest -q tests/test_provider_runtime.py tests/test_mem0_provider.py tests/test_langgraph_provider.py tests/test_pydantic_provider.py tests/test_provider_cli.py tests/test_provider_integration.py tests/test_provider_performance.py tests/test_provider_packaging.py tests/test_documentation.py` — 28 passed.
- `python -m pytest -q tests/test_provider_server.py tests/test_delegated_context.py` — 40 passed with loopback permission.
- `python -m pytest -q` — 407 passed; one upstream Pydantic AI event-loop deprecation warning.
- CI independently installs and checks `atmem[mem0]`,
  `atmem[langgraph-provider]`, and `atmem[pydantic-provider]` before running
  their focused suites.

## Convergence tasks

- [x] [T029] Correct the FR-003 wording so v1 request bindings are preserved while nonce and idempotency are generated and bound in the signed result, without changing wire fields, in `specs/004-context-provider-adapters/spec.md`.
- [x] [T030] Expose redacted provider readiness, last decision, and adapter latency, and make doctor report actionable optional-extra/factory failures before startup in `atmem/provider_adapters/runtime.py`, `atmem/provider_adapters/server.py`, and `atmem/provider_adapters/lifecycle.py`.
- [x] [T031] Assert in clean installed-wheel CI that Mem0, LangGraph, and Pydantic AI SDKs are absent from the base installation in `.github/workflows/ci.yml`.
