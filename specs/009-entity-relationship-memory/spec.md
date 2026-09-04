# Feature Specification: Entity and Relationship Memory

**Feature directory**: `specs/009-entity-relationship-memory`
**Created**: 2026-09-05
**Status**: Draft
**Input**: `todo.md` P1.6

## Overview

Represent canonical entities, aliases, types, and relations as evidence-bound derived structures so authorized multi-hop questions work without making the graph authoritative.

## User Scenarios & Testing

### User Story 1 - Traverse evidence-backed relationships (Priority: P1)

A scoped query resolves aliases to canonical entities and follows a configured number of authorized edges. Every node/edge points to eligible canonical memory and exact source evidence.

**Why this priority**: Relationship recall is valuable only when every traversal remains authorized and auditable.

**Independent Test**: Query a two-hop fixture containing an inaccessible alternative edge and verify the authorized path/evidence only.

**Acceptance Scenario**: **Given** an authorized bounded relationship query, **when** traversal runs, **then** every returned node and edge reconciles to eligible evidence.

### User Story 2 - Repair identity over time (Priority: P2)

Operators can merge, split, rename, supersede, and delete entities with previews, conflict checks, lineage, derived-index repair, and reversible receipts.

**Why this priority**: Identity errors otherwise compound across every relationship query.

**Independent Test**: Preview and commit each identity mutation, rebuild the graph, and compare lineage and results before/after rollback.

**Acceptance Scenario**: **Given** an authorized identity repair, **when** it commits, **then** lineage and derived repair are receipted without changing unrelated entities.

### Edge Cases

- Cycles, alias collisions, self-relations, evidence deletion, temporal edge conflicts, and traversal budget exhaustion return bounded explicit results.
- A node visible in scope does not make an inaccessible edge or neighbor visible.
- Interrupted identity mutation leaves either the prior generation active or a visible repair state.

## Requirements

### Functional Requirements

- **FR-001**: Entities MUST have stable IDs, normalized names, aliases, types, scope, lifecycle, and supporting canonical record/evidence references.
- **FR-002**: Relations MUST identify subject, predicate, object, confidence, validity interval, and one or more eligible evidence references.
- **FR-003**: Entity/edge materialization MUST be derived and rebuildable; canonical memory remains authoritative.
- **FR-004**: Traversal MUST authorize every node and edge, enforce hop/candidate/byte limits, detect cycles, and revalidate before delivery.
- **FR-005**: Merge, split, rename, delete, and supersede MUST preserve lineage and update or invalidate graph/vector/cache copies atomically or via visible repair state.
- **FR-006**: Alias resolution ambiguity MUST withhold or request review rather than silently join identities.
- **FR-007**: CLI/dashboard explanations MUST show the safe path, evidence, scope/policy decisions, and omissions without revealing inaccessible graph structure.

### Key Entities

- **Entity**: Stable scoped identity with names, aliases, types, lifecycle, and evidence links.
- **Relation**: Directed typed edge with validity, confidence, and canonical support.
- **Authorized Path**: Bounded sequence of individually authorized nodes/edges and evidence.
- **Identity Mutation Receipt**: Preview, lineage, affected derivatives, and commit/rollback result.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Graph fixtures measure entity resolution, edge precision/recall, bounded multihop accuracy, and ambiguous-alias withholding.
- **SC-002**: Cross-scope node, edge, path, and explanation leakage is zero across adversarial tests.
- **SC-003**: Every returned path reconciles to currently eligible canonical records and evidence.
- **SC-004**: All identity mutations pass rebuild, deletion, backup/restore, and rollback tests.

## Out of Scope

An authoritative knowledge graph, unbounded traversal, or inferred edges without labeled evidence and confidence.

## Assumptions

- Spec 008 provides the signal registry and rank/explanation contracts.
- Graph materialization is always reproducible from canonical eligible records.
- Ambiguous alias resolution requires review rather than probabilistic auto-merge.
