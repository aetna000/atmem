# Operations and retention

Run one source-pinned cloud service using a dedicated service home/config/key.
Keep production emulator flags off; the service refuses mixed production and
emulator configuration. It refuses native ~/.atmem and mismatched service home.
Initialization is explicit; no real AtMem store is imported or modified.

The production configuration uses registered, verified-email Firebase accounts.
The invited policy remains available for closed testing. Ordinary tool callers
never provide the target account UID. Firebase account changes are revalidated
on plugin refresh; existing access tokens last at most ten minutes. Account-wide
deletion fences all grants and household access immediately at its transaction.

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
  TTL is verified ACTIVE in the atmem-chatgpt database; emulator behavior does
  not prove production TTL deletion timing.
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

## Account-wide deletion and deployment compatibility
Direct users to `/account/delete`, linked from the connection page. Fresh Firebase
password authentication, an account-labelled preview and explicit confirmation
are required. Neither an MCP call nor a signed-in browser alone can confirm it.
The account fence is committed before purge. Household loads, chunk staging,
manifest swaps and account-bound controls check that fence in transactions.
Purge removes every current/superseded/orphan chunk, all scopes and indexed
controls; Firebase deletion uses a fresh user ID token rather than Auth-admin IAM.
A five-minute encrypted deletion proof supports lost-response receipt recovery.
Legacy unindexed auth controls remain inaccessible and expire/TTL within their
old retention (up to 24 hours plus asynchronous TTL processing).

If Firebase deletion fails after purge, do not reopen access or claim success.
The same proof can retry while valid; fresh credentials can renew the same
blocked deletion after expiry if the Firebase account still exists. Keep the
minimal HMAC-addressed fence and encrypted structural receipt indefinitely to
prevent resurrection. Provider history/logs and external ChatGPT copies are not
verified erased. Manual account/support recovery must never remove the fence.
Do not roll back to pre-fence code or copy an old entire database over account
markers. Snapshot restore rejects fenced accounts. Existing 8 MiB default
snapshots are compatible; configurations above 8 MiB now fail explicitly to keep
atomic fenced staging below Firestore request limits. This is an optional-cloud
config tightening; no local AtMem schema or store is migrated.

## Encrypted snapshot recovery
`Repository.export_snapshot(account)` creates a key- and account-bound encrypted
artifact. Keep its recovery key separately under operator controls. Restore using
`restore_snapshot(account, blob, expected_generation=observed_generation)` after
quiescing that account. It validates encryption, format, real native engine and
scope audit chains before CAS. Wrong key/account, concurrent generation changes,
plaintext or a deletion fence fail closed. This is an operator SDK operation, not
an MCP tool; it neither enables a backup schedule nor verifies a managed disaster
recovery SLO. The real-emulator recovery test demonstrates native data/audit
round-trip; actual operator-key rotation remains separate work.

## Public usage admission and monitoring
Tool admission has a durable 30-calls/account/minute default, independent of
process restarts and of the per-peer HTTP limiter. It stores only opaque account
identifiers, a minute window and count with TTL. Quota exhaustion returns
account_rate_limited and retry_after_seconds; it cannot bypass memory authority.
Account deletion purges that account's counter as well. These bounds, max instance
1 and max snapshot 8 MiB are not financial spending caps or load qualification.

monitoring-policy.json uses the built-in Cloud Run request count (no memory/tool
arguments) to create Console incidents for repeated HTTP 5xx responses. It has no
notification channel: select and verify an owner-controlled destination before
relying on paging. Numeric billing budget/alert settings still need an operator
choice; no amount is invented or an existing website billing limit changed.
