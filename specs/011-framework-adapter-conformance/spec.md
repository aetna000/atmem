# Feature Specification: Framework Adapter Conformance

**Feature directory**: `specs/011-framework-adapter-conformance`
**Created**: 2026-09-05
**Status**: Draft
**Input**: `todo.md` P1.10

## Overview

Provide honest, capability-negotiated host adapters for OpenAI Agents SDK, Microsoft Agent Framework, Google ADK, Hugging Face smolagents, CrewAI, and a verified Hermes/generic recipe, with MCP retained as the universal tool-only fallback.

## User Scenarios & Testing

### User Story 1 - Integrate a supported framework (Priority: P1)

A developer installs one optional adapter and gets capture, prepare, exact injection, exposure confirmation, model input/output, tool/terminal/failure events, and multi-agent scoping where the host can prove them. Unsupported proof points are reported, never inferred.

**Why this priority**: An advertised automatic adapter must preserve authority and state exactly at the host boundary.

**Independent Test**: Run the common lifecycle suite against one adapter with a fake host and verify applicable proofs and explicit gaps.

**Acceptance Scenario**: **Given** a supported host version, **when** conformance runs, **then** every lifecycle capability is verified or explicitly unsupported.

### User Story 2 - Compare capabilities and recover (Priority: P2)

CLI/dashboard show adapter version, host version, negotiated capabilities, mode, health, evidence gaps, activation, and rollback. Automatic activation requires a passing conformance result and explicit approval.

**Why this priority**: Users need one honest control surface for compatibility and recovery.

**Independent Test**: Present compatible, incompatible, shadow, active, and degraded fixtures through CLI/dashboard and compare authoritative capability payloads.

**Acceptance Scenario**: **Given** an incompatible host version, **when** activation is requested, **then** it is refused with the failed capability evidence and rollback guidance.

### Edge Cases

- Duplicate, missing, delayed, and out-of-order lifecycle hooks resolve idempotently without false exposure claims.
- Unsupported host versions, missing task identity, multiple agents, streaming cancellation, and partial tool failures remain explicit capability or flight states.
- An adapter that cannot prove exact injection may operate only at its honestly declared weaker boundary.

## Requirements

### Functional Requirements

- **FR-001**: Extend Spec 007's versioned `AtMemAdapterIdentity` and `AtMemTurnLifecycle` protocol and conformance matrix for capture, prepare, exact injection, exposure confirmation, model I/O, tools, terminal events, failures, cancellation, and multi-agent scope; this feature MUST NOT create a competing adapter protocol.
- **FR-002**: Each advertised adapter MUST publish detected/supported/verified/unsupported capabilities and tested host-version ranges through `atmem/contracts/versions.py::capabilities()`, the single runtime authority established by Spec 007 FR-039.
- **FR-003**: Exact-exposure claims MUST require host evidence binding prepared bytes, model call, scope, and nonce; unavailable proof MUST remain an explicit gap.
- **FR-004**: Adapters MUST preserve host-owned execution state and AtMem-owned memory authority.
- **FR-005**: Multi-agent events MUST carry stable host session/run/agent identities mapped to exact AtMem scope.
- **FR-006**: Failures, retries, streaming cancellation, duplicate hooks, and out-of-order events MUST be idempotent and safely finalized.
- **FR-007**: Setup, status, doctor, activate, and rollback MUST extend Spec 007's capability-gated control-plane surface, consume its authoritative runtime response, and MUST NOT silently enable egress or memory delivery.
- **FR-008**: MCP MUST remain documented and tested as a tool-only fallback whose proof limitations are clear.
- **FR-009**: Optional framework dependencies MUST not enter the base package.
- **FR-010**: Every applicable adapter and framework SDK dependency MUST support Python 3.10–3.13 and have Apache-2.0-compatible enterprise licensing before the adapter is advertised.

### Key Entities

- **Adapter Capability Projection**: Framework-specific view of the authoritative runtime capability response.
- **Host Lifecycle Event**: Scoped capture/model/tool/terminal/failure event with stable host identity.
- **Conformance Result**: Applicable cases, pass/fail/gap outcomes, host/package versions, and evidence.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Every advertised adapter passes the same applicable conformance cases and publishes its gaps.
- **SC-002**: Cross-agent and cross-run leakage is zero in adversarial concurrency tests.
- **SC-003**: Duplicate/out-of-order/failure fixtures yield one consistent evidence lifecycle.
- **SC-004**: A host-version incompatibility prevents activation with actionable recovery.
- **SC-005**: The supported-version matrix passes on Python 3.10–3.13, dependency audits find no incompatible licence, and the clean base package imports without framework SDKs.

## Out of Scope

Claiming capabilities a host cannot expose, replacing framework orchestration, or making MCP equivalent to automatic exact injection.

## Dependency

Spec 007 is a prerequisite for task-aware adapter identity, runtime capability authority, activation gating, and exact task-state delivery/guard reporting. Frameworks may implement non-task memory hooks earlier, but they cannot advertise governed task-state capabilities until Spec 007's applicable contracts are present.

## Assumptions

- Spec 007 remains the sole runtime capability and task-aware lifecycle authority.
- Framework public hooks differ; conformance reports may declare unsupported proof points.
- Framework SDKs remain optional extras and supported version ranges are pinned by evidence.
