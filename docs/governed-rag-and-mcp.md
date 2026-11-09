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

Canonical memory uses subject/agent/workspace scope inside a physical home. An
application must map each tenant to its own canonical memory home and encryption
authority. `FeedbackService(..., memory=memory, memory_tenant_id="TENANT")` binds
that home to one configured tenant; it defaults to `local` for existing local
homes. A different tenant is denied even with a valid credential and a matching
subject name. Never derive the home or this binding from model arguments, and
never map distinct tenants to the same canonical home. A service with no canonical
memory can still serve its independently scoped encrypted document partitions.

Canonical-source eligibility reuses the core store's bounded authorization query
before loading record contents, including workspace/agent, active status,
retrieval exclusions and sensitivity. Feedback defaults to `egress_class="remote"`:
sensitive/restricted canonical sources are withheld. Only a trusted local-only
application should explicitly select `egress_class="local"`; stdio transport by
itself does not prove a caller keeps data on device. Proposal operations return
closed versioned receipts, not raw canonical sources or human review notes,
including on legacy cached retries. Full encrypted source snapshots remain
available through the privileged review surface.

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
application dispatcher; execution and `feedback_propose_*` require canonical memory.
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
| `guarded_tools` | execute | Exact schemas and versions for owner-registered proxy tools in this scope. |
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

Create and protect the backup/restore root with AtMem's existing
`protect_private_path` **before** copying private keys/accounts/checkpoints.
On Windows a plain `copytree` does not preserve DACLs; copies must inherit an
owner-private destination or be created with explicit protected DACLs. The reader
rejects an unprotected checkpoint rather than silently accepting or repairing it.

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
The journal must also distinguish succeeded, failed, not-dispatched and unknown
operations; correct destination state after a failed operation is not success.
Generic stdio does not itself establish trusted host run/turn IDs: the application
must retain that correlation independently. A caller's reported IDs are not proof.
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
verifier, disputed operation status or missing/deleted evidence prevents reconciliation.
Conclusive terminal-operation evidence can clear a hold even when task checks
failed; the retained failed task is not promoted to success. This permits an
explicit corrected attempt without conflating task quality with effect certainty.
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

Diagnostic attempts are reserved in protected storage before replay. Failed or
crashed attempts remain charged; a same-key retry returns the retained failure or
an explicit in-flight/unknown result rather than re-executing. Content-free
per-hypothesis attempt counters survive registered-source cleanup. The current
disk check bounds serialized qualification payloads, not complete filesystem or
provider consumption; full production resource qualification is still pending.

The existing local dashboard accepts an optional `FeedbackDashboard` with a
trusted signed-in-identity/session binding and optional per-request memory
factory. It exposes real scoped quality counts, exact per-action arguments,
checks, source evidence, proposal review and shadow/suspend/revoke controls.
Existing login, origin and CSRF checks apply. Without this application binding,
the screen reports unconfigured. With matching runtime configuration, an owner
can select an accepted current qualification, inspect its evidence and confirm
activation, or request rollback to a previous active generation. The server
rechecks authority and source/version/qualification state; displayed metadata
does not grant permission. With only the current diagnostic qualifier, activation
remains unavailable. The export workflow has separate consent, exact preview,
manual review, confirmation and withdrawal controls. Production qualification
remains acceptance work. For threaded HTTP actions, supply a per-request
`memory_factory`; do not share a thread-bound SQLite connection from setup.

Owner SDK `FeedbackRecovery.preview_forget` / `forget` requires exact preview
confirmation and privileged deletion authority. It removes registered scoped
source-dependent feedback payloads, retains content-free revocation/idempotency
anchors, and checks canonical deletion completion. RAG re-registration requires
a new generation. `reconcile_after_restore` disables restored grants, approvals,
export consents and RAG sources, and quarantines active/qualified behavior until
fresh qualification. The supported Home preflight/adoption workflow now changes
a content-free machine binding: feedback refuses the read-only restore and then
requires scoped reconciliation after adoption, including after process restart.
An old reconciliation ID cannot clear a newer adoption. Corrupt/missing binding
state fails closed. Ordinary native recall and historical evidence inspection
are unchanged. A Home cannot be made globally rollback-proof without an external
monotonic witness; arbitrary file copies or direct canonical database restores
still require explicit operator reconciliation and remain outside automatic
restore detection.
Neither operation erases provider originals, backups, recipient exports or
forensic storage remnants.

After administrator-approved Home adoption, use a private **owner** credential
file, not the revoked application grant, to quarantine the exact scope:

```sh
atmem rag --root /existing/control --vault-id VAULT \
  --credential-file /private/owner.token --agent AGENT --workspace WORKSPACE \
  reconcile-restore --restore-id ADOPTION_EVENT --confirm ADOPTION_EVENT
```

This disables restored grants/approvals/consents/source registrations and
quarantines covered rules/profiles. It does not restore access, issue a fresh
qualification or replay an uncertain write. The owner must explicitly regrant
the required capabilities, reattach/register authorized sources and independently
requalify behavior before activation. The command is owner-only CLI/SDK; it is
not exposed to models through MCP. Repeat the same event ID for an idempotent
retry; use a new ID for a new restore event.

`FeedbackService.operational_metrics(session)` returns authenticated, scoped
process-local counters and p50/p95 over the last 256 calls per closed operation.
They contain no passages, arguments, tokens, provider exception text or dynamic
metric labels. Counters reset on restart; 64 scopes are tracked at most and
telemetry exhaustion cannot discard evidence or block an action. Rule-evaluation
latency is separate from the full proxy request, verification and provider time;
these samples do not qualify a performance improvement or the production budget.

An application may use owner-only `record_usage` with an already observed
provider receipt, run ID, integer USD micro-units, input/output token counts and
model-call count. Receipt reuse cannot double-count or reassign a run. Quality
reports aggregate only retained scheduled runs and label these costs as partial
host reports, never verified billing. Each count/cost may be explicitly unknown;
known subtotals remain separate and a missing component makes the total null.
Overflow is explicit as well. Missing capture is null, not zero. This API
makes no model calls and grants no spending authority. The dashboard displays
the same missing/partial usage distinction.

`ExampleExportService` is an owner-only SDK using the existing export privilege,
explicit purpose, recipient public key, bounded record IDs, expiry and exact
preview confirmation. It uses real recipient encryption and includes lineage
and exclusions. Unverified, disputed, known evaluation/test records, detected
secrets and unrevalidated sources are excluded. Secret detection is not a
guarantee of anonymization; review the exact authorized preview. Withdrawal
blocks new exports, not already delivered copies. It starts no training.

For the optional dashboard workflow, the trusted application supplies
`FeedbackDashboard(..., export_signer=...)`; that callback returns the signing
public/secret key pair from the application's own protected key custody. The
browser supplies only the recipient's **public** ML-KEM-768 key, purpose,
explicit outcome IDs, development/train destination and a consent expiry of at
most seven days. No signing key or recipient private key is accepted over HTTP.
The feature remains unavailable without the configured signer. Actual scoped
export authority is rechecked before signing-key access. Consent precedes an
exact plaintext preview; a separate reviewed confirmation binds its SHA-256 and
recipient before downloading a recipient-encrypted JSON bundle. Editing the
form invalidates its preview; logout clears its content and pending requests.
Withdrawal prevents future export and does not recall existing copies. Known
RAG evidence is revalidated against the complete registered source snapshot at
both preview and export, including cached retries: revocation, revision changes
and missing receipts exclude the example. No provider fetch occurs during export.

Frozen quality schedules may additionally specify `task_class` and `versions`
(a bounded map of version names to identifiers). These are owner-supplied before
observations, never inferred from model text or retroactively overwritten.
Quality reports include the same denominators per class/version, preserving
missing tasks; legacy schedules explicitly show unspecified versions/classes.
The `uncertainty` field uses whole-episode resampling for diagnostic 95% rate
intervals. Fewer than two observed clusters or a zero denominator is
inconclusive. These intervals do not establish adequate statistical power,
production qualification or a measured quality improvement.

Remaining acceptance work includes independent production qualification, complete
quality/resource qualification gates, production Hermes conformance, recovery
coverage outside the supported Home workflow and final cross-platform CI results. No existing
DolphinBench score is changed or relabelled by these development features.

An offline diagnostic can measure the pure interpreter with 1,000 applicable
synthetic rules; it opens no memory store, dispatches no effect and calls no model:

```sh
python scripts/evaluate_verified_memory_feedback.py \
  --manifest tests/fixtures/feedback/baseline-manifest.json \
  --output /path/to/a/new-diagnostic-report.json
```

The file is created exclusively, never overwritten. The report enforces frozen
baseline/resource definitions and records actual p50/p95 and elapsed time. Native
and AtMem quality outcomes, power, independent conformance, false-denial coverage
and retrieval overhead remain insufficient evidence. Fast synthetic evaluation
cannot issue qualification, activation or an efficacy claim. Compilation,
authority/storage and remote time are explicitly outside the pure rule latency.
