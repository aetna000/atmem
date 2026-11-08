# Authority and storage contracts

All plugin tools obtain the current authenticated OAuth subject server-side.
The tool schema has no tenant_id, user_id, subject_id, file path or arbitrary URL.
Only personal or explicitly owned project scopes resolve to canonical subjects.
Returned memory is labelled untrusted data. Return bounded text/records/activity;
source assertions are caller-asserted unless independently attested.

Mutation states: pending -> approved (authenticated human browser) -> completed;
expired/cancelled/stale/forbidden never commits. Intent digest binds operation,
user, scope, replacement text and expected source version. Tool args cannot
supply an approval boolean or generate their own approval credential. Pending
content is removed on completion/expiry; durable receipts contain structural
IDs/digests, not a second copy of the memory. Platform confirmations are extra.

Durability: repository.load returns generation+encrypted household. Engine runs
against a private temporary household and produces a new encrypted snapshot.
repository.commit(expected_generation, snapshot) atomically swaps the manifest
or raises conflict. Only after this succeeds may an operation report committed.
Namespaced intent state and engine audit/mutations share the same snapshot.
No durable success from local SQLite alone. Best-effort obsolete generation
cleanup is reported separately; no promise about Firestore backups/PITR or
ChatGPT copies. Reopen/retry returns the receipt or requires a new approval on
stale revisions. Quotas bound snapshot bytes, record count, tool input/output,
requests and auth flows. No model calls are needed.
