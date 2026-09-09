# Implementation Plan: Framework Adapter Conformance

**Branch**: `future/011-framework-adapter-conformance` | **Date**: 2026-09-05 | **Spec**: `specs/011-framework-adapter-conformance/spec.md`

**Input**: Feature specification from `specs/011-framework-adapter-conformance/spec.md`

## Summary

Extend Spec 007's adapter lifecycle and authoritative capability response into framework-specific bindings backed by one reusable conformance suite.

## Technical Context

- **Language/Version**: Python 3.10–3.13; framework versions pinned in the support matrix.
- **Dependencies**: Optional OpenAI, Microsoft, Google, Hugging Face, and CrewAI SDK extras.
- **Storage**: Existing AtMem authority/evidence only; adapters own no canonical database.
- **Testing/Target**: Shared fake-host conformance plus supported framework sync/async/streaming matrices.
- **Constraints/Scale**: Spec 007 capability authority, exact multi-agent identity, optional base packaging.

Extend the Spec 007 additions to `atmem/adapters/base.py` and `atmem/contracts/versions.py`, plus existing LangGraph/Pydantic patterns, into optional modules for each framework. Reuse context-provider contracts, flight evidence, topology/health, and the existing capability-gated control-plane activation; do not introduce another capability registry or activation authority.

## Constitution Check

| Principle | Gate | Evidence required |
| --- | --- | --- |
| I. Authority Before Intelligence | PASS | Adapters invoke AtMem authority and cannot admit, authorize, or invent memory. |
| II. Provenance and Exact Evidence | PASS | Exposure claims bind bytes, model call, nonce, host identity, and honest capability gaps. |
| III. Safe Defaults and Reversibility | PASS | Integrations start shadow, require verified activation, and support rollback. |
| IV. Scope, Privacy, and Verifiable Deletion | PASS | Exact session/run/agent/task scope and retry ordering are conformance gates. |
| V. Contract-First Host Neutrality | PASS | One Spec 007 lifecycle/capability authority is extended by replaceable bindings. |
| VI. Executable Claims | PASS | Supported host-version matrices and boundary conformance reports gate advertising. |
| VII. Local-First, Explicit Egress, and Replaceable Intelligence | PASS | Framework and intelligence extras are replaceable; egress/delivery activation remains explicit and no adapter owns memory authority. |

Dependency gate: every framework SDK MUST support Python 3.10–3.13 where applicable and have Apache-2.0-compatible enterprise licensing; unsupported versions remain unadvertised.

## Design

1. Freeze adapter event/capability/identity contracts and reusable fake-host conformance kit.
2. Implement framework modules using public lifecycle hooks and pin tested version ranges.
3. Normalize retries/streaming/failures into idempotent flight transitions.
4. Expose a single capability/health payload to CLI/dashboard and require explicit activation.
5. Publish MCP and generic recipes with precise automatic-versus-tool-only distinctions.

## Cross-Spec Dependency and Ownership

Spec 007 owns task-aware adapter identity, lifecycle methods, runtime capability truth, and activation gating. Spec 011 owns framework-specific bindings and the broader reusable conformance matrix. All runtime/schema/documentation capability views are projections of `atmem/contracts/versions.py::capabilities()`.

## Project Structure

Framework bindings live in `atmem/adapters/`; capability truth stays in `atmem/contracts/versions.py`; conformance fixtures stay in `tests/`; optional dependency metadata stays in `pyproject.toml`.

## Dashboard and CLI Integration

Follow `docs/dashboard-design-language.md`, implement the Spec 022/025 seven-section target with legacy-route migration, and follow `specs/integration-ownership.md`: Spec 022 owns shared dashboard-shell integration; Spec 007 retains task/capability activation and Spec 012 owns shared CLI routing/output conventions.

## Test Strategy

Contract fixtures plus framework-specific sync/async/streaming/tool/error/multi-agent tests; version-drift detection; packaging-without-extras; exact-byte evidence and privacy adversaries.

## Rollout

Mark adapters experimental until CI exercises supported versions. Enable per integration only after doctor/conformance succeeds; rollback removes hooks without deleting canonical memory.


## Unified product integration plan — 2026-09-09

Implement adapter coverage integration against the new contract owners (Specs 019, 020); use [integration ownership](../integration-ownership.md) and [roadmap order](../product-roadmap.md). Baseline prerequisites refer to existing implementations, not completion of all later amendments.

Touch points (existing or proposed tests): `atmem/adapters/`, `atmem/contracts/versions.py`, `tests/test_framework_adapter_conformance.py`. Extend actual host hooks and negotiated evidence coverage without a second registry. Reuse the existing application service and authoritative capability response. Public fields are additive/versioned; persisted changes require allocated migrations, real published-floor upgrade/recovery tests and no inferred historical relationships. UI shell ownership transfers to Spec 022; this feature supplies its view models.

Verification: write boundary fixtures for FR-011, FR-012, SC-006 before integration, then run the affected native/delegated, scope, fallback and interface regressions. Missing live-provider or real-host evidence is reported as unavailable, never substituted by a mock pass. Constitution I–VII remain binding; this amendment does not change the constitution or delegate canonical memory authority.

## Public conformance kit implementation

Implement FR-013–FR-016 through an installable `atmem/conformance/` runner/harness reusing existing adapter contracts. Publish `atmem/schemas/v1/host-conformance-manifest.json` from the [manifest contract](conformance-manifest.md), plus contributor commands in `docs/host-conformance.md`. Spec 012 integrates CLI entry points; 020 supplies execution coverage without another schema. Ship test fixture support as packaged resources, not imports from repository-private tests.

Store reviewed listing metadata in a versioned `docs/compatibility/hosts.json` catalog with explicit issuer/reviewer/reproducer identity and immutable evidence references. Schema validation does not award verification. Maintainers review proposed listings; private runs do not submit automatically. Reject secret-bearing payloads and overclaimed assurance; stale versions retain historical records with visible status.

Test SC-007/SC-008 with `tests/test_host_conformance_kit.py`, a clean installed external adapter fixture, negative schema/assurance/privacy vectors and local CLI/dashboard projection checks. Dependent third-party runners need only stable adapter contracts, not completed provider integration or every framework.

## Product-wide integration (FR-017, SC-009)

Implement FR-017 through `atmem/conformance/`, consuming Spec 012 space/membership and feedback contracts, 019 context authorization, 020 time/identity evidence and the owner mappings in `specs/product-requirements.md`. Allocate persisted changes through Spec 010; retain legacy scope behavior and keep new private/shared space behavior explicit. Domain code owns facts and permissions; UI and transports project the same result.

Add boundary fixtures in `tests/test_host_conformance_kit.py` for SC-009, including positive/negative scope access, concurrent membership changes and real-versus-unknown verification time. Report unsupported host/provider coverage rather than infer it. Existing OpenClaw APIs are adapter compatibility surfaces, not required core fields. The relevant tasks below gate this requirement; broader future features do not block M0's scoped profile.
