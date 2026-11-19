# Cloud plugin verification — current status, 6 November 2026

The cloud backend is deployed and a private personal test plugin exists. The
intended release is public. **No public directory submission, approval or
publication has occurred.** Actual ChatGPT tool invocation and real mailbox
verification are not certified by backend tests.

## Source and deployed artifact

- Base: main 22d1d0f311b59958adad2ecfe1b831b13a9cdf69 (AtMem 2.3.12).
- Branch: feat/chatgpt-memory-plugin; public source PR:
  https://github.com/aetna000/atmem/pull/33 (draft pending release gates).
- Runtime source: 9c1d108fe2ad4bf939bdcf7e22f53521c1ccf84c.
- Image: sha256:b084a047ec8146c96ab9282b7293ad221be7223e0b5118dad18959a68403a908.
- Cloud Build: acfb51f6-8b35-4e96-8aaa-69e413f0848e, SUCCESS.
- Cloud Run revision: atmem-chatgpt-00004-cll, 100% traffic.
- MCP: https://atmem-chatgpt-nvwvv4d7sa-uc.a.run.app/mcp .
- Native published version remains 2.3.12. This optional cloud feature is a source
  build, not an assertion that the existing PyPI wheel contains these changes.
  Plugin package version: 0.1.0. Source licence: Apache-2.0.

## Measured results

| Boundary | Result | Evidence and limits |
|---|---|---|
| Final installed-wheel integration | 38 passed, 25.48 s | Real Auth/Firestore emulators, HTTP MCP client, native encrypted engine; server imported outside source checkout |
| Native memory/MCP/encryption regression | 50 passed, 1 skipped, 3.56 s | Windows-specific encryption case skipped on macOS |
| Final managed cloud additions | 10 checks passed | Real HTTPS CIMD, encrypted recovery, approval, account/Firebase deletion and independent cleanup verification |
| Website local validation | Passed; 55 browser tests | Build, existing gates/docs, new policy routes, axe and mobile overflow |
| Website PR CI | SUCCESS | PR #34 at 633bd1f9f98573f865b03b93c3d198609df1a9ae; workflow 42157350040 |
| Private account package save | Accepted; USER / PRIVATE | Real Plugin Creator creation and metadata readback; IDs retained privately |
| Actual ChatGPT read/write invocation | Not run | Tools are not exposed in this current task; not classified as a permission rejection |
| Actual Pro 100 plan entitlement | Unverified | Private account package creation does not establish subscription/write/publication permissions |
| Real mailbox verification/reset delivery | Not run | Synthetic identities were admin-verified for backend testing |
| Public portal scan/review | Not run | Private package acceptance is a different boundary |

Installed cases cover create/recall/provenance, approval/cancellation, scopes,
account isolation, correction/versioning, exact deletion, audit, stale/conflicting
changes, read-only grants, expiry/revocation, refresh/code replay, resource binding,
idempotent retries, lost acknowledgements, offline/restart, tampered ciphertext,
injection/secret screening, immutable intents, Firebase project identity, verified
registration/recovery, account-wide deletion and partial retry, deletion fencing
between staging/swap, legacy unindexed token denial, real native recovery with
wrong key/account/generation rejection, official CIMD/PKCE/issuer and persistent
per-account quotas across repository restart. No native store or real personal
memory was imported or modified. Synthetic emulator data/processes were cleaned.

Final managed checks created one new synthetic Firebase account, completed OAuth
using official ChatGPT client metadata, saved an approved synthetic memory,
exported/restored its encrypted snapshot with native audit verification, confirmed
whole-account deletion with fresh sign-in, observed immediate old-token rejection,
verified zero remaining household chunks, rejected restore after deletion,
independently confirmed Firebase account absence and recovered the browser
receipt. Its private test credentials and local inspection directory were removed.
This is independent protocol execution, not a conversation in ChatGPT.

An earlier 18-check managed lifecycle suite passed on the prior registration
image. It remains separately labelled in evidence/managed-checks.json; it is not
presented as an additional final-image or ChatGPT-host benchmark. Synthetic
checks establish wiring/security behavior, not retrieval quality or production
scale/latency. Raw local traces remain outside the plugin ZIP.

## Production boundaries verified

Existing atmemai Blaze was owner-approved. Billing account was not changed.
The new standard native database atmem-chatgpt in us-central1 is separate from
the website's default nam5 database. It has no free-tier allocation, deletion
protection, PITR disabled and 3,600-second provider version history; no scheduled
backup exists. Control expiry TTL is ACTIVE. Default Cloud Logging retention is
30 days. Neither memory nor account deletion attests removal from those histories
or copies held by ChatGPT.

The runtime identity has database-conditioned datastore access. Real impersonated
API probes returned 404 for an authorized missing document in atmem-chatgpt and
403 in the website default database. The temporary impersonation binding was
removed. Anonymous and registered Firebase users both received 403 for direct
Firestore memory access. Unauthenticated MCP calls receive 401. Existing website
Hosting, waitlist, security rules and native stores are unchanged.

Keys are operator-held: Secret Manager master version 1 and config version 2,
with a protected operator recovery copy. SQLCipher plus AES-256-GCM are not E2EE,
zero knowledge, a FIPS certification or a new post-quantum/Black Box capture
claim. Privileged operators with keys can decrypt service state.

Limits: 8 MiB packed snapshot, 1,000 active records/scope, 30 tools/account/minute,
120 HTTP requests/observed peer/minute and 5 account-email requests/peer/minute,
with a two-minute address delivery throttle. Account counters survive restart.
Cloud Run has min 0/max 1, CPU 1, 512 MiB, concurrency 4, timeout 60 s and request
CPU throttling. These are controls, not a spending cap or production load result.
Console incident policy 13781382782955428729 is enabled for repeated HTTP 5xx;
no notification channel is attached. Owner must choose notification and budget.

Account deletion is browser-only with fresh password, account-labelled preview
and explicit confirmation. Fenced transactional staging/swap prevents recreation
by concurrent/late work. All household versions/chunks and indexed controls are
purged, then Firebase deletion is reported separately. Failure leaves access
blocked and the same deletion can be renewed with fresh credentials. An
indefinite non-content fence/encrypted structural receipt prevents resurrection.
A five-minute encrypted deletion proof permits lost-response receipt recovery;
legacy unindexed auth controls expire/TTL under their prior <=24h bound, with
access denied by the fence. Never roll back to pre-fence code or replace these
markers with an old backup. Automatic key rotation is not implemented.

## Package and website status

Source package: plugins/atmem-chatgpt (local loopback development).
Cloud candidate override: deploy/chatgpt/cloud-package-metadata.json, actual
HTTPS endpoint and official CIMD; no static credentials. The four listing URLs
are planned routes in private website PR #34. Live probes currently return 404;
they are not called published policies. Owner-only merge and validated-main
Hosting deployment remain required. Local and GitHub website CI passed.

Private account package uses the real cloud endpoint and excludes those unmerged
listing URLs. Package creation succeeded once after a definitive validation error
was corrected: release_notes belongs under publication, not review. It was not
an approval rejection or a public submission. No app account has been connected
or real user memory written in ChatGPT by that save.

Packaging is deterministic, archive-readback checked, with 5 positive/3 negative
review cases and 7 reference guides. Versioned upstream Agent Plugins transport
schema lacks the OpenAI extensions documented by OpenAI; local validation checks
its strict transport projection plus explicit extensions. Private host validation
accepted the corrected package. Full public portal acceptance remains unverified.
Public archive generation refuses missing publisher/demo/verification evidence.

## Remaining public release gates

1. Owner connects the saved test plugin, registers/verifies a real mailbox and
   executes read/save/new-chat recall/correct/forget plus negative cases. Record
   tool discovery, calls, platform approvals/errors and exact account surface.
2. Record and verify the real ChatGPT demo; retain a synthetic reviewer account
   with no owner data and no reviewer dependency on an inaccessible mailbox/MFA.
3. Complete verified individual publisher identity, organization/project access,
   supported countries, commerce/policy attestations and ownership challenge.
4. Owner reviews/merges website PR #34; deploy only the validated main artifact,
   then verify the four public URLs before public package metadata is finalized.
5. Choose a numeric billing budget/notification destination and finish any
   required public operational qualification without advertising unmeasured scale.
6. Run portal package/tool scans, submit the selected version within authorization,
   respond to review, and publish only after approval. These are separate states.

Source CI: push checks were superseded/cancelled when PR checks started. The
current PR run had no failures at last inspection, with some platform jobs still
running. No source merge or published native/package tag has been performed.

## 19 November 2026: account access repair

The deployed source previously required a live OAuth nonce even to register or
recover access. Direct account links returned a dead end. Independent account
pages now address this, while expired/forged OAuth requests still fail closed.
Login errors link to recovery; opening another account page no longer rotates
CSRF unexpectedly. Explicit credentials are validated even with a browser session.

Local real Firebase Auth/Firestore emulator suite: **43 passed**, no skips,
including standalone signup/consent, unverified-user rejection, verification
resend/consumption, password reset and old-password rejection, browser sign-out,
CSRF/Origin checks, stale linking and existing OAuth/MCP/deletion/isolation tests.
Playwright exercised mobile and desktop account navigation/login/retry/logout
with JavaScript disabled, plus the existing consent and native callback tests.
Native regressions: **50 passed, 1 platform-specific skip**.

Live preflight: actual ChatGPT authorization requests returned HTTP 302, dedicated
reviewer Firebase credential sign-in returned 200, and all four public cloud
policy/support routes returned 200. This does not prove delivery to a real
mailbox or completion inside the owner's ChatGPT session. Deployment and live
post-update results are recorded separately below when complete.

### Deployed repair and live evidence

- Source commit: `0220516041b998d04657a52eec3f5f02f5ae50e4`; repair
  [PR #40](https://github.com/aetna000/atmem/pull/40) targets the existing hosted
  feature branch. Documentation follow-up commits do not change this image.
- Cloud Build: `431413d9-1c50-4069-b06f-9a682d37a1b5`, SUCCESS. Remote context
  contained only committed runtime files, Dockerfile and required license/build
  metadata (394 files, 4.5 MiB); no working-tree state or credentials.
- Image: `us-central1-docker.pkg.dev/atmemai/atmem-chatgpt/mcp@sha256:ca404e07086ba4fba05d47177091ca07ef1e9aa9dd3c57a486ec1e0d533445f3`.
- Cloud Run: `atmem-chatgpt-00010-b7s`, 100% traffic. Existing service, named
  database, config secret version 3, master-key secret version 1, max instance 1,
  512 MiB and existing IAM retained. Previous compatible revision
  `atmem-chatgpt-00009-zb5` remains available for rollback. No schema/key migration.
- Canonical account entry: https://atmem-chatgpt-nvwvv4d7sa-uc.a.run.app/login .
  The existing plugin 0.1.2 continues to use the same `/mcp` endpoint; no native
  package release or plugin ZIP replacement was needed for this service repair.
- Live synthetic checks passed: all four account forms, verified reviewer login,
  browser logout, OAuth discovery, official Codex CIMD + PKCE authorization/token
  exchange, authenticated MCP `list_memory_scopes`, revocation and subsequent
  token rejection. Test grants were revoked; no memory content was written.
- Live Playwright: mobile and desktop create-account/recovery navigation, rejected
  password with usable retry, correct login and logout, with JavaScript disabled.
- Existing synthetic account signup probe returned Firebase `EMAIL_EXISTS`; it
  created no identity and sent no mail. This is not new-mailbox delivery evidence.
- Hosted [CI run 44520557887](https://github.com/aetna000/atmem/actions/runs/44520557887)
  passed. Broad repository CI is separate and was not all green at verification
  time (including failed OpenClaw jobs); this repair does not claim full branch
  merge readiness.

The full new-user verification/reset lifecycle was exercised against real local
Firebase emulators. Actual email receipt by the owner's mailbox and reconnect
inside the owner's ChatGPT session remain unverified; neither is replaced by
the synthetic live/browser checks. No owner password, OAuth token, email action
code or encryption key is included in these receipts.
