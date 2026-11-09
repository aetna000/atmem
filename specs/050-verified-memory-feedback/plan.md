# Implementation plan — Spec 050

Status: implementation started; see `implementation-evidence.md` for completed
work, the tested host-boundary fix and remaining integration. Governing requirements: `spec.md`; source
review: `research.md`. The implementation remains opt-in and is not released.

Maintain `benchmark-impact.md` and notify the owner before integrating changes
that can alter DolphinBench inputs, execution or scoring. Distinguish condition
changes from report-only changes. Benchmark execution is not authorized here.

## Technical context

Python 3.10–3.13; existing AtMem core authority, SQLite/SQLCipher stores, encrypted
EvidenceStore, review service, context engine, task-state contracts, MCP and control
web UI. Optional intelligence remains behind AtBot; no training framework or model
SDK becomes a base dependency. Linux, Windows and macOS remain supported.

## Architecture and ownership

1. **Observe:** adapter emits attributable turn/tool observations. A feedback service
   links existing context/evidence receipts; it cannot invent missing capture.
2. **Verify:** a separately authenticated verifier checks the target's actual state
   when authorized. Host claims, human attestations and LLM judgements remain distinct.
3. **Diagnose:** retain proposed/verified failure classification per required action.
   A successful read and an unsuccessful write never collapse into one result.
4. **Propose:** existing ReviewService receives a versioned correction, retrieval-profile
   change or typed rule candidate. Optional AtBot proposes, never approves or executes.
5. **Qualify:** an offline-first evaluator freezes exact inputs and bounds, runs paired
   comparisons, and records accept/reject/inconclusive without changing activation.
6. **Activate:** the authenticated owner confirms exact revision/scope and qualification.
   Existing authority is rechecked transactionally; derived code cannot rewrite policy.
7. **Enforce/monitor:** the MCP proxy or a qualified adapter checks the specific pending invocation; a real
   blocked-call receipt differs from a would-block observation. Compare regressions,
   suspend/revoke and collect a new outcome without automatic promotion or retraining.

This is a governed feedback loop, not a second memory database and not a training
service. Built-in `atmem/invariants/` continues to verify product guarantees; runtime
user policies live in a separate explicit namespace and cannot change those guarantees.

8. **Retrieve documents:** a shared RAG service authorizes a registered provider and
   fixed scope before search/inspect, applies requested jurisdiction/effective-date
   filters, validates provenance and scope, and records authorized delivered evidence
   in the existing encrypted vault. External passages never become instructions or
   admitted memories merely because they were retrieved.

## Existing components to extend

| Component | Reuse and extension |
|---|---|
| `atmem/extract/models.py`, `atmem/extract/review.py` | Typed units, ReviewAuthorization, evidence-bound decisions; additive candidate kinds and review capabilities. |
| `atmem/contracts/models.py`, `atmem/contracts/task_state.py` | Existing scope/identity concepts; add dedicated versioned feedback contracts, not untyped dictionaries accepted from a model. |
| `atmem/context_engine/service.py`, `atmem/context_engine/profiles.py` | Authorized candidate/context receipts and versioned retrieval configuration; no change to canonical permission. |
| `atmem/evidence/store.py`, `atmem/store/sqlite.py` | Protected evidence and canonical persistence; additive migrations, receipts and indexes. |
| `atmem/graph/identity.py` | Exact identity resolution; ambiguous entities require review. No new fuzzy identity resolver. |
| `atmem/task_state/enforcement.py`, `atmem/task_state/host_boundary.py` | Capability and host-identity conventions; do not equate registry presence with independently tested enforcement. |
| `atmem/action_guard.py`, `atmem/adapters/hermes/action_guard_plugin.py` | Preserve routing and detour guards. Compose the new rule decision by deny-wins at the actual tool boundary. |
| `atmem/control/server.py`, `atmem/control/assets/app.js`, `atmem/control/assets/app.html`, `atmem/control/assets/app.css` | Existing auth/CSRF, scoped Feedback screen, evidence links and explicit controls. |
| `atmem/mcp/server.py`, `atmem/cli.py` | Discoverable bounded report/proposal commands; no model-accessible owner capability. |

Proposed new modules:
`atmem/contracts/feedback.py`; `atmem/schemas/v1/feedback-*.json`;
`atmem/feedback/{service,store,verification,metrics,qualification,export}.py`;
`atmem/rules/{models,compiler,evaluator,lifecycle}.py`;
`atmem/adapters/hermes/feedback_guard.py`;
`atmem/control/feedback.py`; `atmem/cli_feedback.py`;
`docs/verified-memory-feedback.md`; `docs/benchmarks/verified-memory-feedback.md`.
Also `atmem/knowledge/rag/{contracts,service,sqlite}.py`,
`atmem/mcp/governed.py`, `atmem/mcp/guarded.py`,
`docs/governed-rag-and-mcp.md`, and corresponding real-store/client tests.
Paths are implementation targets, not claims that they exist today.

## Data and contract design

- `OutcomeRecord`: stable scoped identity, required-action set, captured context IDs/
  byte digest, invocation IDs, tool/schema/argument digests, delivery state, actual
  effect references, independent verification links, version and predecessor.
- `ActionCheck`: read/write, exact invocation, check type/version, result pass/fail/
  unknown/disputed, attributable verifier, evidence reference and failure reason.
- `FeedbackCase`: source episode and chronology, diagnosis plus assurance, supporting
  and contradicting evidence, original memory versions, reviewer decisions and revisions.
- `RuleCandidate`: typed predicates, target adapter/tool/schema/scope, source revisions,
  explicit applicability, priority ceiling, review and shadow receipts, expiry. Plain
  language rationale is inert content; no runtime eval of generated strings.
- `QualificationReceipt`: manifest/dataset/split digests, baseline/candidate/adapter/
  verifier versions, all task IDs and outcomes, counts, uncertainty, cost, thresholds,
  decision, expiry and authorizing issuer. Model cannot mint or alter it.
- `ActivationReceipt`: exact qualified artifact plus authority decision, generation,
  lifecycle state, current-source binding, superseded activation and rollback lineage.
- `ExampleExport`: explicit purpose/consent/recipient, reviewed record list, redaction
  policy, dataset split exclusions, provenance manifest and destination confirmation.

IDs and formats are versioned; maximum sizes and tool/schema registries are validated
before storage. Stable error families include denied, stale_revision, conflicting_retry,
missing_evidence, disputed_outcome, rule_unexpressible, qualification_inconclusive,
qualification_expired, enforcement_unavailable and covered_call_blocked.
No errors enumerate inaccessible objects. Repeated identical requests return the same
receipt; same idempotency key with a different payload is rejected.

## Storage, authority and deletion

Use the existing authoritative store and protected evidence service, not a new plaintext
training ledger. Semantic metadata is protected as well as bodies. Feature enablement
refuses insecure production stores; existing offline recall outside this opt-in feature
continues under its current contract. Test-only insecure options never establish the
production encryption claim.

Where canonical transactions and encrypted artifact persistence cannot be one transaction,
use staged encrypted evidence plus a durable outbox. No candidate becomes qualified or
active until required references are verified and its canonical commit completes. Retry
is idempotent; a crash leaves pending/unavailable state, never an implicit allow. Inventory
and garbage-collect only verified unreferenced staging artifacts under retention policy.

Feedback payloads currently fit inline in the existing vault transaction, so no
artifact outbox is needed for them. An encrypted per-scope Home checkpoint binds
the committed ciphertext root and catches row deletion or DB-only rollback. A
pending/new-root protocol spans SQLite commit and checkpoint publication; real
effects dispatch only after this context completes. Include checkpoints with
keys/accounts in supported backups. Whole-Home-and-key rollback has no external
monotonic witness and must not be advertised as detected. Full activation/restore
reconciliation remains T017; this checkpoint does not qualify an adapter.

Dependencies between source revisions, rules, profiles, receipts and exports are explicit.
On supersession/deletion/permission revocation, suspend dependent authority immediately at
dispatch; asynchronously repair indexes and verify deletion of registered representations.
Restore reconciles revocation generations before serving calls. Export withdrawal marks
local lineage and prevents new export; it cannot promise recall of uncontrolled copies or
removal from already trained weights. Key custody and recovery use existing home contracts.

## Deterministic rule interpreter and enforcement

Implement an allowlisted data interpreter, not code generation. Initial predicates:
required argument exists; typed argument equals a reviewed literal; approval receipt is
valid for exact principal/scope/tool/schema/argument digest/expiry and unused nonce.
Business language that needs unsupported arithmetic or ambiguous semantics cannot compile.

MCP guarded dispatch is the generic enforcement surface; Hermes is an additional
adapter with a concrete final-tool hook candidate. Pin supported host and installed artifacts in conformance evidence
before activation becomes available. Intercept real dispatch, wrappers and supported batch
members. Revalidation and dispatch must share a bound invocation token; source revocation
or changed arguments invalidates it. Define dispatch as the atomic admission boundary;
a call admitted before revocation may already be in flight and is reported as such.

Registered alternate tools are checked under the same covered action mapping. An unknown
wrapper or schema that might execute a covered action is refused in the enforcing path.
Calls outside the adapter's control cannot be claimed prevented. Existing guard decisions
are preserved and composed by deny-wins. Enforcement outages block covered writes; offline
read-only memory and unrelated operations retain their existing behavior.

Conformance evidence is keyed by adapter/version/schema/OS. Task capability registration
is advertised only for the action classes actually supported and tested. Host fixtures
alone are plumbing; the installed-host journey must demonstrate a tool call really did
not execute. No real user data or production side effects are needed for this proof.

## Generic RAG and MCP integration

Re-use `EvidenceScope`/`EvidencePrincipal` and current encrypted EvidenceService,
plus `AuthorityScope` for agent/workspace binding. Authenticate credentials afresh
at each service operation; keep agent and workspace capability grants in the same
protected authoritative vault. A model cannot send a role, endpoint, token, tenant
or alternate scope as a search argument. Owner configuration is separate from MCP.

Use one versioned provider interface: bounded `search(request)` and
`inspect(document_id, chunk_id, revision, scope)`. A trusted application registers
the adapter implementation; model tools select only an authorized source ID.
Adapters can call existing SQL/vector/HTTP/MCP RAG clients using their own scoped
credentials. The reference adapter stores documents in the existing encrypted SQLite vault
and builds FTS5 only in RAM within an authorized query. No plaintext disk index
or SQLCipher dependency is needed for this adapter.
Retrieve original passages and citation metadata, not an LLM-generated answer.

Each hit includes exact scope/source revision, stable document/chunk identifiers,
text digest, citation, jurisdiction and nullable effective dates. Validate complete
results before persistence. Requested date/jurisdiction filters exclude missing
metadata; intervals are [effective_from, effective_to). Registration revocation
and policy generation are rechecked after the provider returns. No implicit fetch
of a citation URL and no user-supplied SQL or dynamically imported adapter code.

Keep stdio local-first. MCP server identity is bound by an application credential
and fixed agent/workspace; revocation is read each call. The new server must use
explicit supported legacy protocol revisions (2025-06-18 and 2025-11-25) and a
documented negotiation error for newer/unknown revisions. Official 2026-07-28 MCP
was reviewed: it uses per-request metadata and has no initialize handshake. Do not
claim support for that revision until implemented/tested as a distinct path.
Retain the legacy server unchanged for existing users; the new governed server
must not inherit its unrestricted subject override or optimistic version echo.

Expose RAG search/inspect, feedback report/propose, rule preview and guarded-call
tools only when the service capability is implemented. A proxy handler is chosen
from owner configuration, never arbitrary code/URLs supplied by a model. Protected
writes recheck exact final arguments and authority in the server, persist an
in-flight record before execution, and return an uncertain receipt on transport
ambiguity. Repeated writes use a payload-bound idempotency key; do not automatically
retry unknown effects. A pure check tool has no control of external host calls.

## Metrics, UI and qualification

One service supplies CLI/API/MCP/dashboard counts using spec denominators. The Feedback
view shows agent/workspace and profile version, verification coverage, wrong-answer rate,
coverage, per-action failures, disagreements, expiry, latency/cost and proposed changes.
A detail view joins exact retained evidence to one action and its checks. Owner-only
controls are review, start shadow, inspect qualification, activate, suspend/revoke, rollback
and preview/export. Keyboard operation, clear focus, accessible error messages and distinct
unknown/disputed states are acceptance requirements.

Initial work uses synthetic isolated fixtures only to verify contracts and safety. Before
any efficacy run, freeze an operator-approved manifest with independently established native
and current-AtMem baselines, held-out corpus/license/scope, cluster-safe splits, statistical
power, all SC thresholds, verifier independence and a finite budget. A missing budget
permits zero paid calls. No DolphinBench execution is implied; its separate prerequisites
remain mandatory if a future authorized manifest selects it.

Maximum three candidate attempts per failure hypothesis. A failed held-out gate cannot
be tuned against and reused as an untouched test. Preserve every trial and report failure
or inconclusive rather than extending compute. SC-003/004/005 apply without retrospective
threshold changes. Export only after FR-019 consent and never include held-out examples.

## Delivery phases and stopping points

1. Contracts, native baseline definition and regression inventory; no side effects.
2. Encrypted outcome chain, scope/identity grants, provider registration and document
   retrieval through generic MCP; independent verification and per-agent reporting.
3. Versioned profile qualification and review; shadow-only until statistical gates pass.
4. Typed rules plus generic MCP proxy enforcement and adapter integration, explicit
   activation, revocation and recovery. Hermes is never required for core/MCP operation.
5. Consented example export, dashboard/CLI parity, cross-platform installed-artifact gates.
6. Review evidence and choose release scope. No training, promotion or publication is
   automatic. A failed gate stops the affected activation, not useful offline diagnosis.

## Verification and release

Implemented extensions (2026-11-10): the application-owned Home restore/adoption
binding is rechecked at feedback admission. Scoped owner reconciliation is a
separate SDK/CLI operation, works without an agent grant and disables restored
authority before requalification. Arbitrary file-copy/direct canonical restores
remain explicit operator procedures. The Hermes service bridge verifies the
recorded candidate boundary hashes, composes through the existing action-guard
plugin's optional binding and places one-time approval consumption in the shared
dispatcher; its final hook stays read-only. Unknown tools/batches deny unless
explicitly configured as read-only. This is a pinned development candidate,
not owner-runtime installation or universal interception. Active-profile engine
outages use bounded native deterministic context and retain a fallback record;
governance violations never fall back. Dashboard exports use an application-owned
signer, explicit consent/preview/review/confirmation and recipient encryption;
no private key enters an HTTP request or browser state.

Source cleanup resolves typed forward protocol links and defining-record
ownership rather than recursively treating raw tool payload IDs as authority.
Document, canonical-source, outcome, artifact and receipt namespaces are distinct.
Cached/copy payloads cannot seed backward deletion of their referenced originals.
Active or qualified dependent policy must be explicitly revoked before purge;
deleting a source cannot silently remove its guard. Opaque copies without protocol
lineage require their own evidence retention/deletion and are not claimed erased.

Tests use real temporary AtMem stores and synthetic principals; mocks supplement, never
replace, store and installed-host journeys. Include auth/injection, matched invocation,
unknown/disputed evidence, retries, TOCTOU, wrapper bypass, rule conflicts, outage,
rollback, deletion and store-only disaster recovery. Test migrations from the latest
published store fixtures and all supported Python/OS targets.

No broad benchmark run during implementation without a frozen approved manifest. Run
existing memory/core/task-state/action-guard regressions once relevant changes land; repeat
only on new changes or unresolved failures. Record installed wheel/bridge versions, source
commit, test outputs and operational limitations. Follow AGENTS.md release coordination
only if publication is subsequently requested. Preserve the original checkout's active
Spec 048 and unrelated work; this worktree alone selects Spec 050.
