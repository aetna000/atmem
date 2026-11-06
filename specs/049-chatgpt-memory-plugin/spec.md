# Cloud AtMem, accessed through a ChatGPT plugin

Owner-approved feature path: specs/049-chatgpt-memory-plugin (6 November 2026).
Base: public main 22d1d0f311b59958adad2ecfe1b831b13a9cdf69, AtMem 2.3.12.
The owner extended the goal to cloud-deployable AtMem with Firestore persistence.
ChatGPT is the first and only product UI; do not build a website dashboard.

## Outcomes
A user connects an account, searches only their chosen personal/project memory,
explicitly approves a proposed save/correction/deletion, and receives durable
AtMem records and verifiable receipts. A second account cannot see or change it.
An operator can deploy the service independently of the existing local product.

## Requirements
- FR-001: Inventory the current licence, memory/MCP/storage/auth contracts and
  current official OpenAI requirements with immutable source and dated references.
- FR-002: Use the actual AtMem engine for admission, search, corrections,
  supersession, provenance, deletion, screening and audit. Preserve local stdio,
  stores, default dependencies and unrelated work. No provider/model calls.
- FR-003: Expose authenticated Streamable HTTP MCP. Derive user identity from
  validated OAuth access tokens, bind tokens to the exact resource and enforce
  read/write/delete permissions on every operation. Never accept subject/tenant
  identity from tool arguments. Scope IDs must be authorized before storage access.
- FR-004: Isolate accounts and explicitly distinguish personal/project scopes.
  Return bounded requested-scope content and source/lifecycle details only.
- FR-005: Propose save/correct/delete operations with exact previews. Mutation
  requires an independent authenticated user approval outside model-controlled
  tool arguments. Bind approval to identity, scope, intent digest, expiry and
  expected record revision. Platform approval remains an additional host control.
- FR-006: Support stable IDs, idempotent retry, concurrent-update rejection,
  useful errors, activity/receipts and integrity checks. No false save/delete
  success on failed persistence. Retrieval is untrusted data, never instruction.
- FR-007: Make durable cloud persistence usable with Firestore while retaining
  AtMem authority semantics. No database on ephemeral Cloud Run disk may be the
  durable authority. Test crash/restart, optimistic concurrency and tenant isolation.
- FR-008: Encrypt retained memory and pending content; keep credential/key custody
  explicit, revoke access, expire drafts and prevent logging content or tokens.
  State precisely what is retained in audit, backups and superseded cloud copies.
- FR-009: Provide least-privilege scopes, bounded sizes/quotas, rate limits,
  health checks, TLS/host/origin checks, safe configuration and deployment/runbook.
- FR-010: Prepare portable manifests with MCP in the initial package, useful
  skill content, provided logo assets, exact review cases and reproducible archive
  validation. Never invent endpoint, verified publisher, policies or demo URLs.
- FR-011: Supply installation/uninstall, architecture/threat model, permission
  matrix, privacy/retention/deletion and consent-flow docs, support/terms drafts,
  reviewer fixture setup, evidence, changelog and owner release checklist.
- FR-012: Use real engine and real local Firebase emulators for integration;
  mocks supplement only. Test >=10 scenarios, clean/repeated setup, recovery and
  regressions. Account invocation evidence distinguishes discovery, invocation,
  permissions and backend failures. Unknown Pro 100 entitlements remain unknown.
- FR-013: Prepare Firebase/Cloud Run deployment with explicit egress and costs.
  Owner allows public hosting if needed, but provisioning/billing is gated by
  explicit cost approval. The owner subsequently approved the existing atmemai
  Blaze project for a lightweight isolated cloud pilot. Directory submission and
  publication remain gated; real memories remain untouched.
- FR-014: ChatGPT is the only product interface. Minimal secure OAuth sign-in,
  consent and per-operation approval pages are allowed; no separate app/dashboard.

## Acceptance
- SC-001: A real MCP client completes create/recall/detail/correct/delete and
  independently checks the persisted engine state and audit, using synthetic users.
- SC-002: Wrong user/scope, missing consent, stale version, revoked/expired token,
  wrong resource, secret/injection, duplicate retries and offline failures fail
  safely. A CAS loser cannot report a successful write. Deletion has exact receipts.
- SC-003: Restart preserves approved state; retention/cleanup has documented,
  tested boundaries. Cloud copies are encrypted and scanned for synthetic markers.
- SC-004: Package build is reproducible and validated. Public-readiness checks
  fail honestly for absent endpoint/policies/verification/demo/account evidence.
- SC-005: Local memory/MCP regression tests remain green with optional cloud
  dependencies absent from the base installation. Native user state is untouched.
- SC-006: Owner receives an evidence matrix, code/branch/commit, install commands,
  hosting choice and exact actions before cloud deployment and public submission.

## Boundaries
This is functional integration evidence, not a retrieval-quality benchmark.
Do not claim automatic invocation across chats, universal plan/mobile support,
OpenAI approval, zero cost, zero knowledge, complete forgetting from third-party
copies, AGPL licensing, or legal clearance. Current checked licence is Apache-2.0.
No new runtime frontend, native memory import, real-memory migration, public
reviewer credentials, paid model execution, or production identity creation.

## Approved hosting refinement (6 November 2026)
Use existing atmemai Blaze, with a separate Firestore database and database-bound
runtime IAM, Cloud Run min 0/max 1, synthetic invited accounts, and no website
dashboard. Preserve website Hosting, waitlist, security rules and native stores.
No directory submission/publication is authorized by hosting approval.

## Registration refinement (owner request, 6 November 2026)
FR-015: Provide Firebase registration/sign-in as the only user access gate, with
verified email before OAuth linkage, cloud data-flow acknowledgement, verification
resend/password recovery, per-address/peer email throttles, no credentials stored
in AtMem memory, and no user-selected tenant identity. Revalidate Firebase accounts
on OAuth refresh; document bounded active-token and browser-session lifetimes.
Retain invited policy for closed testing; registration alone grants no memory access.

## Public release completion (owner authorization, 6 November 2026)
The intended outcome is public directory availability, not an invitation-only
product. Technical preparation and existing-project deployment are authorized;
identity/legal attestations and actual account interaction cannot be invented.
- FR-016: Support fresh-authenticated, CSRF-protected account-wide deletion with
  a separate explicit preview/confirmation. Immediately fence every scope, grant,
  read, write and refresh; physically remove all household generations/chunks and
  indexed account controls. Concurrent or delayed work cannot resurrect content.
  Return an accurate resumable receipt, including Firebase account deletion state,
  legacy expiring auth records, retained non-content tombstone and external copies.
  No model-callable account deletion or caller-selected target UID.
- FR-017: Support ChatGPT's official CIMD public-client identity using bounded,
  HTTPS-only official metadata fetch/validation; never arbitrary URL fetching or
  wildcard callback allowlists. Advertise actual token authentication methods and
  authorization response issuer correctly. Preserve provided clients.
- FR-018: Demonstrate encrypted-snapshot recovery on isolated real AtMem storage,
  including native content/audit, wrong-key rejection and deletion-fence behavior.
  A recovery artifact cannot revive a deleted account. No real-user backup import.
- FR-019: Prepare cloud-specific product/support/privacy/terms website pages and a
  release package targeting the real HTTPS endpoint. Keep website changes in an
  owner-review PR and distinguish draft URLs from verified live pages.
- FR-020: Preserve truthful submission state: actual ChatGPT review cases/demo,
  verified publisher, country/commerce decisions, policy approval and portal scans
  remain unverified until performed. Hosting alone is not a directory release.
