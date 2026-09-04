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
| VII. Local-First and Explicit Egress | PASS | Framework extras are optional; egress/delivery activation remains explicit. |

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

Follow `docs/dashboard-design-language.md`, preserve the four-workspace layout, and follow `specs/integration-ownership.md`: Spec 007 owns shared dashboard-shell/capability activation and Spec 012 owns shared CLI routing/output conventions.

## Test Strategy

Contract fixtures plus framework-specific sync/async/streaming/tool/error/multi-agent tests; version-drift detection; packaging-without-extras; exact-byte evidence and privacy adversaries.

## Rollout

Mark adapters experimental until CI exercises supported versions. Enable per integration only after doctor/conformance succeeds; rollback removes hooks without deleting canonical memory.
