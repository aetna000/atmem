# Spec 029 implementation evidence — 2026-09-13

## Implemented boundary

- Encrypted local account, session and security-audit documents bound to the AtMem
  identity key; raw-file planted-secret and tamper checks.
- One-time Administrator bootstrap, scrypt verifiers, bounded login throttling,
  idle/absolute session expiry, forced first password change, self change, logout
  and OS-owner recovery.
- Viewer, Investigator, Evidence Collector and Administrator authorization with
  server-side enforcement, exact scope conversion and last-Administrator safety.
- Cookie authentication, CSRF protection and Administrator create/list/role/
  enable/disable/reset operations; legacy evidence bearer credentials remain a
  separately labelled compatibility boundary.
- Idempotent `atmem init`, secret-fragment prefill with immediate history removal,
  non-echoing user CLI commands and simple lost-password recovery.
- Compact sign-in, role ladder, account password and Administrator Users UI. Only
  the run inspector enters master/detail mode; memory search and archive stay
  full-width.

## Focused verification

The final source suite completed with `1540 passed` and one upstream Pydantic AI
deprecation warning. The focused AtBot/framework/provider suite completed with
`42 passed`. Build, twine, sdist rebuild, clean-wheel installation, dependency
validation and all five published-version upgrade fixtures passed.

The role matrix verifies:

- Viewer cannot decrypt, reconstruct or export plaintext.
- Investigator decrypts/reconstructs but cannot plaintext-export or administer.
- Evidence Collector can export after exact confirmation but cannot manage users.
- Administrator includes evidence authority and exclusively manages local users,
  recovery and portable-home adoption.
- Host/API `admin`, submitter credentials and key custody do not create a local
  Administrator.

## Honest limits

This is deliberately local loopback identity, not SSO, passkeys, email recovery,
external directory sync or multi-node identity replication. Passwords are any
non-empty user-selected value by product choice; generated temporary credentials
remain high entropy. Responsive behavior has static regressions at narrow and wide
breakpoints; no measured two-cohort usability claim is made.

OpenClaw 2.3.0 built, typechecked, passed its hook/identity/tool/spool/task/delegated
tests, completed all smoke journeys and passed `npm pack --dry-run`. The live latest
host resolved to OpenClaw 2026.9.4; its reviewed hook-context fixture satisfies the
same fail-closed identity premises and is in the tested host registry.
