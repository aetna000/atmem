# Tasks

## Facts and contracts
- [x] T001 Inventory current main, licence, schemas, transport, memory/scope/encryption/deletion/auth in research.md; record official-source revisions (FR-001).
- [x] T002 Define cloud storage, authority, tool and consent contracts in contracts.md; check spec/plan/task coverage (FR-002–FR-009, FR-014).

## Real cloud service
- [x] T003 Implement optional config/crypto and durable Firestore generation/chunk repository in atmem/chatgpt (FR-007–FR-009).
- [x] T004 Implement authenticated scoped service using real Memory operations and atomic pending/approval/commit/version/idempotency/receipt paths (FR-002, FR-004–FR-008).
- [x] T005 Implement OAuth/Firebase identity, resource-bound grants, discovery, revocation and secure browser consent/approval routes (FR-003, FR-005, FR-009, FR-014).
- [x] T006 Expose bounded annotated MCP tools, errors, health and CLI in atmem/chatgpt; add optional package extra without core default changes (FR-003, FR-006, FR-009).

## Evaluation
- [x] T007 Add real Firestore/Auth emulator and MCP integration harness; cover lifecycle, consent, isolation, conflicts, retries, offline, revocation and audit (FR-012, SC-001–SC-003).
- [x] T008 Test clean/repeated setup, upgrade/restart and actual memory/MCP regression; clean synthetic data and retain secretless evidence (FR-012, SC-003, SC-005).

## Package and handoff
- [x] T009 Prepare valid development plugin, skill, logo, metadata, exactly 5 positive/3 negative review cases and reproducible validator/packager (FR-010, SC-004).
- [x] T010 Write docs/chatgpt architecture/threat/permissions/install/uninstall/runbook/privacy/terms/reviewer/demo and evidence/Pro 100 matrix (FR-011, FR-014).
- [x] T011 Prepare deploy/chatgpt Firebase/Cloud Run design with durability, secret, quota and billing controls; owner-approved isolated atmemai pilot added (FR-013).
- [x] T012 Build/inspect package and real evidence; commit source, report readiness/blockers and exact owner steps; stop before directory submission/publication; record authorized hosting separately (SC-004, SC-006).

## Actual platform gates
Implementation tasks do not certify actual ChatGPT account invocation, individual
verification, public policy/demo/reviewer readiness or submission approval. See
docs/chatgpt/verification.md for measured results and remaining gates.

- [x] T013 Implement Firebase registration/verified-email/recovery and delivery throttles; test real emulator signup, verification, linkage, refresh and disabled-user rejection (FR-015).

Managed evidence: 18 checks passed against the real HTTPS pilot, with independent
engine/audit inspection and synthetic-household cleanup. Actual ChatGPT and
public-directory gates remain explicitly unverified, not completed by T012.

## Public directory completion
- [x] T014 Implement account fence, atomic staging and indexed control cleanup; test stale/concurrent writes and legacy token denial (FR-016).
- [x] T015 Implement fresh Firebase account deletion preview/confirm/retry and accurate receipts; test real Auth/Firestore lifecycle without targeting real users (FR-016).
- [x] T016 Implement official ChatGPT CIMD and truthful OAuth discovery/issuer; test SSRF/redirect/method/cache bounds plus real official metadata (FR-017).
- [x] T017 Implement encrypted snapshot recovery and actual engine/audit/wrong-key/deleted-account gates (FR-018).
- [x] T018 Prepare cloud product/support/privacy/terms in private website PR, with build/gates/browser evidence; owner merge/deployment status separate (FR-019).
- [ ] T019 Rebuild cloud candidate package and installed artifact, validate/deploy exact source, record managed new-feature evidence and remaining public gates (FR-020).
- [ ] T020 Complete actual ChatGPT account cases/demo, publisher verification, owner policy/country/commerce decisions and portal scans; submit/publish only within explicit authorized review actions (FR-020).

T018 evidence: private website PR #34, build/gates/docs and 55 browser tests passed;
owner merge and live publication remain pending, not certified by this task.
T019 in progress: installed artifact suite 38 passed; native regression 50 passed
and 1 platform-specific skip. Final cloud deployment/managed checks pending.
