# Verification record — 6 November 2026

Base: main `22d1d0f311b59958adad2ecfe1b831b13a9cdf69` (AtMem 2.3.12).
Branch: `feat/chatgpt-memory-plugin`; plugin development version 0.1.0.
This optional integration is not in the published PyPI 2.3.12 artifact.

## Real results

| Boundary | Result | Evidence / limit |
|---|---|---|
| Source cloud integration | 30 passed, 19.99 s | Real Firebase Auth/Firestore emulators, real HTTP MCP SDK client, real encrypted AtMem engine |
| Native memory/MCP/encryption regression | 50 passed, 1 skipped | Windows-only encryption test skipped on macOS; 2.85 s |
| Wheel and sdist | Built | Local feature build; not a package publication |
| Installed wheel MCP service | Registration update pending final wheel verification | Previous 29 passed; do not infer latest boundary until rerun |
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

Actual managed service URL, image/build receipt, IAM allowed/denied checks and
managed transport tests will be appended after deployment. Do not infer these
passed from the emulator results. Numeric budget/alert response, operational
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
