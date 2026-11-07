# Cloud AtMem privacy disclosure — DRAFT, not a published policy

This describes the implemented data flow. The operator must confirm publisher,
support, hosting region, actual provider configuration, retention/backup/log
choices, supported countries and applicable obligations before publishing it.
It is not legal advice or a legal-clearance/compliance statement.

The ChatGPT plugin reads only the requested personal or owned-project memory.
It does not silently capture all conversations. A save/correction/deletion is
proposed explicitly, previewed through a signed-in approval page and committed
only after approval. Returned memory is sent to ChatGPT and governed by its own
handling. A remote store is cloud-hosted; it is not local-only.

The service processes account identity, requested scopes, focused search text,
explicitly proposed memory, record/source lifecycle information, approvals and
receipts. Firebase Auth processes sign-in credentials; this application does not
retain passwords. OAuth credentials are hashed for lookup and encrypted at rest.
The service does not require an AI provider or transmit memory to an embedder.

Firestore retains encrypted AtMem household snapshots, including native facts,
episodes/source text, graph/FTS, audit metadata and pending approvals. Operator
holds keys and can decrypt authorized service data; this is not end-to-end
or zero-knowledge storage. Access is restricted by identity, scope, service IAM
and application checks. Reviewers receive separate synthetic accounts and cannot
access the owner's or other users' memory.

Memories remain until explicitly forgotten. Corrections preserve prior native
versions. An exact-record receipt names what was purged and does not imply whole
lineage erasure. Pending content is removed on completion/cancellation; expired
bodies are purged on the next successful account operation. Encrypted expired
auth/control records rely on configured TTL/maintenance for physical removal.
Obsolete generations are cleaned after commit; interrupted cleanup is separate.

Cloud provider backups/PITR, managed platform logs and ChatGPT copies have
separate retention; the current database PITR is disabled with a 3,600-second historical version
window, and default Cloud Logging retention is verified at 30 days. No scheduled
Firestore backup is configured for this database.
Do not promise complete erasure from these systems. Uninstalling/disconnecting
revokes access but is not a memory deletion. Deleting a key prevents recovery and
is not a substitute for a verified native forget receipt.

Contact/support and data-access/deletion handling: use the owner's approved
published support page once available. The existing website privacy page mainly
covers that website; it has not been silently reused as this cloud policy.
No sale/sharing, lawful-basis, age, residency or response-time promise is made
without the operator supplying and reviewing the actual policy.

Registration uses Firebase account email/password and email verification. Passwords
are forwarded to Firebase over TLS, not stored by AtMem. Firebase refresh tokens
used for account revalidation are encrypted in the auth-control store, separately
from memory. Delivery throttles hold opaque HMAC address identifiers and expiry,
not plaintext email. Firebase necessarily retains account identity until account
deletion; deleting a memory does not delete the Firebase account. Account deletion
handling and actual email-delivery policy must be verified before general launch.

Account-wide deletion now has a fresh-authenticated preview/confirmation route.
It fences access before purging all household data and indexed controls, then
separately verifies Firebase deletion. Partial failure is blocked and retryable,
not reported as complete. The non-content deletion fence/structural receipt is
retained indefinitely; legacy unindexed credentials expire under old bounds
(up to 24 hours plus asynchronous TTL cleanup). The five-minute encrypted deletion
proof supports receipt recovery after a lost response. Per-account usage counters
hold opaque identifiers/minute counts with TTL, not plaintext memory or email.
The website PR contains complete cloud-specific wording for owner review; it
has not been silently made live by this document.
