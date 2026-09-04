# Implementation Plan: Entity and Relationship Memory

**Branch**: `future/009-entity-relationship-memory` | **Date**: 2026-09-05 | **Spec**: `specs/009-entity-relationship-memory/spec.md`

**Input**: Feature specification from `specs/009-entity-relationship-memory/spec.md`

## Summary

Move graph behavior into an evidence-bound derived package and register bounded entity/graph retrieval through Spec 008's extension point.

## Technical Context

- **Language/Version**: Python 3.10–3.13.
- **Dependencies**: Spec 008 signal registry; existing SQLite graph behavior.
- **Storage**: Rebuildable evidence-bound derived graph; canonical memory remains authoritative.
- **Testing/Target**: pytest graph quality, mutation, compatibility, privacy, deletion, and recovery suites.
- **Constraints/Scale**: Hard hop/candidate/byte bounds and compatible `atmem.graph` imports.

Evolve `atmem/graph/` behind a versioned derived-graph interface, add canonical entity-operation receipts, and register authorized entity/graph candidates through Spec 008's signal extension contract. SQLite remains the first backend; Spec 008 retains ownership of the base ranker and `atmem/retrieve/signals.py`.

## Constitution Check

| Principle | Gate | Evidence required |
| --- | --- | --- |
| I. Authority Before Intelligence | PASS | Graph is derived; every node/edge/path is authorized and revalidated. |
| II. Provenance and Exact Evidence | PASS | Entities, relations, paths, and mutations link to canonical evidence and lineage. |
| III. Safe Defaults and Reversibility | PASS | Ambiguous identity withholds/reviews; edits preview and preserve reversible lineage. |
| IV. Scope, Privacy, and Verifiable Deletion | PASS | Per-edge checks, hard bounds, and deletion/rebuild verification prevent leakage. |
| V. Contract-First Host Neutrality | PASS | Graph contracts and the Spec 008 signal plugin are host-neutral. |
| VI. Executable Claims | PASS | Quality, path reconciliation, mutation, privacy, and recovery tests gate claims. |
| VII. Local-First and Explicit Egress | PASS | SQLite graph derivation is local and needs no hosted intelligence. |

Re-check after design: public `atmem.graph` imports and existing graph tests MUST remain compatible through the module-to-package move.

## Design

1. Define entity, alias, relation, path, evidence, and mutation-receipt contracts.
2. Materialize graph generations from eligible canonical records with deterministic IDs.
3. Resolve aliases conservatively; quarantine ambiguous merges.
4. Traverse with per-edge authorization and hard hop/candidate/byte budgets.
5. Implement staged identity mutations plus repair/rebuild and shared CLI/dashboard inspection.

## Cross-Spec Dependencies

- **Spec 008**: required signal registry, rank-decision, explanation, calibration, and final revalidation contracts. This feature supplies only the entity/graph plugin.

## Project Structure

Graph models, identity, storage, and traversal live under `atmem/graph/`; the only retrieval integration is `atmem/retrieve/graph_signal.py`; shared ranker files remain owned by Spec 008.

## Dashboard and CLI Integration

Follow `docs/dashboard-design-language.md`, preserve the four-workspace layout, and follow `specs/integration-ownership.md`: Spec 007 owns shared dashboard-shell integration and Spec 012 owns shared CLI routing/output conventions.

## Test Strategy

Golden graph quality fixtures, ambiguity/property tests, cross-scope adversaries, cycle/budget tests, temporal supersession, mutation fault injection, deletion verification, and rebuild equivalence.

## Rollout

Build/read in shadow mode, compare to existing graph behavior, then enable bounded candidates. Schema additions are backward-compatible and derived state can be discarded.
