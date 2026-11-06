# Verification record — 6 November 2026

Base: main `22d1d0f311b59958adad2ecfe1b831b13a9cdf69` (AtMem 2.3.12).
Branch: `feat/chatgpt-memory-plugin`; plugin development version 0.1.0.
This optional integration is not in the published PyPI 2.3.12 artifact.

## Real results

| Boundary | Result | Evidence / limit |
|---|---|---|
| Source cloud integration | 30 passed, 20.14 s | Real Firebase Auth/Firestore emulators, real HTTP MCP SDK client, real encrypted AtMem engine |
| Native memory/MCP/encryption regression | 50 passed, 1 skipped | Windows-only encryption test skipped on macOS; 2.85 s |
| Wheel and sdist | Built | Local feature build; not a package publication |
| Installed wheel MCP service | 30 passed, 21.14 s | Final wheel server imported outside checkout; actual HTTP MCP client |
| Browser consent | Passed | Real Chromium, keyboard approval, no-JS sign-in, mobile view; axe checks on two pages |
| Actual ChatGPT Pro 100 account | Not tested | No usable signed-in browser control; entitlement, invocation and confirmation behavior unverified |
| Natural-language review prompts | Prepared, not host-executed | Exactly 5 positive and 3 negative cases |
| Public directory / individual verification | Not performed | Requires owner's actual account and final review |

The cloud suite covers create, recall, details/provenance, scoped project creation,
account isolation, correction/versioning, exact deletion, audit verification,
missing/cancelled consent, wrong human/CSRF/host, stale/conflicting changes,
read-only grants, revocation, refresh rotation, code replay, resource binding,
expiry, idempotent retries, lost commit acknowledgement, unavailable service,
tampered ciphertext, proposal secrets/injection, immutable intent fingerprints,
Firebase project identity binding and absent ownership challenge. Stored data and
receipts are independently checked against AtMem and Firestore. Synthetic emulator
accounts/documents are removed and owned server processes stopped by the fixture.

Initial tests found and fixed public-client revocation schema incompatibility,
untrusted proposal screening and browser form Origin handling. Final tests preserve
permission checks; no write tool is misrepresented as a read.

Raw synthetic local evidence (not credentials or published user data):
`/private/tmp/atmem-chatgpt-evidence` and
`/private/tmp/atmem-chatgpt-installed-evidence`; JUnit/logs in the corresponding
`/private/tmp/atmem-chatgpt-*` files. Credentials and service keys are not evidence
artifacts and are never included in the ZIP or source repository.

## Approved Firebase pilot

Owner authorized existing atmemai Blaze. Billing already enabled; linked account
was not changed. New named native standard Firestore database `atmem-chatgpt`
(`us-central1`) has deletion protection, PITR disabled, provider version retention
3600 seconds and **no free-tier allocation**. Existing default nam5 database,
website Hosting, waitlist and rules are preserved. Runtime identity
`atmem-chatgpt@atmemai.iam.gserviceaccount.com` has database-conditioned datastore
access; a separate build identity has repository/source-bucket/log permissions.
Cloud Run/build/Artifact Registry/Secret Manager/IAM APIs were enabled. Firebase
Auth was initialized with password sign-in; only synthetic test accounts created.
The service independently enforces invited UIDs. Hosting is still a pilot, not a
plugin publication or an invitation to import real personal memories.

Managed results below are separately measured; emulator results do not certify
ChatGPT account invocation or public directory permissions. Numeric budget/alert response, operational
recovery drill, production performance and actual ChatGPT tests remain release
gates; min 0/max 1 is not a spending cap.

## Package boundary

The development ZIP is reproducible, read back and validated against pinned
AgentPlugins 1.0 transport schemas plus explicit OpenAI extension checks. The
versioned upstream MCP schema rejects extension properties despite current OpenAI
documentation requiring OAuth in extensions; validation therefore checks the
transport projection separately. Full unchanged upstream schema/portal acceptance
has not been claimed. `--public` refuses incomplete listing/policy/demo/identity/
account evidence. No credentials, guessed verification or fake policy URLs occur
in the package. ChatGPT account testing and public submission remain owner steps.

Registration refinement: real Auth emulator signup, required cloud acknowledgement,
verified-email gate, verification delivery/action, recovery emails, real OAuth
linkage and refresh passed. Disabling the registered Firebase user rejected the
next plugin refresh. Delivery to a real mailbox is not verified by emulator links.
Active access tokens have a ten-minute bound and browser approval sessions five
minutes; revoke the plugin grant for immediate grant invalidation.

## Managed HTTPS evidence

- Managed endpoint: https://atmem-chatgpt-nvwvv4d7sa-uc.a.run.app/mcp .
- Independent managed suite: **18 checks passed**; real Firebase Auth, OAuth
  PKCE, actual MCP SDK client and Firestore/native engine. See committed evidence
  in specs/049-chatgpt-memory-plugin/evidence/managed-checks.json. This is not
  ChatGPT-host invocation. Synthetic identities were administratively marked
  verified for backend testing, not presented as real mailbox-delivery evidence.
- Runtime IAM: a real impersonated runtime token returned 404 (authorized lookup
  of a missing synthetic document) in atmem-chatgpt and 403 in website (default).
  The temporary operator impersonation binding was removed after verification.
- Original managed lifecycle image: source 32386b48b55a3067a20cc051abbf338b762705dc,
  digest sha256:91cdacaa213057923aa769f822d13533018f8512857db8bf111502b9e0bbc57d.
- Health correction image: source b72e5442550936df94614217107bec61164202ff,
  digest sha256:fedf4560c1b661461a4eb3040157db6ac0a3f6f77f28f065c56374a8c42417aa.
  The sole runtime diff is /healthz -> /health. Build
  7f578be9-8a9c-4b45-ac82-2fa22f65ff48 succeeded in us-central1.
- Three small allowlisted image builds ran (including the pre-registration source
  build and its approved registration refinement). Each uploaded 391 source files,
  4.4 MiB before compression. No user state, native memories, history, credentials
  or benchmarks were uploaded. Build/artifact/Firestore charges may apply; no
  claim of zero cost or actual billing amount yet.
- Service: atmem-chatgpt, CPU 1, 512 MiB, concurrency 4, 60 s request timeout,
  CPU request throttling, min instances 0, max instances 1 (service and revision).
  Master key version 1 and config version 2 are pinned Secret Manager versions.
- Firestore control expiry TTL is ACTIVE. PITR disabled, provider database
  historical version retention 3600 s; Cloud Logging default retention 30 days.
  Native exact-record forgetting does not attest erasure from those histories or
  ChatGPT copies. A restore/rotation drill remains untested.
- Firebase registration enabled with email-enumeration privacy. Registered mode
  requires a verified email; the service does not accept a caller-supplied UID.
- Both synthetic households and chunks (including superseded test versions) were
  deleted after managed testing. Test OAuth grants revoked. Encrypted expiring
  auth controls are covered by TTL; account credentials remain only in an operator
  mode-0600 private file for synthetic reviewer preparation, never this repository.
- GitHub CI has not run: feature commits are local and have not been pushed. This
  record describes executed local, installed-artifact and managed tests only.

### Failures found during managed verification
Cloud Run intercepts /healthz with a frontend 404; changed to supported /health.
The initial independent inspection helper unnecessarily committed its local
inspection and hit a five-second cross-region SDK timeout; inspection now opens
an encrypted snapshot read-only. The first deletion assertion expected an empty
semantic search despite older synthetic facts in the same test account; corrected
it to verify the exact deleted ID is absent from both detail and recall. No native
retrieval behavior or deletion checks were weakened. Final cleanup removes all
synthetic household versions. One partial helper attempt was interrupted while
correcting an import; partial attempts are not counted as successful managed runs.

### Remaining public-release gates
Actual mailbox verification/reset delivery and recovery after expired linking;
owner's exact Pro 100 plan and tool discovery/invocation across new chats;
portal-provided OAuth client/callback, verified individual identity/org/project
rights and ownership challenge; approved plugin-specific policy/support URLs,
account-wide deletion procedure and retention/backup decisions; numeric budget
and monitored abuse/load/recovery limits; actual demo, synthetic reviewer access
and portal validation. No directory upload, submission, OpenAI approval or release
publication occurred. Development ZIP is not submission-ready.

Final image smoke: revision `atmem-chatgpt-00003-nh5` returned /health 200,
protected-resource metadata 200 and unauthenticated MCP 401. No memory mutations
in that smoke check. Separate live Firestore REST probes returned 403 for both
an anonymous request and a registered user's Firebase ID token: clients cannot
read the memory database directly. Evidence is committed alongside runtime IAM.
