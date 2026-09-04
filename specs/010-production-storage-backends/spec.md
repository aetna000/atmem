# Feature Specification: Production Storage Backends

**Feature directory**: `specs/010-production-storage-backends`
**Created**: 2026-09-05
**Status**: Draft
**Input**: `todo.md` P1.7–P1.8

## Overview

Scale AtMem beyond one local process through versioned canonical-store and derived-index interfaces, PostgreSQL, pgvector, and Qdrant, while preserving SQLite/local sidecar defaults and proving that optimizations cannot serve stale or unauthorized context.

## User Scenarios & Testing

### User Story 1 - Select and operate a backend (Priority: P1)

An operator configures PostgreSQL canonical storage and an optional pgvector or Qdrant derived index, verifies compatibility/health, migrates or restores data, and can rebuild all derived state from canonical records.

**Why this priority**: Production scale requires replaceable storage without transferring authority to an index.

**Independent Test**: Run the backend conformance suite against one canonical backend and rebuild a selected derived backend from it.

**Acceptance Scenario**: **Given** a declared backend configuration, **when** conformance and health pass, **then** canonical transactions and derived rebuilds expose their exact supported guarantees.

### User Story 2 - Meet measured performance safely (Priority: P2)

Profiling separates candidate generation, database indexes, graph search, reranking, context preparation, and evidence recording. Caches bind scope, authority generation, policy/topology/model/index identities, and exact output bytes.

**Why this priority**: Performance work must not create stale or cross-scope context.

**Independent Test**: Run the reference workload with cold/warm/degraded paths and adversarial invalidation between cache creation and use.

**Acceptance Scenario**: **Given** the reference dataset and concurrency, **when** benchmarks run, **then** stage metrics and p95 gates are reported and no invalid cache entry is delivered.

### Edge Cases

- Network partition, transaction retry, replica/index lag, partial derived writes, stale cache entries, and interrupted restore never become authoritative successes.
- Unsupported capability calls return structured errors rather than emulation with weaker guarantees.
- Connection secrets and private query content are absent from plans, traces, metrics, and benchmark reports.

## Requirements

### Functional Requirements

- **FR-001**: Publish versioned canonical-store and derived-index interfaces with capability negotiation and structured unsupported errors.
- **FR-002**: SQLite/local sidecar MUST remain the zero-service default; PostgreSQL MUST be a canonical option; pgvector and Qdrant MUST be optional derived indexes.
- **FR-003**: Vector/graph/cache backends MUST never become canonical or authorize records.
- **FR-004**: Each backend MUST support or explicitly reject transactional mutation, concurrency control, rebuild, backup, restore, migration, and verified deletion.
- **FR-005**: Cross-backend conformance MUST prove scope/lifecycle filtering, lineage, receipts, crash recovery, and derived rebuild equivalence.
- **FR-006**: The reference scale profile MUST cover 1,000,000 canonical records, 10 concurrent query workers, and 50 concurrent capture workers. On the published reference hardware/configuration, warm authorized retrieval through final context preparation MUST achieve p95 ≤ 250 ms, canonical capture commit p95 ≤ 100 ms, and degraded deterministic retrieval p95 ≤ 500 ms; reports MUST also include cold measurements without using them to satisfy warm targets.
- **FR-007**: Profiling MUST attribute latency and candidate counts to each retrieval/delivery stage without recording private content.
- **FR-008**: Database indexes MUST be justified by captured query plans and regression measurements.
- **FR-009**: Cache keys MUST include exact scope and all relevant generations/digests; invalidation MUST cover memory, policy, topology, model, index, lifecycle, and deletion changes.
- **FR-010**: A cache hit MUST still pass current authorization/lifecycle revalidation and reproduce receipt-bound byte-stable output.
- **FR-011**: Secrets, TLS modes, connection failures, lag, and partial outages MUST have safe health/degradation semantics.
- **FR-012**: Every optional Python driver and service client MUST support Python 3.10–3.13 and have Apache-2.0-compatible enterprise licensing; the base install MUST remain free of those dependencies.
- **FR-013**: Any SQLite schema change introduced by interface adaptation, caching, or migration metadata MUST pass real persisted upgrades from every supported published AtMem upgrade floor with rollback/forward-recovery evidence.

### Key Entities

- **Backend Capability Manifest**: Versioned operations and guarantees a backend supports.
- **Canonical Transaction**: Authoritative mutation with generation, idempotency, and commit evidence.
- **Derived Generation**: Rebuildable vector/index epoch tied to canonical and model identities.
- **Cache Entry**: Scope/generation/digest-bound byte result subject to current revalidation.
- **Performance Report**: Dataset, hardware, configuration, stage samples, and percentile outcome.

## Success Criteria

### Measurable Outcomes

- **SC-001**: One conformance suite passes for SQLite and PostgreSQL canonical stores and each derived backend’s declared capabilities.
- **SC-002**: Fault tests prove no acknowledged canonical mutation is lost and no failed/partial derived write becomes authoritative.
- **SC-003**: Cache adversaries produce zero stale, cross-scope, deleted, or policy-invalid deliveries.
- **SC-004**: A reproducible target-scale run publishes hardware, configuration, dataset digest, concurrency, cold/warm/degraded samples, and percentile method; it either meets every FR-006 p95 threshold or fails the release gate explicitly.
- **SC-005**: Clean-install and dependency audits pass on Python 3.10–3.13, find no incompatible licence, and prove optional backend imports are absent from the base path.

## Out of Scope

Replacing canonical truth with a vector database, automatic production provisioning, or unsupported multi-region consensus.

## Assumptions

- Specs 005 and 008 define semantic epoch and retrieval/cache identities.
- Reference performance hardware will be recorded with each report rather than implied universally.
- Optional services and drivers are installed through explicit extras.
