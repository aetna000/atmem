# Feature Specification: Guided Onboarding and Health

**Product-wide requirements**: [Agent neutrality, multiple agents, private/shared memory, governed providers and clear time-aware feedback](../product-requirements.md) (PR-001–PR-006). Applies to this feature's advertised capabilities; implementation status below remains authoritative.

**Feature directory**: `specs/017-guided-onboarding-and-health`
**Created**: 2026-09-05
**Status**: Implemented
**Unified product amendment status**: Specified; implementation and verification pending. The status above describes the historical baseline only.
**Input**: `todo.md` P2.16

## Overview

Give new users one safe, resumable path from install to a verified test memory and semantic recall, while making shadow mode, activation, restoration readiness, and “why” explanations clear in CLI and dashboard.

## User Scenarios & Testing

### User Story 1 - Complete guided setup (Priority: P1)

A user selects a supported host, verifies prerequisites, keeps shadow mode by default, optionally configures AtBot and local embeddings with explicit egress/download consent, captures a synthetic test memory, verifies retrieval/context behavior, checks backup readiness, and explicitly activates.

**Why this priority**: The primary journey must prove safe value before activation.

**Independent Test**: Run the deterministic wizard against a fresh isolated install with optional egress declined.

**Acceptance Scenario**: **Given** a fresh supported install, **when** the wizard completes, **then** synthetic capture/paraphrase/context checks pass in shadow mode before explicit activation.

### User Story 2 - Diagnose from dashboard or CLI (Priority: P2)

One health model reports host topology, authority store, shadow/active mode, AtBot, semantic index, evidence integrity, deletion/backup readiness, and direct corrective actions. Explanations answer why a record was remembered, retrieved, ranked, injected, or withheld.

**Why this priority**: Users need actionable understanding when setup or memory behavior is degraded.

**Independent Test**: Render every health/reason fixture through CLI JSON and dashboard and invoke only allowed corrective actions.

**Acceptance Scenario**: **Given** a simulated component fault, **when** health is viewed, **then** both surfaces show the same evidence, limitation, and safe next action.

### Edge Cases

- Interrupted steps, stale checkpoints, declined consent, existing partial configuration, host-version mismatch, missing model service, failed smoke-memory cleanup, and rollback failure remain explicit recoverable states.
- Unauthorized users see neither memory content nor whether scoped objects exist.
- Dashboard refresh and CLI resume consume the same state without repeating mutations.

## Requirements

### Functional Requirements

- **FR-001**: Provide a versioned resumable setup state machine for host, authority store, shadow mode, AtBot, embeddings, test capture, retrieval verification, activation, and restore readiness.
- **FR-002**: Setup MUST detect existing installations/configuration, preview changes, preserve unrelated settings, checkpoint progress, and offer verified rollback.
- **FR-003**: Shadow mode MUST be the default; activation MUST require passing mandatory checks and explicit confirmation.
- **FR-004**: Downloads, credentials, hosted providers, content egress, and optional dependencies MUST require explicit choices and show consequences.
- **FR-005**: CLI human/JSON and dashboard MUST consume one health/action contract with severity, evidence, limitations, and state-valid corrective commands/actions.
- **FR-006**: “Why” explanations MUST distinguish extraction proposal, admission/policy, retrieval signals, authorization/lifecycle revalidation, rank/support class, byte-budget selection, delivery evidence, and withhold/degradation reason.
- **FR-007**: Example paths MUST cover OpenClaw, Pydantic AI, LangGraph, and HTTP API using synthetic data and declared proof boundaries.
- **FR-008**: Setup/health MUST work in deterministic local-only mode; optional-component failure MUST not corrupt or silently activate the installation.
- **FR-009**: The wizard MUST never expose secrets or scoped memory content in health output, logs, telemetry, or support bundles.

### Key Entities

- **Setup Session**: Scoped versioned steps, checkpoints, consent, changes, and terminal state.
- **Health Check**: Component state, severity, evidence, limitations, and allowed actions.
- **Setup Receipt**: Previewed/applied changes, verification, activation, cleanup, and rollback.
- **Why Explanation**: Safe projection of admission, retrieval, policy, rank, budget, and delivery evidence.

## Success Criteria

### Measurable Outcomes

- **SC-001**: In a documented controlled usability protocol, at least 90% of representative new users complete the local install-to-verified-paraphrase flow in under 15 minutes excluding download duration and without undocumented assistance.
- **SC-002**: Every simulated health fault maps to one consistent CLI/dashboard state and at least one safe next action or explicit manual guidance.
- **SC-003**: Interrupted setup resumes or rolls back without ambiguous activation/configuration.
- **SC-004**: Each documented example passes an installed-package smoke test and states what capture/exposure evidence it can prove.
- **SC-005**: An automated fresh-install fixture completes the deterministic wizard state machine in at most 12 user decisions, with every mutation checkpointed and all optional egress declined.

## Out of Scope

Hiding security choices, auto-activating delivery, collecting private diagnostics by default, or replacing advanced operational documentation.

## Assumptions

- Specs 005, 006, 008, 012, and 015 supply the component contracts composed by the wizard.
- Controlled usability evidence supplements rather than replaces automated state-machine tests.
- Existing advanced setup commands remain supported during migration.
## Invariant Attestation

Touches INV-004, INV-006, INV-008, INV-009, and INV-010 through `spec017.activation-guard`, `spec017.explanation`, `spec017.health-proof`, `spec017.rollback`, and `spec017.local-discovery`.


## Unified product amendment — 2026-09-09

**Roadmap status**: Baseline status above is historical; this amendment is specified and not implemented. Existing unchecked tasks remain prerequisites where referenced.

**Product role**: adoption and onboarding. See [product roadmap](../product-roadmap.md) and [implementation review](../implementation-review-2026-09-09.md).

**Observed foundation**: Resumable setup exists; activate currently requires capture/paraphrase/context/evidence/restore checks for every path.

### Additional functional requirements

- **FR-010**: Offer memory-only, govern-existing-context and investigate-existing-agent adoption paths with path-specific checks; investigation MUST NOT require native migration, embeddings, AtBot or memory activation.
- **FR-011**: Preserve explicit activation for context influence and show observed/enforced/missing coverage during a synthetic connected-agent failure walkthrough.

### Acceptance and success criteria

- **SC-006**: Each adoption path completes with irrelevant components absent; choosing investigation performs zero canonical imports and no context injection, while failed required delivery checks block governance activation.

**Scenario**: Given the declared capability and scope, when the integrated journey executes with the relevant provider or host failure, then the additional requirements above hold and the result distinguishes observed, enforced, missing and unsupported evidence.

### Compatibility and ownership

Integration contracts: Specs 019–022. This feature owns its existing component adaptation only; new contract ownership is in `specs/integration-ownership.md`. New navigation follows Spec 022; historical four-workspace task text is retained as delivery history and is superseded for future integration. Preserve canonical authority, explicit activation, optional task state, host-owned checkpoints, local fallback and existing public contracts. No new capability may be advertised until its acceptance evidence passes.

## Product-wide requirements — agent neutrality and clear evidence

**Required, not yet implemented:** [Product requirements](../product-requirements.md) PR-001–PR-006. This amendment applies to this feature's public and UI boundaries; host-specific integrations cannot redefine core identity or authority.

- **FR-012**: Onboard by customer need and authenticated agents/spaces, not host-specific defaults. Offer private space by default for new memory, explicit shared-space selection and readable permission previews; no implicit membership from parent/child relationships. Show health reason, verification time/age and permitted next action. Existing scopes and investigation-only users require no sharing or migration.
- **SC-007**: Native/private, shared-memory and investigation-only onboarding complete without OpenClaw dependencies in core tests; disabled sharing stays disabled, inaccessible spaces remain undisclosed and refresh alone never renews a health check.

This work extends existing authority and preserves legacy scopes. Private/shared memory and multi-framework claims require their own evidence; M0 delivers only its applicable capture/feedback subset. See the central ownership and release matrix.
