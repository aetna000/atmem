# Implementation Plan: Memory Lifecycle Controls

**Branch**: `future/015-memory-lifecycle-controls` | **Date**: 2026-09-05 | **Spec**: `specs/015-memory-lifecycle-controls/spec.md`

**Input**: Feature specification from `specs/015-memory-lifecycle-controls/spec.md`

## Summary

Centralize lifecycle timestamps, eligibility, policy transitions, derived invalidation, and verified forgetting behind one governed service.

## Technical Context

- **Language/Version**: Python 3.10–3.13.
- **Dependencies**: Existing policy/storage plus Spec 010 registry for production derived backends.
- **Storage**: Additive SQLite lifecycle fields, immutable transition receipts, derived invalidation state.
- **Testing/Target**: pytest state-machine/time/property/migration/deletion and cross-surface suites.
- **Constraints/Scale**: Explicit trusted time, scope-bound policy, no unexplained deletion, honest backup boundary.

Extend canonical models/storage migrations and policy evaluation; add a lifecycle service, scheduler-friendly scan API, invalidation events, verification receipts, and shared CLI/dashboard/API projections.

## Constitution Check

| Principle | Gate | Evidence required |
| --- | --- | --- |
| I. Authority Before Intelligence | PASS | AtMem alone evaluates eligibility and commits lifecycle transitions. |
| II. Provenance and Exact Evidence | PASS | State timelines retain actor, reason, precondition, evidence, time, and receipt. |
| III. Safe Defaults and Reversibility | PASS | Automatic expiry starts disabled; previews, review, restore, and rollback are explicit. |
| IV. Scope, Privacy, and Verifiable Deletion | PASS | Invalidation spans canonical, graph, vector, cache, context, and backup truth. |
| V. Contract-First Host Neutrality | PASS | Lifecycle state machine and policy contracts are shared across all surfaces/backends. |
| VI. Executable Claims | PASS | Transition, time-boundary, deletion, migration, and published-upgrade tests are gates. |
| VII. Local-First and Explicit Egress | PASS | Lifecycle evaluation is deterministic/local and needs no model. |

SQLite migration gate: test real persisted state from every supported published AtMem upgrade floor on Python 3.10–3.13, including rollback/forward recovery.

## Design

1. Define lifecycle state machine, timestamp semantics, policy precedence, and reason codes.
2. Migrate legacy records with neutral defaults and retain rollback compatibility.
3. Centralize eligibility and typed transitions with optimistic generations.
4. Emit transactional invalidation work for every derived consumer and track verification.
5. Implement policy preview/scans and optional decay/promotion proposals.
6. Project one timeline/action model to all surfaces.

## Test Strategy

State-machine/property tests, clock-boundary tests, concurrent edits, policy precedence, derived invalidation fault recovery, backup-policy verification, migration rollback, and cross-surface contract tests.

## Rollout

Migrate/display first with no automatic expiry. Enable preview-only scans, then explicitly configured policies after verification gates and backup documentation pass.

## Cross-Spec Dependency

Spec 010 supplies optional production backend conformance and derived-store registration. Spec 015 can begin on SQLite, but production-backend deletion verification and cache invalidation gates require Spec 010.

## Project Structure

Models, policy, service, and invalidation live under `atmem/lifecycle/`; canonical migrations remain in `atmem/store/sqlite.py`; all UI/API projections consume one lifecycle view model.

## Dashboard and CLI Integration

Follow `docs/dashboard-design-language.md`, preserve the four-workspace layout, and follow `specs/integration-ownership.md`: Spec 007 owns shared dashboard-shell integration and Spec 012 owns shared CLI routing/output conventions.
