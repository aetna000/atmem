# Tasks: Local User Management

**Status**: Complete for AtMem 2.3.0
**Input**: [spec.md](spec.md), [plan.md](plan.md)
**Evidence policy**: Record verification under `docs/implementation-evidence/029/`.

## Phase 1 — Identity foundation

- [x] [T001] Define local account/session/security-audit models, canonical username validation, four-role authority and password policy in `atmem/identity/models.py` and `atmem/evidence/models.py`, with unit tests in `tests/test_local_identity.py` (FR-001–FR-002, FR-005, FR-010–FR-011).
- [x] [T002] Implement atomic encrypted identity/session persistence bound to the existing identity key in `atmem/identity/store.py`, including planted-secret raw-file scans and tamper/failure tests (FR-001, FR-017; SC-003).
- [x] [T003] Implement bootstrap, scrypt verification, login throttling, expiring/revision-bound sessions, logout, self password change and Administrator recovery in `atmem/identity/service.py` (FR-002–FR-004, FR-006, FR-009, FR-012–FR-013; SC-001, SC-004).

## Phase 2 — Administration and authorization

- [x] [T004] Implement Administrator-only list/create/enable/disable/role/scope/reset operations, one-time temporary passwords, session revocation and last-enabled-Administrator protection in `atmem/identity/service.py` (FR-005, FR-008–FR-013; SC-002, SC-004).
- [x] [T005] Add identity/application projections and convert authenticated local accounts to exact scoped `EvidencePrincipal` values in `atmem/service/application.py`, keeping host/API admin separate (FR-005, FR-007–FR-009).
- [x] [T006] Add cookie authentication, auth/user HTTP routes, forced-change restriction, CSRF checks and actionable error contracts in `atmem/control/web.py`; retain and mark legacy beta evidence bearer authentication in `tests/test_http_api.py` (FR-006–FR-009, FR-012, FR-016, FR-018; SC-002, SC-006).

## Phase 3 — Installation and CLI

- [x] [T007] Add idempotent `atmem init`, one-time fragment pre-fill with immediate browser-history scrubbing, foreground-dashboard bootstrap output, visible recovery guidance and daemon initialization refusal with one exact recovery command in `atmem/cli.py`, dashboard assets and `atmem/dashboard_daemon.py` (FR-003–FR-004, FR-019; SC-001).
- [x] [T008] Add safe hidden-input CLI commands for account list/create/enable/disable/role/reset/self-password/recovery without password command arguments, with installed CLI tests (FR-008–FR-009, FR-015).

## Phase 4 — Dashboard journey

- [x] [T009] Replace the evidence bearer-token box with a concise sign-in/forced-change/logout/account-status experience in `atmem/control/assets/app.html`, `app.js` and `app.css`, with no browser credential persistence (US2, US4; FR-006–FR-007, FR-014, FR-018).
- [x] [T010] Display the Viewer/Investigator/Evidence Collector/Administrator capability ladder and gate view/reconstruct/plaintext-export controls from the server projection in the run inspector (US5, FR-005, FR-014; SC-002, SC-005).
- [x] [T011] Add an Administrator-only compact Users panel for create, role/scope change, enable/disable and one-time reset credentials in the dashboard (US3, FR-008, FR-014; SC-004–SC-005).
- [x] [T012] Fix the Agent sessions composition so Memory search and Session archive remain full-width and only `blackboxWorkspace` enters master/detail mode, with static and responsive assertions (FR-014; SC-005).

## Phase 5 — Compatibility, consistency and acceptance

- [x] [T013] Amend Spec 028, integration ownership, onboarding and status documentation to define local Administrator supremacy without granting authority to a host/API admin or key custodian, and document legacy token migration (FR-005, FR-016).
- [x] [T014] Run the exhaustive four-role evidence/user-operation matrix, auth/session lifecycle, encrypted theft scan, dashboard 375px/1280px, existing evidence/HTTP/dashboard/CLI/OpenClaw regressions and installed-wheel gates; append exact evidence under `docs/implementation-evidence/029/` and leave unavailable claims explicit (SC-001–SC-006).
