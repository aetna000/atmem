# Implementation Plan: Semantic Setup and Health

**Branch**: `future/005-semantic-setup-and-health` | **Date**: 2026-09-05 | **Spec**: `specs/005-semantic-setup-and-health/spec.md`

**Input**: Feature specification from `specs/005-semantic-setup-and-health/spec.md`

## Summary

Add hardware-aware local embedding setup, authoritative semantic-index health, and staged rebuilds while preserving deterministic hashing.

## Technical Context

- **Language/Version**: Python 3.10–3.13; existing dashboard JavaScript.
- **Dependencies**: Base standard-library hashing; optional local embedding runtimes behind extras.
- **Storage**: Canonical SQLite plus rebuildable local semantic epochs.
- **Testing/Target**: pytest on supported desktop/server platforms, clean base install, fake-provider integration, and dashboard contract tests.
- **Constraints/Scale**: Explicit downloads/egress, atomic epoch activation, hardware-aware bounded recommendations, existing-store coverage.

Extend `atmem/semantic/providers.py` and `index.py`; add health/orchestration in `atmem/semantic/health.py`; expose commands in `atmem/cli.py` and shared control-plane JSON through `atmem/control/server.py` and `assets/app.js`. Keep optional model runtimes behind extras.

## Constitution Check

| Principle | Gate | Evidence required |
| --- | --- | --- |
| I. Authority Before Intelligence | PASS | Only authorized eligible canonical records enter embedding; index results are revalidated. |
| II. Provenance and Exact Evidence | PASS | Manifests bind model, revision, dimensions, digest, generation, and coverage. |
| III. Safe Defaults and Reversibility | PASS | Hashing remains default; rebuilds stage and atomically activate with rollback. |
| IV. Scope, Privacy, and Verifiable Deletion | PASS | Scope/lifecycle filtering precedes embedding and deletion invalidates vectors. |
| V. Contract-First Host Neutrality | PASS | Health/setup contracts are shared by CLI, dashboard, and hosts. |
| VI. Executable Claims | PASS | Fault, parity, smoke, and fallback tests back setup and health claims. |
| VII. Local-First and Explicit Egress | PASS | Downloads and remote access require consent; offline hashing remains useful. |

Re-check after design: Python 3.10–3.13, backward compatibility, and base-install tests remain release gates.

## Design

1. Define a versioned `SemanticManifest` and health-state evaluator independent of UI.
2. Add a checked-in model catalog containing resource bands and provenance, not silent installers.
3. Implement `semantic setup|status|rebuild|verify` with human and stable JSON output.
4. Build into an inactive epoch, checkpoint progress, reconcile canonical generation/deletions, validate dimensions and coverage, then atomically switch.
5. Serve the same health payload and allowed actions to the dashboard; disable unsafe actions by state.

## Test Strategy

Unit-test manifests and recommendations; integration-test setup with fake local providers; fault-test rebuild checkpoints and concurrent mutation; contract-test CLI/dashboard parity; regression-test no optional dependencies and authorization/deletion behavior.

## Rollout

Ship status first, then opt-in setup/rebuild. Existing indexes are reported as legacy/unknown until rebuilt; no automatic model download or epoch activation occurs.

## Project Structure

Implementation stays in `atmem/semantic/`, with public orchestration in `atmem/cli.py`, control-plane projections in `atmem/control/`, tests in `tests/`, and operator guidance in `docs/semantic-search.md`.

## Dashboard and CLI Integration

Follow `docs/dashboard-design-language.md`, preserve the four-workspace layout, and follow `specs/integration-ownership.md`: Spec 007 owns shared dashboard-shell integration and Spec 012 owns shared CLI routing/output conventions.
