# Governed documents and host-neutral MCP — development preview

Spec 050 implementation on `feat/verified-memory-feedback`; not a released
feature. Existing memory recall, MCP server and DolphinBench routing stay intact.
The document service is opt-in. It is not a bundled law corpus or a legal-advice
system and does not claim current-law completeness.

## Connect an existing retriever

Use `FeedbackService(existing_evidence_service)` and `RagService(feedback)`.
The authenticated owner grants the application principal explicit `search` and
`inspect` capabilities for one agent/workspace with an expiry. Identity derives
from the evidence credential, not model arguments. Register a `RagSource` with
fixed scope, collection, revision and explicit `egress` (`none` or `remote`).
Pass a trusted application adapter object to `rag.register(owner_token, source,
adapter)`. Owner tokens stay in application setup; never pass them to a model.

The adapter implements:

```python
def search(self, source, query, *, deadline) -> tuple[RagHit, ...]:
    ...  # Use the existing retriever with scoped application credentials.

def inspect(self, source, document_id, chunk_id, *, deadline) -> RagHit:
    ...
```

Return original passages, SHA-256 of their exact UTF-8 text, citation/locator,
source/document/chunk identity, revision, fixed scope and known jurisdiction and
effective dates. Respect the monotonic deadline. The service validates results,
filters requested jurisdiction/date, and rechecks authorization and registration
before returning them. A requested date excludes unknown start dates; validity
intervals are `[effective_from, effective_to)`. Unfiltered unknowns remain explicit.
URLs are citations, never automatically fetched. Adapter code is trusted owner
configuration; the model cannot provide SQL, executable code or endpoints.

`SQLiteRagProvider(feedback)` is the built-in reference provider. Register it with
`provider_id="sqlite-vault"`, `egress="none"`; use owner-only `put_documents` to
import bounded batches of `RagHit` values. Persistent passages/metadata use the
existing encrypted evidence vault. The FTS5 search index exists only in RAM for
an authorized query. Updating a passage requires a new source revision rather
than overwriting content under an existing document/chunk/revision identity.

`rag.search(session, RagQuery(...), idempotency_key=...)` returns a retained receipt.
`rag.inspect` returns the exact retained passage from that receipt, not a live
refetch. Revoked or changed sources cannot be inspected through this model path.
External documents are untrusted evidence and are not automatically admitted as
memory or promoted into rules. Retrieved instructions cannot grant permissions.

## Local MCP and CLI

Owner configuration and an existing encrypted EvidenceService store are required.
Put the application credential in an owner-private file (POSIX mode 0600 or a
verified protected Windows DACL). Never put a token in tool arguments or a command
line. The following command starts a local subprocess, not a public server:

```sh
atmem rag --root /path/to/existing/control --vault-id MY_VAULT \
  --credential-file /path/to/private/application.token \
  --agent writer --workspace project serve
```

The same prefix supports `sources`, `capabilities`,
`search --source law --query 'filing deadline' --key request-1 --jurisdiction XX --as-of 2026-01-01`,
and `inspect --receipt RECEIPT --document DOCUMENT --chunk CHUNK`.
No default memory store is opened. The CLI reattaches only already registered
built-in local sources. External adapters use an application-owned Python entry
point that constructs `RagService`, registers its trusted adapter and calls
`GovernedMCPServer(feedback, rag, session).serve()`.

Supported transport: **local stdio**, legacy MCP revisions **2025-06-18** and
**2025-11-25**, with initialization. Unsupported versions are rejected. There is
no claim of MCP 2026-07-28, Streamable HTTP, OAuth hosting or public availability.
See the versioned official sources in Spec 050 `protocol-decisions.md`.

Implemented tool inventory (`guarded_*` requires an explicitly configured
application dispatcher; `feedback_propose_*` requires canonical memory.
The standard CLI does not register arbitrary handlers):

<!-- governed-tool-inventory:start -->
| Tool | Capability | Effect |
|---|---|---|
| `feedback_capabilities` | Any active grant | Current fixed scope and granted operations; unrelated host tools remain advisory. |
| `rag_sources` | search | Scoped registered sources. |
| `rag_search` | search | Original passages and encrypted request/result receipts; no memory admission. |
| `rag_inspect` | inspect | Retained passage, subject to live source authorization. |
| `feedback_outcome` | read | Retained observations; host reports remain unverified. |
| `feedback_quality` | read | Counts for an owner-frozen schedule; undefined rates are null. |
| `feedback_report_outcome` | report | Append attributable unverified observations; no review or activation. |
| `guarded_execute` | execute | Optional application-owned dispatch; persists intent before effects and refuses blind retries. |
| `guarded_inspect` | read | Optional inspection of an execution intent/result; not independent verification. |
| `feedback_propose_rule` | propose | Requires an explicit canonical-memory binding; source-grounded proposal only. |
| `feedback_propose_profile` | propose | Requires an explicit canonical-memory binding; bounded profile proposal only. |
<!-- governed-tool-inventory:end -->

Tool annotations guide clients; server-side authority enforces access on every
call. MCP connectivity does not control tools outside this server. Guarded proxy
execution is available through the optional dispatcher API. The dashboard and
owner export SDK described below are implemented development surfaces. Production
activation qualification and complete lifecycle acceptance remain Spec 050 work.

CLI feedback operations use the same service: `outcome --id ID`,
`quality --schedule ID`, `report --file outcome.json --key KEY`,
`propose-rule --file candidate.json --key KEY` and
`propose-profile --file candidate.json --key KEY`. Proposal commands and tools
require an additional explicit `--memory-db` binding to an existing encrypted
canonical store, plus the authenticated `propose` grant. A file's scope must
match the bound caller. MCP derives scope server-side. No model tool can review
or activate a proposal. Ordinary plaintext/local recall remains unaffected.

## Retention, availability and limitations

Exact passages, queries, source metadata, observations and readback evidence are
encrypted at rest in the existing vault. Authorized tool responses leave the
application boundary in plaintext and can enter the calling agent/provider's
context; that agent's storage/egress policy is separate. A remote RAG adapter
sends queries to its explicitly configured provider. A local adapter does not.

Revocation is checked per call and after provider work. Timeouts, unavailable
providers and malformed results produce explicit errors, not fabricated answers.
A hung read holds a bounded worker slot until it finishes; retries cannot spawn
unlimited workers. No document-provider deadline changes DolphinBench model/judge
retry policy. Use a new request key for a deliberate new search; conflicting reuse
is rejected and identical successful retries return the original receipt.

If access is revoked before a final audit update, the already retained pending
attempt remains unknown. Capture does not prove model use. Ordinary memory
forgetting invalidates future selection but does not itself erase historical
flight evidence. Owner-previewed registered-copy cleanup is described below;
backups, client copies and external providers have separate retention.

Current evidence is isolated macOS testing with synthetic documents, real
credentials/stores and actual MCP subprocesses. It is not a quality benchmark,
cross-platform certification or a released artifact. See Spec 050
`implementation-evidence.md` and `benchmark-impact.md` for exact status.

## Integrity, quotas and supported backups

The opt-in ledger has encrypted per-scope checkpoints under the Home's
`.feedback-checkpoints` directory. These anchor ciphertext outside the DB:
deleting a policy row, removing an anchor while records remain, or replacing only
the DB with an older copy fails closed. Pending/committed checkpoints recover
crashes around SQLite commit. Effects dispatch only after both commits complete.
Vault data-key rotation preserves the checkpoint identity key and roots.

A supported backup includes the protected database, identity/accounts, required
keys, artifacts where used, **and `.feedback-checkpoints`**. A DB alone is not a
usable evidence backup. An existing pre-checkpoint development feedback ledger
is not silently trusted; no published release used that ledger. Restoring a whole
old Home together with all its keys and anchors cannot be distinguished from the
old legitimate state without an external monotonic authority. Full restore and
activation reconciliation remain acceptance work; no universal rollback-proof
claim is made. Standalone retained-action reconstruction has been tested without
the original host, destination or canonical memory process.

The development service bounds a scope to 10,000 historical encrypted records
and 64 MiB of ciphertext. Contract messages are bounded to 256 KiB and stdio
frames to 1 MiB. Exhaustion fails explicitly, rather than silently discarding
evidence or claiming complete retrieval. Retention/compaction and larger-scale
performance qualification remain work; the reference RAM-FTS adapter is not a
million-document performance claim.

The first opt-in feedback mutation upgrades the evidence container to **format
4**. Ordinary native-only stores retain their existing format. The published
2.3.14 reader refuses a format-4 vault rather than rotating its keys while
discarding unknown scope partitions. Upgrade is tested against the actual public
2.3.14 wheel. Downgrading a feedback-enabled vault to that old binary is not
supported; restore a complete pre-opt-in backup instead.

## Action verification and uncertain effects

`VerificationService` accepts only owner-registered callbacks and separately
authenticated verifier identities. `Readback` contains exact checks and retained
evidence. `state_only` is the default: correct destination state alone cannot
prove an agent made the required call. To count a completed action, a verifier
must use `binding="effect_receipt"` and independently read an operation journal
binding the outcome, run, turn, invocation, canonical argument digest and a unique
backend effect reference. One reference cannot prove different invocations.
All required checks must pass on one matching invocation; partial calls are never
combined. Conflicts stay disputed. Proposed failure labels are not certified
causal diagnoses. Host/model reports never become independent verification.

The optional `GuardedDispatcher` persists admission and a scope/tool hold before
dispatching. A timeout or lost acknowledgement leaves an uncertain receipt and
the hold survives new retry keys, restarts and registered-source cleanup. Even a
successful same-key retry returns the original admission; use `inspect` for the
latest status. A deliberate new invocation is permitted after a healthy handler
acknowledgement; that acknowledgement still does not verify task success.

Application handlers can opt into `register(..., with_context=True)` and receive
`invoke(arguments, context=...)`. The application-owned context carries the
execution receipt, idempotency key, authenticated actor and fixed scope, so a
backend can persist operation correlation. It contains no credential. A normal
return must mean the handler has a definitive response; handlers must raise on
ambiguous effects rather than hiding transport failures in an ordinary result.

Unknown effects are never replayed automatically. The owner SDK's `reconcile`
requires a retained, independent effect-bound verification of the exact proxy
execution and a trusted backend-terminal journal receipt. A state snapshot or
model assertion cannot clear a hold. A still-running local handler, changed
verifier, disputed result or missing/deleted evidence prevents reconciliation.
The application is responsible for the backend's terminal-journal contract; the
proxy cannot terminate a remote operation or undo a completed effect.

## Review, dashboard, deletion and export

Rule/profile proposals reuse the canonical engine's review authority. Source
generation, exact content digest and scope are checked again under transaction.
Review authorizes neither execution nor activation. The three supported rule
predicates are argument presence, exact typed equality and approval-required.
The compiler executes no generated code. A native guard veto always wins.

`RuleLifecycle` records encrypted versioned activation receipts. Active use
requires a reviewed candidate, current eligible sources, accepted unexpired
qualification and matching runtime versions. `rollback` creates a new generation
from an exact previously active generation only if those checks still hold.
Revocation, expiry, source deletion and restore quarantine cannot be bypassed
using historical receipts. The current offline qualification evaluator is
**diagnostic and always inconclusive**; it cannot activate production behavior.
Test-only trusted-store fixtures exercise consumers of accepted authority and
are explicitly not qualification or efficacy evidence.

The existing local dashboard accepts an optional `FeedbackDashboard` with a
trusted signed-in-identity/session binding and optional per-request memory
factory. It exposes real scoped quality counts, exact per-action arguments,
checks, source evidence, proposal review and shadow/suspend/revoke controls.
Existing login, origin and CSRF checks apply. Without this application binding,
the screen reports unconfigured. Production activation, rollback and export
consent browser journeys remain incomplete; the activation button is disabled.

Owner SDK `FeedbackRecovery.preview_forget` / `forget` requires exact preview
confirmation and privileged deletion authority. It removes registered scoped
source-dependent feedback payloads, retains content-free revocation/idempotency
anchors, and checks canonical deletion completion. RAG re-registration requires
a new generation. `reconcile_after_restore` disables restored grants, approvals,
export consents and RAG sources, and quarantines active/qualified behavior until
fresh qualification. The application must invoke reconciliation as part of its
restore procedure; automatic integration into every restore path remains work.
Neither operation erases provider originals, backups, recipient exports or
forensic storage remnants.

`ExampleExportService` is an owner-only SDK using the existing export privilege,
explicit purpose, recipient public key, bounded record IDs, expiry and exact
preview confirmation. It uses real recipient encryption and includes lineage
and exclusions. Unverified, disputed, known evaluation/test records, detected
secrets and unrevalidated sources are excluded. Secret detection is not a
guarantee of anonymization; review the exact authorized preview. Withdrawal
blocks new exports, not already delivered copies. It starts no training.

Remaining acceptance work includes independent production qualification, complete
cost/latency gates, the installed Hermes service adapter, full consent/activation
UI, automatic recovery hooks and actual cross-platform CI results. No existing
DolphinBench score is changed or relabelled by these development features.
