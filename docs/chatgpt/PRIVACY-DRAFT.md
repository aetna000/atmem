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
separate retention; their actual values are **not yet selected or verified**.
Do not promise complete erasure from these systems. Uninstalling/disconnecting
revokes access but is not a memory deletion. Deleting a key prevents recovery and
is not a substitute for a verified native forget receipt.

Contact/support and data-access/deletion handling: use the owner's approved
published support page once available. The existing website privacy page mainly
covers that website; it has not been silently reused as this cloud policy.
No sale/sharing, lawful-basis, age, residency or response-time promise is made
without the operator supplying and reviewing the actual policy.
