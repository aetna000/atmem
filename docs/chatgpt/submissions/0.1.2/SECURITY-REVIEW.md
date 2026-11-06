# Submission archive security review — 7 November 2026

Scope: exact submitted ZIP, extracted package, current plugin branch tree,
13 plugin commits since origin/main, and complete history reachable from the
plugin branch. Tool: Gitleaks 8.30.1 with default rules and redacted reporting.

- Submitted archive extraction: zero scanner findings.
- Plugin branch commits since main: zero scanner findings.
- Current repository tree: nine generic-key findings, manually inspected as
  synthetic test keys, deterministic sample signing bytes, idempotency keys,
  conversation identifiers or code expressions.
- Complete reachable history: 18 findings, manually inspected as those same
  fixture/code categories, synthetic approval secrets or a source-file checksum.
- No Firebase admin/service-account private keys or live access tokens were
  identified by these checks.
- Exact-value checks against the live cloud master key and stored reviewer
  password found no matches in tracked files, new archive files or plugin-branch
  patches. The values were read in memory and were not saved in the repository.
- The archive's ZIP and extracted files are identical; SHA256SUMS pins the bytes.
- Ignore rules now exclude common cloud credential and reviewer-password paths.

Reviewer credentials are in Secret Manager, not this archive. Live configuration
and the encryption key remain in their existing Secret Manager secrets. No
Firebase rules, IAM permissions, user data or production application code were
changed by this archival task. Ignore rules and scanners reduce risk; they are
not a guarantee that every possible secret can be detected. This is not a full
Firebase IAM/rules/security audit or a user-data backup verification.
