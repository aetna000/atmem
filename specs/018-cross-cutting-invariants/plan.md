# Implementation Plan: Cross-Cutting Invariant Conformance

**Branch**: `future/018-cross-cutting-invariants` | **Date**: 2026-09-05 | **Spec**: `specs/018-cross-cutting-invariants/spec.md`

**Input**: Feature specification from `specs/018-cross-cutting-invariants/spec.md`

## Summary

Define eleven product-level invariants as a versioned registry, back each with executable assertions against the installed package, require feature specs to attest to the invariants they touch, and fail the release gate on any regression, missing assertion, or missing attestation.

## Technical Context

- **Language/Version**: Python 3.10–3.13.
- **Dependencies**: Standard library and pytest only; no optional extra, model provider, or network may be required.
- **Storage**: None canonical. The registry is a checked-in versioned document; reports are build artifacts.
- **Testing/Target**: pytest suite executed against the installed wheel in CI across the supported version matrix.
- **Constraints/Scale**: Deterministic, offline, synthetic-data-only, content-minimizing, and fast enough to run on every pull request.

Add `atmem/invariants/` for the registry, verdict model, attestation loader, and report writer. Assertions live in `tests/invariants/`, one module per invariant, reusing existing fixtures rather than duplicating feature tests.

## Constitution Check

| Principle | Gate | Evidence required |
| --- | --- | --- |
| I. Authority Before Intelligence | PASS | The suite observes and asserts; it never admits, authorizes, or mutates memory. |
| II. Provenance and Exact Evidence | PASS | Every verdict cites executing assertions and names gaps instead of implying proof. |
| III. Safe Defaults and Reversibility | PASS | A missing, skipped, or unrunnable assertion fails closed as unproven, never as pass. |
| IV. Scope, Privacy, and Verifiable Deletion | PASS | Synthetic scoped fixtures only; reports carry no secrets or scoped content. |
| V. Contract-First Host Neutrality | PASS | The registry is host-neutral; host-specific proofs are declared configurations. |
| VI. Executable Claims | PASS | This feature exists to make eleven customer-visible claims executable at their boundary. |
| VII. Local-First, Explicit Egress, and Replaceable Intelligence | PASS | The suite runs offline with no provider, and proves the deterministic fallback path itself. |

No SQLite schema change is introduced. `INV-011` consumes the published-version upgrade fixtures owned by Spec 010's migration sequence rather than adding its own.

## Design

1. Freeze the invariant registry schema: stable ID, guarantee statement, governing principle, owning assertions, declared configurations, verdict, and amendment history.
2. Encode `INV-001`–`INV-011` from the `todo.md` guarantee list, each citing the constitution principle it enforces.
3. Capture the baseline from the behavior shipped by Specs 001–004, so later specs are measured against a real starting point rather than an aspiration.
4. Implement the verdict evaluator: an invariant is `proven` only when every declared configuration has an executing assertion, `partially_proven` when a configuration is uncovered and named, and `unproven` when an assertion is missing, skipped, or unrunnable.
5. Implement the attestation loader that reads each feature spec's declared invariant IDs, rejects conflicts, and fails on an unattested change to an invariant-bearing surface.
6. Add mutation coverage: a seeded violation harness that proves each assertion fails for the right invariant and only that one.
7. Emit a content-minimized report consumed by CI and `docs/invariants.md`.

## Test Strategy

Registry schema and validation tests; one assertion module per invariant reusing existing authority, retrieval, context, deletion, blackbox, OpenClaw-restore, fallback, and upgrade fixtures; mutation tests proving each guard fails correctly; offline and no-extras packaging tests; attestation conflict and omission tests; redaction tests over the full report surface.

## Rollout

Land the registry and baseline first with the gate advisory, so existing gaps surface as `partially_proven` or `unproven` without blocking. Publish the gap list, close it, then make the gate blocking before Spec 005 changes an invariant-bearing surface. Attestation becomes mandatory for specs from 005 onward once the gate is blocking.

## Cross-Spec Dependency

None. This spec asserts behavior that Specs 001–004 already ship, and is a prerequisite guard for Specs 005–017 rather than a consumer of them. `INV-011` reuses the upgrade fixtures under `tests/fixtures/upgrades/` shared with the Spec 010-owned migration sequence.

## Project Structure

Registry, verdict model, attestation loader, and report writer live under `atmem/invariants/`; the schema lives in `atmem/schemas/v1/invariant-registry.json`; assertions live under `tests/invariants/`; the published gap list and guarantee documentation live in `docs/invariants.md`.

## Dashboard and CLI Integration

This feature adds no dashboard workspace and no user-facing CLI command family. The conformance report is a build artifact surfaced through CI and `docs/invariants.md`. Ownership of the invariant registry is recorded in `specs/integration-ownership.md`.
