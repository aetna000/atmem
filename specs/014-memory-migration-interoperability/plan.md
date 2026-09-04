# Implementation Plan: Memory Migration and Interoperability

**Branch**: `future/014-memory-migration-interoperability` | **Date**: 2026-09-05 | **Spec**: `specs/014-memory-migration-interoperability/spec.md`

**Input**: Feature specification from `specs/014-memory-migration-interoperability/spec.md`

## Summary

Add neutral evidence-preserving archives and governed Mem0 import with deterministic dry-run, review, resume, verification, and rollback receipts.

## Technical Context

- **Language/Version**: Python 3.10–3.13.
- **Dependencies**: Spec 006 proposal/review service; standard-library streaming formats by default.
- **Storage**: Neutral archive files plus canonical checkpoint/idempotency/receipt state.
- **Testing/Target**: pytest golden formats, tamper, resume/replay, conflict, rollback, and round-trip suites.
- **Constraints/Scale**: Streaming bounded memory, explicit scope mapping, no foreign index authority.

Add `atmem/interchange/` contracts, readers/writers, planner, checkpoints, and receipts. Route proposed records through the Spec 006 validator/review and expose commands plus API operations with agent/admin separation.

## Constitution Check

| Principle | Gate | Evidence required |
| --- | --- | --- |
| I. Authority Before Intelligence | PASS | Imported records pass normal proposal, policy, review, and canonical admission. |
| II. Provenance and Exact Evidence | PASS | Archive/source digests, mappings, counts, loss, checkpoints, and receipts persist. |
| III. Safe Defaults and Reversibility | PASS | Dry-run precedes commit; batches are resumable/idempotent with rollback. |
| IV. Scope, Privacy, and Verifiable Deletion | PASS | Scope mapping is explicit; export and rollback reapply lifecycle/redaction policy. |
| V. Contract-First Host Neutrality | PASS | Neutral versioned schemas prevent Mem0 or AtMem lock-in. |
| VI. Executable Claims | PASS | Golden versions, tamper, replay, conflict, round-trip, and rollback tests gate claims. |
| VII. Local-First, Explicit Egress, and Replaceable Intelligence | PASS | Archive operations are local, introduce no intelligence dependency, and import never creates a foreign authority database. |

Re-check after design: imported SQLite mutations use the existing canonical schema or trigger published-version upgrade tests if that schema changes.

## Design

1. Freeze neutral manifest/record/evidence/history and receipt schemas with canonical digests.
2. Parse Mem0 exports into normalized proposals while recording source-field mapping/loss.
3. Plan deterministically against canonical fact keys and lifecycle state.
4. Commit reviewed batches transactionally with checkpoint/idempotency receipts.
5. Export authorized snapshots and verify archive digests; support restore-like validation without admission.

## Test Strategy

Golden format versions, dry-run/commit reconciliation, resume/replay, conflicts/review, scope mapping, tampering, partial batches, rollback, round-trip fidelity, deletion/retention, and optional real-version fixtures.

## Rollout

Ship neutral export and dry-run first; gate commit imports behind explicit admin action and backup recommendation. Format versions remain readable for the declared support window.

## Cross-Spec Dependency

Spec 006 supplies typed proposal validation and review. Import planning may run without AtBot and foreign vectors/graphs are never authoritative.

## Project Structure

Schemas, readers, planning, export, import, checkpoints, and receipts live under `atmem/interchange/`; surfaces reuse CLI/API; fixtures and format docs live under `tests/` and `docs/`.
