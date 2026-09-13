# Implementation Plan: Local User Management

**Date**: 2026-09-13
**Status**: Implemented and verified for AtMem 2.3.0
**Specification**: [spec.md](spec.md)

## Summary

Replace the dashboard's copied bearer credential with an encrypted local account
authority and server-side web sessions. Bootstrap one forced-change Administrator,
make the four roles visible, expose user lifecycle and self-password operations via
the application service/HTTP/CLI, and retain the legacy evidence-token verifier only
as a beta compatibility path.

## Technical context

- Python 3.10–3.13 and the standard library `hashlib.scrypt`, `secrets`, `hmac`,
  `unicodedata`, `http.cookies` and existing `cryptography`-backed sealed JSON.
- No new runtime dependency and no network requirement.
- Existing `EvidenceAccountStore` is encrypted with the identity key. It becomes a
  compatibility reader; the new `LocalIdentityStore` owns human accounts, sessions,
  throttling state and encrypted security audit objects.
- The dashboard remains loopback-only. HttpOnly SameSite cookies replace pasted
  tokens for human evidence routes; existing API bearer behavior remains additive.

## Constitution check

| Principle | Result | Implementation gate |
| --- | --- | --- |
| I Authority before intelligence | Pass | Identity never admits or ranks memory. |
| II Full-fidelity evidence | Pass | Authorized accounts reveal exact retained evidence rather than hashes. |
| III Safe defaults | Pass | Forced password change, expiring sessions, deny by default and last-admin guard. |
| IV Scoped transparency | Pass with explicit Spec 028 amendment | Local Administrator is a separately named account authority and ultimate evidence role; host/API admin remains unrelated. Authorization precedes decryption and all access is audited. |
| V Contract-first neutrality | Pass | Account/application contracts are host-neutral; no OpenClaw-specific identity. |
| VI Executable claims | Pass | Boundary and installed-artifact tests cover bootstrap, auth, role matrix and theft scan. |
| VII Local-first | Pass | Entire flow works offline with standard-library password verification. |

## Design

### Encrypted identity store

Add `atmem/identity/` with models and `LocalIdentityStore`. One encrypted JSON
container stores accounts and security audits; a second encrypted container stores
server-side sessions and throttle buckets. The storage wrappers expose only fixed
format and ciphertext metadata. Writes use mode 0600 temporary files, fsync and
atomic replace.

Accounts contain lowercase ASCII canonical/display username, optional Unicode display name, versioned
scrypt verifier, role, evidence scope, enabled state, revision,
`password_change_required`, timestamps and failed-login state. Sessions contain
only a digest of a 256-bit random token, account/revision binding, CSRF secret,
created/last-seen/idle/absolute expiry and revocation state. Privilege or password
revision changes invalidate prior sessions.

### Bootstrap and password lifecycle

`atmem init` initializes identity explicitly and prints a generated
`administrator` username plus one-time temporary password. Foreground
`atmem dashboard` invokes the same bootstrap and prints the credentials before
serving. Daemon management checks identity readiness and returns a precise init
command if missing. The bootstrap password is never persisted or recoverable.

`atmem users recover-administrator` verifies that the current OS user owns the
state, identity and key files with no group/other write bit, then requires the exact
text `RECOVER LOCAL ADMINISTRATOR`. It generates a new temporary password,
increments account revision and revokes all sessions. Normal CLI administration
prompts for Administrator username/password without echo; the dashboard uses its
authenticated session.

### HTTP and dashboard session boundary

Add `/api/auth/status`, `/api/auth/login`, `/api/auth/logout`,
`/api/auth/change-password`, `/api/users` and per-user state/role/reset endpoints.
Login sets `atmem_session` as HttpOnly, SameSite=Strict, Path=/ and Secure when the
request is HTTPS. State-changing session routes require the session's CSRF value.
Normal dashboard data remains readable at its existing compatibility level, but
exact evidence and user administration require a session. Temporary sessions may
call only status, logout and change-password.

The shell presents a sign-in gate when unauthenticated, a forced password-change
card when required, and an identity chip thereafter. The evidence drawer consumes
the signed-in account projection, displays effective role/scope, and shows
Reconstruct/Export only when allowed. Settings gains a compact Administrator-only
Users panel. No password/token is placed in browser storage.

### Role mapping

Extend `EvidenceRole` with `administrator`. Its evidence-operation set equals
Evidence Collector. User-management authorization is separate and accepts only
`administrator`; it is never inferred from API principal role, host identity or
key custody. The application converts a validated local session into the exact
EvidencePrincipal before calling the existing evidence service.

### Compatibility

Legacy test bearer tokens remain accepted by `/v1/evidence` during 2.3 beta and
return a deprecation marker. Existing encrypted evidence and account-token files
are not rewritten. Bootstrap creates a separate identity store. Spec 028's role
table is amended additively with Administrator and its conflicting generic-admin
sentence is narrowed to distinguish the local role.

## Files

- `atmem/identity/models.py`, `store.py`, `service.py`: identities, passwords,
  sessions, throttling, encrypted audit and authorization.
- `atmem/evidence/models.py`: explicit Administrator evidence operation mapping.
- `atmem/service/application.py`: account/session projections and user operations.
- `atmem/control/web.py`: cookie parsing, auth/CSRF gates and JSON routes.
- `atmem/cli.py`, `atmem/dashboard_daemon.py`: init, recovery and user commands.
- `atmem/control/assets/app.html`, `app.js`, `app.css`: sign-in, identity, password
  change, role actions and user management; fix the session detail split locally in
  `blackboxWorkspace`.
- `tests/test_local_identity.py`, `tests/test_http_api.py`,
  `tests/test_dashboard.py`, `tests/test_evidence_protection.py`: contract and UI.
- Spec 028, integration ownership, onboarding/release documentation: migration and
  authority consistency.

## Verification strategy

1. Deterministic-clock unit tests for bootstrap, normalization, password policy,
   password change/reset, last Administrator, session rotation/expiry/revocation,
   throttling and audit sanitization.
2. Raw-byte planted-secret scan of identity/session/audit stores.
3. HTTP cookie/CSRF tests and the complete role × evidence/admin operation matrix.
4. Dashboard static/CSP tests plus rendered 375px/1280px smoke where browser tooling
   is available; no pasted bearer UI and stable master/detail layout.
5. Existing evidence, dashboard, HTTP, CLI, OpenClaw and installed-wheel regression
   gates. Legacy token tests must remain green with deprecation asserted.

## Rollout and recovery

This is additive in 2.3 beta. Existing installs must run `atmem init`; evidence is
unchanged. Until initialization, exact dashboard evidence is unavailable with a
guided message, while agent recording continues. Recovery resets only the local
Administrator verifier/sessions and cannot decrypt, rewrite or discard evidence.

## Honest limitations

The initial profile is local single-instance username/password authentication, not
federated identity. Cookie `Secure` is unavailable over loopback HTTP, so loopback
binding, HttpOnly and SameSite are the development boundary. OS-account compromise
can invoke explicit recovery and is outside remote-login protection; the recovery
action remains audited inside encrypted AtMem state.
