# Feature Specification: Guided Onboarding and Health

**Feature directory**: `specs/017-guided-onboarding-and-health`
**Created**: 2026-09-05
**Status**: Draft
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
