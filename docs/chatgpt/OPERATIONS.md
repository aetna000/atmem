# Operations and retention

Run one source-pinned cloud service using a dedicated service home/config/key.
Keep production emulator flags off; the service refuses mixed production and
emulator configuration. It refuses native ~/.atmem and mismatched service home.
Initialization is explicit; no real AtMem store is imported or modified.

The first cloud pilot is invitation-only. Populate allowed_firebase_uids with
approved actual UIDs; an arbitrary newly registered Firebase account cannot use
the service. Removing a UID requires a config reload/restart and revoking its
existing grant. Sign-in errors do not disclose whether another user exists.

## Health and observability
GET /health returns only service/engine versions and operating mode, not
account, memory, project config or token values. It is a liveness/config check,
not a claim Firestore is reachable. Use a scheduled **synthetic** scoped workflow
for readiness if approved, and clean its data. Observe aggregate HTTP status,
latency/error/conflict/quota counts without tool arguments or approval URLs.
Access logging is disabled because OAuth codes/approval IDs appear in URLs.
Cloud platform request logs and retention must be explicitly reviewed before
production; application logging does not control provider-managed logs.

No automatic background capture, provider calls or user-memory import exists.
No automatic secret rotation is implemented; keep encrypted backups and keys
separate, and test migration before rotation or rollback. A new key cannot open
old envelopes. Source format mismatch and cipher tampering fail closed.

## Persistence and cleanup
- A record persists until explicit governed deletion. Corrections keep native
  supersession/source history. Exact-record forgetting is not whole-lineage
  purging; do not promise it erased versions absent from its receipt.
- Pending action body expires after ten minutes. It is removed on the next
  successful household operation, or cancellation/completion; expiry rejection
  is immediate but physical cleanup is lazy. State this accurately to users.
- Browser/OAuth pending/code/access/refresh/grant data have separate expiries;
  access checks enforce them immediately. Firestore TTL on expires_at must be
  configured for physical cleanup, with optional bounded purge_expired_control.
  Do not assume TTL has been enabled by the supplied source/emulator tests.
- Obsolete snapshot chunks are removed after durable CAS. Inspect the cleanup
  flag. An ambiguous RPC commit never deletes possibly active chunks. Crashes
  may leave encrypted staged or obsolete chunks; prune_orphan_chunks is an
  operator maintenance method with a >=1h safety window, after quiescing traffic.
- Firestore backups/PITR, platform logs and ChatGPT copies are not erased by
  native forgetting. Select and disclose their actual retention before release.

## Costs and deployment
See deploy/chatgpt/README.md. Firebase Hosting alone cannot run Python MCP.
Cloud Run requires billing even within usage quotas. Snapshot storage keeps the
real engine but amplifies Firestore document reads/writes; benchmark cost and
latency with synthetic accounts before widening the pilot. Zero min instances
and one max instance reduce exposure but are not spending caps. No LLM/embedding
cost is introduced by this integration. A native indexed Firestore backend is
future work; do not market the snapshot adapter as high-scale cloud retrieval.

The approved atmemai pilot uses a separate named database and database-bound IAM. Never deploy
the demo deny-all rules over the production atmemai project's existing rules.
See verification.md for provisioned resources and actual deployment/test status.
The live website, existing default database and native memories are unchanged.

Use `/health` on Cloud Run. `/healthz` is intercepted by its reserved-path
frontend and can return a Google 404 without reaching the container. See
https://docs.cloud.google.com/run/docs/known-issues#reserved_url_paths .
