# Implementation plan

## Decisions
1. Add optional `atmem.chatgpt` cloud service and extra, using MCP Python SDK
   1.30.0 (OAuth authorization-code/PKCE parsing and Streamable HTTP) and real
   AtMem 2.3.12 memory engine. Existing stdio is unchanged.
2. First Firestore persistence is an explicitly bounded encrypted snapshot
   repository, not a claim that SQL queries were translated to Firestore. Each
   account owns one AtMem household with scoped subjects. Firestore atomically
   switches a generation pointer to immutable encrypted snapshot chunks. Load
   a bounded snapshot into an isolated temporary working household, run actual
   AtMem transactions, checkpoint/close, encrypt and CAS the next snapshot.
   A failed CAS discards the operation and cannot report success. This retains
   engine lifecycle and audits without creating a competing memory authority.
   Quotas/costs are proportional to snapshot size; native indexed Firestore
   queries and high-scale multi-tenant performance are explicitly not claimed.
3. Keep cloud account OAuth/control metadata separate from canonical memories.
   Firebase Auth authenticates real users; the MCP OAuth adapter issues opaque,
   resource-bound, revocable short-lived grants. Provided PKCE OAuth clients
   require exact operator-configured callback allowlists. No open DCR/CIMD claim.
4. Read/write/delete grant scopes constrain MCP access. Personal/project scope
   membership is enforced server-side using authenticated account IDs, never
   model-provided identity. Browser approval requires Firebase sign-in and a
   CSRF-bound identity session; the model cannot approve its own pending intent.
5. Persist pending actions inside the same encrypted AtMem household; intent
   fingerprints/record versions and consumption are atomic with memory commits.
   Bounded retained receipts omit memory text; expired/rejected/deleted intent
   content is purged. Use existing screening and exact-record deletion receipts.
6. Configure a dedicated explicit service home and encryption secret. Never
   fall back to ~/.atmem, global stores, plaintext or unsigned emulator auth in
   production. Cloud Run settings must require a durable Firestore repository.
   Keep temporary files encrypted and isolated; keys held by operator, not E2EE.
7. MCP results have typed bounded output, clear untrusted-data flags and error
   codes, accurate annotations and permission scopes. Add no extra MCP UI app.
8. Package a local development bundle with a real loopback endpoint and initial
   MCP configuration. A separate public package renderer requires a verified
   HTTPS endpoint and complete public metadata. Refuse placeholder public ZIPs.
   An unsigned public template is documentation, not a submission-ready upload.
9. Real local Firebase Auth/Firestore emulators and real MCP sessions exercise
   the full lifecycle and OAuth boundary; add unit/invariant tests and existing
   memory/MCP regressions. Record all platform-only tests as not run until a
   real authorized connection/account is available. No tunnel/account upload now.
10. Provide deployment files and lowest-cost safe options, policy/terms drafts,
    user/reviewer flow and package/review checklist. Owner subsequently authorized the existing atmemai Blaze pilot; use a
    separate database and restricted runtime identity. No billing-account change,
    directory upload, submission or public plugin publication.

## Architecture
ChatGPT -> OAuth-protected MCP -> authorized scoped service -> AtMem engine
-> encrypted Firestore snapshot repository (generation CAS).
User browser -> Firebase Auth + OAuth/operation consent -> same scoped service.
There is no website application or second memory engine. Data sent to ChatGPT
leaves the host; remotely persisted memory is cloud-hosted, not local-only.

## Engineering
Optional dependencies only. New modules under atmem/chatgpt; tests/chatgpt;
plugins/atmem-chatgpt and scripts/package_chatgpt_plugin.py; docs/chatgpt;
deploy/chatgpt. No core schema change: namespaced adapter/control tables live
in the engine household and have independent schema versioning. Source licence
and notices follow current Apache-2.0 files, without legal-clearance claims.

Owner registration refinement: implement verified Firebase email registration within
OAuth linking, recovery and email throttles. Recheck Firebase account on token
refresh, keep invited mode for synthetic/closed testing, document expiry windows.

## Public completion design
Account deletion is a browser-only control, not a memory tool. Fresh Firebase
password authentication produces a five-minute encrypted deletion proof. The
user sees all-account scope and confirms the exact operation. A transaction sets
an irreversible account fence; every household load/stage/swap and account-bound
control read/write validates it. Chunk staging becomes a guarded transaction
(maximum packed snapshot 8 MiB, below Firestore's request limit). Purge follows
fencing, including orphan chunks, then delete Firebase with the fresh user token.
A retained HMAC-addressed tombstone stores an encrypted structural receipt and
prevents old tokens, delayed requests or recovery from resurrecting the account.
Deletion is resumable by the same short-lived confirmed proof; backend failure
never unblocks the account or claims Firebase deletion. Legacy auth controls not
indexed by account expire under existing <=24h token TTLs and are denied by fence.

CIMD: fetch only https://chatgpt.com/oauth/client.json or official callback-ID
client documents, no redirects, 32 KiB cap, short bounded cache. Validate client
identity, HTTPS chatgpt.com redirects, supported public-client method and exact
redirects from the document. Publish supported method none and response iss,
copy the issuer into redirects. No DCR or arbitrary metadata URL support.

Recovery: encrypted export/restore methods enforce account binding, quotas,
expected generation, format and account fence. Tests load restored data with the
actual Memory engine and verify contents/audit; wrong key and deleted accounts
fail. No automatic backup scheduler or unreviewed retention promise.

Website pages contain confirmed implementation facts and clearly label launch
status. Product is ChatGPT access only; no account dashboard is introduced.
Authoritative policies and legal decisions still require owner review. Existing
website data/rules/branding remain intact. Public metadata uses only verified
live URLs; a candidate archive with remaining gaps is never submission-ready.
