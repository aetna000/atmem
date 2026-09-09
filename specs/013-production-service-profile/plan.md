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
| VII. Local-First, Explicit Egress, and Replaceable Intelligence | PASS | Production is opt-in; single-user local operation remains supported and intelligence providers remain replaceable service dependencies. |

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


## Unified product integration plan — 2026-09-09

Implement production service hardening against existing 010/012/015 contracts; 024 and 025 are downstream consumers. Use [integration ownership](../integration-ownership.md) and [roadmap order](../product-roadmap.md). Baseline prerequisites refer to existing implementations, not completion of all later amendments.

Touch points (existing or proposed tests): `atmem/server/auth.py`, `atmem/server/config.py`, `atmem/server/jobs.py`, `tests/server/`. Close durable credential and end-to-end production-route enforcement gaps. Reuse the existing application service and authoritative capability response. Public fields are additive/versioned; persisted changes require allocated migrations, real published-floor upgrade/recovery tests and no inferred historical relationships. UI shell ownership transfers to Spec 022; this feature supplies its view models.

Verification: write boundary fixtures for FR-010, FR-011, SC-005 before integration, then run the affected native/delegated, scope, fallback and interface regressions. Missing live-provider or real-host evidence is reported as unavailable, never substituted by a mock pass. Constitution I–VII remain binding; this amendment does not change the constitution or delegate canonical memory authority.

## FR-010 detailed credential and enforcement architecture

T010 is a roll-up marker for T012–T025. The current in-memory `KeyAuthority` does not satisfy durable production authentication.

| Work package | Tasks | Owning artifacts |
| --- | --- | --- |
| Identity and trust contract | T012 | Principal/credential schemas and production threat model |
| Durable credential storage | T013–T014 | `atmem/server/credential_store.py`, `auth.py`, allocated migrations |
| Rotation/revocation and audit | T015–T016 | Transactional generations, idempotency, `admin_audit.py` |
| Replica consistency | T017 | Repository reads, cache generations, measured propagation policy |
| Actual request/route enforcement | T018–T019 | `control/web.py`, production auth, application operation matrix |
| Jobs and secondary surfaces | T020–T021 | Worker claim/effect checks, caches, exports, metrics and audit |
| Recovery and degraded profiles | T022–T023 | Revocation-safe restore, partitions and fail-closed startup |
| Installed evidence and handoff | T024–T025, then T011 | Two-replica installed suite, journal and operations guide |

Store opaque high-entropy credential verifiers with tenant/principal identity and versioned role/scope/expiry/revocation state. Public APIs expose safe metadata only. Rotation defines explicit overlap or immediate replacement; concurrent rotation/revocation uses expected generations and scoped idempotency. Administrative changes and their audit evidence commit together or remain a visibly unsuccessful operation.

Freeze authoritative-read and propagation behavior in T012/T017. Cached success cannot outlive the declared revocation bound; privileged operations that cannot establish sufficiently current authority withhold. Test the actual network boundary and worker effect boundary, not a configuration flag. A caller-provided role/tenant header is untrusted unless it is carried through the explicitly authenticated configured proxy boundary.

Restore must not silently reactivate a previously revoked credential. Preserve a current revocation authority outside the restored snapshot, or quarantine restored credentials and require explicit reissuance when currency cannot be established. Record which strategy a deployment supports; do not assume a stale database proves current permission. In-flight effects remain separate from authorization of future operations.

The route matrix is derived from registered production operations; new 012/024/025 routes need explicit decisions and boundary tests. Contract freeze can precede those routes, but their enterprise claims require their own acceptance. T012 consumes the existing 012 principal contract; membership T016 consumes T012. This is a contract handoff, not a dependency on completed future consumers or fleet availability.
