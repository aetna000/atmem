# Feature Specification: Local User Management

**Feature directory**: `specs/029-local-user-management`
**Created**: 2026-09-13
**Status**: Implemented and verified for AtMem 2.3.0
**Input**: Replace one-time bearer-token UX with local Administrator bootstrap,
username/password sign-in, user administration, self-service password changes,
and visible evidence roles.

## Overview

AtMem is an independent evidence authority and needs its own usable identity
boundary. A fresh local installation must establish one Administrator, show the
generated bootstrap username and password exactly once, and require sign-in before
exact evidence can be decrypted. The Administrator can create, disable and reset
other local users. People sign in with usernames and passwords and receive only the
operations assigned to their account.

Python package installation cannot safely execute instance initialization or print
an instance secret: `pip install` installs code and may target a shared environment.
Therefore the first `atmem init` or first interactive `atmem dashboard` start after
installation performs bootstrap and prints the credentials once to the controlling
terminal. Install and onboarding copy must make that one required step explicit.

This feature preserves Spec 028 encryption and authorization-before-decryption. It
replaces development bearer-token accounts as the normal human experience. Opaque,
short-lived HTTP sessions remain bearer credentials internally; users never need to
copy them. Existing test tokens remain accepted during the beta migration only and
are visibly labelled legacy development credentials.

## Roles and authority

Roles are explicit and scope-bound. A higher evidence role includes the lower
evidence operations for the same scope. Administrator is the local installation
owner and account authority; it has ultimate local evidence access and all Evidence
Collector operations.

| Role | Human outcome | Permitted operations |
| --- | --- | --- |
| Viewer | Inspect content-free evidence status | Metadata, hashes, timing, integrity, coverage and outcomes only; no decryption or exact-content search |
| Investigator | Decrypt, audit and reconstruct what happened | Viewer operations plus exact in-app text/media access, exact-content search, reconstruction, inert replay manifest and recipient-encrypted export |
| Evidence Collector | Collect/control evidence | Investigator operations plus confirmed plaintext export, evidence retention/deletion and evidence key controls |
| Administrator | Own this AtMem installation | Evidence Collector operations plus create/list/disable/enable users, assign scope/role, reset another user's password and inspect account-security audit |

Administrator authority is explicit local product policy and supersedes Spec 028
FR-008's sentence that generic administrator status does not imply evidence
privilege. Only the bootstrap/local `administrator` role defined here gains that
authority; an agent/API `admin` header, host owner, OS account or key custodian does
not.

## User scenarios and acceptance

### US1 — Bootstrap a fresh installation (P1)

After installing AtMem, the owner runs `atmem init` or starts the dashboard. AtMem
creates exactly one Administrator and prints a generated username, generated strong
temporary password, dashboard URL and forced-password-change instruction once.

**Acceptance**: Credentials are written only as a salted password verifier inside
the encrypted identity store, never logged or stored in plaintext. Re-running init
does not disclose or replace them. The first successful login must change the
temporary password before evidence or administration is accessible. Interactive
initialization starts the loopback dashboard and pre-fills the one-time credential;
the browser removes that handoff immediately after reading it.

### US2 — Sign in and see effective access (P1)

A user signs in on one concise screen and sees their username, role, exact scope and
allowed actions. They never paste a bearer token.

**Acceptance**: Authentication creates an opaque, random, idle- and absolute-
expiring local session in a Secure-capable, HttpOnly, SameSite=Strict cookie. The
dashboard renders only server-authorized actions. Logout and account disable revoke
the session immediately. Authorization remains enforced on the server.

### US3 — Administrator manages users (P1)

The Administrator opens Users, creates a Viewer, Investigator or Evidence Collector
with explicit scope, and receives that account's temporary password exactly once.
The Administrator can disable/enable the account, change role/scope, and issue a
one-time password reset.

**Acceptance**: Duplicate/case-confusable usernames fail; the final enabled
Administrator cannot be disabled or demoted; users cannot create or elevate users;
every success and denial is append-only audited without passwords or session tokens.

### US4 — User changes their password (P1)

Any signed-in user changes their own password by supplying the current password.
Temporary/reset passwords force this flow, but the restricted session does not ask
for the just-entered temporary credential a second time.

**Acceptance**: Password policy is explained inline. A successful change revokes
all other sessions, rotates the current session, records an audit event, and never
returns the password. Incorrect current passwords are rate-limited and do not reveal
whether another username exists.

### US5 — Roles control evidence actions (P1)

The same run is opened by all four roles.

**Acceptance**: Viewer sees only content-free metadata and hashes; Investigator can additionally decrypt exact evidence and sees audit
reconstruction; Evidence Collector additionally exports plaintext after explicit
confirmation; Administrator can do all of those and manage users. Hidden buttons
and direct HTTP attempts produce the same deny-by-default result.

## Functional requirements

- **FR-001**: Persist local accounts only inside a versioned encrypted identity
  store. Store normalized username, display name, password verifier parameters,
  role, exact scope, state, revision, password-change flag and timestamps. Never
  store plaintext passwords, recovery answers or session credentials.
- **FR-002**: Hash passwords with `scrypt` using a unique 128-bit-or-larger salt,
  constant-time comparison and versioned work parameters supported by Python
  3.10–3.13. Password verification and upgrade MUST fail closed.
- **FR-003**: Bootstrap exactly one `administrator` when no account store exists.
  Generate at least 192 bits of password entropy; show it once from `atmem init` or
  first foreground dashboard start; mark it temporary. Interactive `atmem init`
  MUST start/open the loopback dashboard by default and pre-fill the sign-in form.
  Non-interactive daemon start without initialized identity MUST fail with the exact
  initialization command.
- **FR-004**: Repeated initialization MUST be idempotent and MUST NOT show, reset or
  replace an existing credential. Lost Administrator access uses
  `atmem users recover-administrator`: the current OS user MUST own the state,
  identity and key files; group/other write permission MUST be absent; and the user
  MUST answer one plain `y/N` confirmation. Recovery revokes every session, opens
  the loopback dashboard with the new temporary credential pre-filled, and is
  audited; it never recovers an old password.
- **FR-005**: Implement the four roles in the table. Administrator is the only user-
  management role and includes scoped Evidence Collector authority. Host/API admin,
  evidence submitter and key custodian do not become Administrator.
- **FR-006**: Authenticate username/password through AtMem and issue opaque random
  server-side sessions with 30-minute idle and 12-hour absolute expiry by default.
  Cookies MUST be HttpOnly, SameSite=Strict and Path=/; use Secure on HTTPS. Rotate
  on login, password change and privilege change. The sole URL exception is the
  newly generated temporary password in a loopback dashboard fragment during the
  same interactive bootstrap: fragments are not sent by HTTP, the UI MUST consume
  it before routing and immediately replace browser history with a secret-free URL.
  Never place credentials in query/path components, localStorage, sessionStorage,
  HTML, application logs or audit payloads.
- **FR-007**: Require authenticated sessions for exact evidence and user-management
  dashboard/API routes. CSRF protection is required on every state-changing cookie-
  authenticated request. Machine bearer credentials remain a separate API concern.
- **FR-008**: Administrator can list, create, disable, enable, change role/scope and
  reset local users. Generated temporary passwords are returned once. The last
  enabled Administrator cannot be disabled, deleted or demoted.
- **FR-009**: Every user can change their own password only after current-password
  verification. A temporary-password session has already verified that credential
  and is restricted to password change and logout, so its forced-change form asks
  only for the new password and confirmation. Changing/resetting a password revokes
  applicable sessions.
- **FR-010**: Usernames are 3–64 ASCII characters, normalized to lowercase, begin
  with an ASCII letter or digit, and thereafter contain only letters, digits, `.`,
  `_` or `-`. Comparison uses the normalized form. Display names are separate
  non-authority Unicode text. This deliberately avoids Unicode-confusable account
  identifiers in the local beta.
- **FR-011**: Human-selected passwords have no length, composition, username or
  denylist policy beyond being non-empty. The UI may offer advice but MUST NOT block
  a chosen non-empty password. Generated temporary passwords remain high entropy.
- **FR-012**: Apply bounded authentication throttling per canonical username and
  source address without disclosing account existence. Clear successful principal
  state after login; record threshold/lockout security events without the attempted
  password.
- **FR-013**: Append encrypted account-security audit events for bootstrap, login
  success/failure threshold, logout, password change/reset, session revocation,
  user creation, role/scope/state change and denied administration. Record actor,
  target, operation, time and result; exclude passwords, hashes, cookies and tokens.
- **FR-014**: Add a compact dashboard sign-in gate and a Users section. After login,
  always show effective username/role/scope. Show Viewer, Investigator, Evidence
  Collector and Administrator capabilities plainly. Render only allowed actions,
  while keeping server checks authoritative.
- **FR-015**: Provide CLI equivalents for init, login-independent local owner
  recovery, user list/create/disable/enable/role/reset-password and self password
  change. Except for OS-owner recovery, each administrative CLI invocation prompts
  for the Administrator username and password using a non-echoing terminal prompt;
  self change prompts for username, current password and new password. Passwords
  and session credentials MUST NOT be accepted as command arguments or environment
  variables. Generated temporary passwords appear once on stdout.
- **FR-016**: Migrate existing encrypted evidence test accounts without decrypting
  evidence. During 2.3 beta, legacy bearer tokens may continue on `/v1/evidence`
  with a deprecation marker; the dashboard no longer asks normal users for them.
  Migration cannot invent passwords; Administrator creates replacement users.
- **FR-017**: All account, session and audit storage is encrypted at rest and bound
  to the AtMem identity key. Stolen files reveal no usernames, roles, scopes,
  password-verifier metadata, session identity or security-event metadata.
- **FR-018**: Authentication errors use actionable product copy: sign-in required,
  session expired, password change required, insufficient role, or account disabled.
  The UI MUST NOT expose raw “valid local bearer credential required” errors to a
  normal dashboard user.
- **FR-019**: The sign-in screen MUST name
  `atmem users recover-administrator` as the lost-bootstrap-password path. Recovery
  creates a new temporary password after local ownership and one simple `y/N`
  confirmation, then opens the local sign-in form with it pre-filled. No UI or CLI
  may recover or redisclose the old password.

## Success criteria

- **SC-001**: Fresh-install acceptance creates one Administrator, shows its generated
  credentials once, forces password change, and shows no credential on rerun.
- **SC-002**: Exhaustive API/UI tests cover every role × evidence operation × user
  administration operation, including direct-route attempts, with zero privilege
  escalation or scope widening.
- **SC-003**: Raw scans of account/session/audit files recover none of ten planted
  usernames, display names, roles, scopes, passwords, session tokens or events.
- **SC-004**: Login, logout, forced change, self change, admin reset, disable, role
  change, session idle/absolute expiry and last-Administrator protection pass with
  deterministic clocks.
- **SC-005**: At 375px and 1280px, sign-in, role display, exact evidence view,
  investigator reconstruction, collector export and administrator user creation
  complete without horizontal overflow or unexplained bearer-token input.
- **SC-006**: Existing evidence ciphertext and hashes remain byte-identical through
  account migration; legacy bearer tests pass with explicit beta deprecation.

## Out of scope

Federated SSO/OIDC/SAML, WebAuthn/passkeys, email recovery, multi-node account
replication, external directory synchronization and production KMS identity policy.
Those may extend this local authority without weakening its server-side role/scope
checks.

## Invariant attestation

Touches INV-006 human-readable provenance/history, INV-008 honest Agent Black Box
boundaries and INV-010 local operation. Required assertions cover authenticated
exact evidence, role denials, encrypted identity storage and local bootstrap with no
network dependency.
