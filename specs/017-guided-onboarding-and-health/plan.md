# Implementation Plan: Guided Onboarding and Health

**Branch**: `future/017-guided-onboarding-and-health` | **Date**: 2026-09-05 | **Spec**: `specs/017-guided-onboarding-and-health/spec.md`

**Input**: Feature specification from `specs/017-guided-onboarding-and-health/spec.md`

## Summary

Compose existing and roadmap health contracts into one resumable, shadow-first setup flow and evidence-based explanation experience.

## Technical Context

- **Language/Version**: Python 3.10–3.13 and existing dashboard JavaScript.
- **Dependencies**: Specs 005/006/008/012/015 and existing OpenClaw/control-plane setup primitives.
- **Storage**: Resumable setup checkpoints/receipts; synthetic verification uses isolated canonical state.
- **Testing/Target**: pytest state-machine/recovery/parity/security, installed examples, and controlled usability protocol.
- **Constraints/Scale**: Shadow/local defaults, at most 12 user decisions, explicit egress/activation, secret-safe output.

Compose existing OpenClaw setup, control-plane topology, AtBot, semantic health, benchmark smoke cases, backup checks, and public API into `atmem/onboarding.py`. Render the same state machine/action payload in CLI and dashboard.

## Constitution Check

| Principle | Gate | Evidence required |
| --- | --- | --- |
| I. Authority Before Intelligence | PASS | Wizard actions call existing authority services and never create a second state source. |
| II. Provenance and Exact Evidence | PASS | Checks, changes, smoke results, explanations, activation, and rollback are receipted. |
| III. Safe Defaults and Reversibility | PASS | Discovery is read-only; setup defaults shadow/local and supports resume/rollback. |
| IV. Scope, Privacy, and Verifiable Deletion | PASS | Synthetic scoped data, cleanup, secret redaction, and safe support bundles are tested. |
| V. Contract-First Host Neutrality | PASS | One setup/health model composes host-specific actions without owning host state. |
| VI. Executable Claims | PASS | State-machine, interruption, parity, installed-example, and controlled usability evidence gate release. |
| VII. Local-First and Explicit Egress | PASS | Deterministic local flow works; every download/provider/egress choice is explicit. |

Re-check after design: all component compatibility, Python 3.10–3.13, licence, persisted-upgrade, and installed-package gates inherited from dependencies must pass.

## Design

1. Define resumable step, check, action, receipt, and health-domain contracts.
2. Discover state without mutation; plan changes and require per-boundary consent.
3. Execute idempotent steps with checkpoints and compensating rollback.
4. Use synthetic scoped memory to verify capture, admission, semantic paraphrase recall, context preparation, and evidence without touching user content.
5. Aggregate component health and map reason codes to state-valid CLI/dashboard actions.
6. Build a safe explanation composer from existing proposal/rank/policy/delivery evidence.

## Test Strategy

Fresh/existing/partial installs, every interruption point, consent refusal, missing optional services, host-version mismatch, secret redaction, activation guards, CLI/dashboard parity, synthetic-data cleanup, and installed examples.

## Rollout

Release read-only doctor/plan first, then resumable apply, then dashboard wizard. Existing setup commands remain supported until parity and rollback evidence are published.

## Project Structure

State-machine orchestration lives in `atmem/onboarding.py`; synthetic verification in `atmem/onboarding_verify.py`; CLI/dashboard render shared control-plane health/action/explanation models.

## Dashboard and CLI Integration

Follow `docs/dashboard-design-language.md`, preserve the four-workspace layout, and follow `specs/integration-ownership.md`: Spec 007 owns shared dashboard-shell integration and Spec 012 owns shared CLI routing/output conventions; this feature owns only onboarding/health modules and views.
