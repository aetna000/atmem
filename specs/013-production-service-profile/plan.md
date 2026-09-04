# Implementation Plan: Production Service Profile

**Branch**: `future/013-production-service-profile` | **Date**: 2026-09-05 | **Spec**: `specs/013-production-service-profile/spec.md`

**Input**: Feature specification from `specs/013-production-service-profile/spec.md`

## Summary

Compose production storage, public API, and lifecycle semantics into an explicitly activated authenticated multi-tenant service profile.

## Technical Context

- **Language/Version**: Python 3.10–3.13; deployment/service versions pinned by operations guide.
- **Dependencies**: Specs 010/012/015 plus optional TLS, secret, metrics, and worker integrations.
- **Storage**: Production canonical/derived backends, scoped jobs, administrative audit, encrypted backups.
- **Testing/Target**: pytest security/recovery plus isolated deployment load, failure, and DR drills.
- **Constraints/Scale**: Exact tenant isolation, authenticated TLS, declared quota/RPO/RTO targets, local profile preserved.

Build on Spec 010 storage, Spec 012 API, and Spec 015 lifecycle/retention semantics. Add production configuration, principals/keys/RBAC, tenant-bound repositories, worker protocol, OpenTelemetry-compatible metrics, and backup orchestration as optional service components.

## Constitution Check

| Principle | Gate | Evidence required |
| --- | --- | --- |
| I. Authority Before Intelligence | PASS | Service layers route authority through tenant-bound canonical repositories. |
| II. Provenance and Exact Evidence | PASS | Principal, request, job, audit, backup, and restore identities are bound. |
| III. Safe Defaults and Reversibility | PASS | Production mode rejects incomplete config; local mode and rollback remain. |
| IV. Scope, Privacy, and Verifiable Deletion | PASS | Isolation covers APIs, stores, jobs, caches, metrics, logs, exports, and backups. |
| V. Contract-First Host Neutrality | PASS | Builds on Specs 010/012/015 without redefining their contracts. |
| VI. Executable Claims | PASS | Isolation, key, quota, load, recovery, RPO, and RTO gates back readiness. |
| VII. Local-First and Explicit Egress | PASS | Production is opt-in; single-user local operation remains supported. |

Re-check after design: Python 3.10–3.13, enterprise-safe dependency licensing, and published persisted-state upgrades remain release gates.

## Design

1. Threat-model trust boundaries and define principal/role/key/job/audit contracts.
2. Enforce tenant filters structurally in repositories and service methods, not caller convention.
3. Validate TLS, secret providers, encryption, retention, and quotas before binding non-loopback.
4. Add idempotent leased workers with scope-preserving payload references.
5. Export content-free health/metrics and separately protected admin audit.
6. Automate encrypted backup, restore verification, and disaster-recovery drills.

## Cross-Spec Dependencies

- **Spec 010**: production canonical/derived storage, cache, backup primitives, and performance evidence.
- **Spec 012**: public service/API contract and agent-versus-admin operation separation.
- **Spec 015**: authoritative retention, expiry, archival, and lifecycle eligibility semantics; Spec 013 configures and operates these policies but does not redefine them.

## Project Structure

Production-only authentication, repositories, jobs, observability, configuration, and recovery live under `atmem/server/`; the public service contract remains in Spec 012's `atmem/service/` package.

## Test Strategy

Authorization matrix and tenant adversaries, key lifecycle, TLS/config rejection, quota races, job replay/lease expiry, observability redaction, backup corruption/restore/deletion, and load/failure testing.

## Rollout

Keep behind an explicit `production` profile. Require preflight and recovery rehearsal before readiness; preserve loopback defaults and provide rollback documentation.
