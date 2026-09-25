# Product continuity v1 — implementation contract

Objective: an explicitly enabled agent can preserve work across process restarts,
check uncertain external actions before repeating them, and show its recovery.
This contract defines the bounded product profile for PC-001–PC-006; completion
of each gate is tracked in tasks.md, not inferred from this document.

## Authority and public surface

Implement `atmem/continuity/service.py` over the existing EvidenceService and
EncryptedEvidenceStore, with an authenticated HTTP surface in `control/web.py`.
The first profile is local, explicitly enabled, collector/admin-authorized
workflow control with read access limited to existing evidence investigators.
No new implicit authority from host text, dashboard status, or telemetry.
The SDK uses a bearer credential and authenticates each request. The controller
checks current scope, enabled state and role before every decision. Disabling a
workflow stops new decisions; authority/key outage blocks, never falls back.

The workflow contains immutable operation definitions (tool name, exact arguments,
declared capabilities). Creation is idempotent only for identical definitions.
The controller mints opaque workflow/operation IDs; hosts mint run/attempt IDs.
All links are validated within authenticated tenant/subject/workspace scope.
No host checkpoint may declare a missing receipt complete. TaskStateService
remains the only writer of Spec 007 tasks; operation records do not silently
create/complete task items. Optional task binding must use its supported API and
current scope/enablement checks, with a pending projection explicitly reported.

Public methods: create workflow, enable/disable, inspect, begin attempt, record
outcome, renew lease, abandon with an operator reason. Begin returns `execute`, `query`, `completed`,
or `blocked`, plus opaque lease token and revision when applicable. Outcome
requires that token; stale tokens cannot change state. Full original result is
retained encrypted and returned only to authorized callers. Attempts carry
run ID, attempt ID, mode, start/end, reason and outcome; no host logs required.
Repeat attempt IDs never grant an additional tool invocation. User retry creates
a new attempt but preserves logical operation identity and arguments.

## Tool safety

Capabilities are immutable and operator-declared: `none`, `idempotent` with
positive retention seconds, or `query` with an explicit reliable receipt lookup.
Undeclared defaults to none. Idempotency key scope includes workflow/operation;
same key binds exact arguments. TTL starts at first possible dispatch, not retry.
After expiry, do not issue another execute for an uncertain operation.
Query returning not-found/pending/unknown never licenses execute. V1 query
recovery can confirm completion; otherwise it blocks for operator investigation.
V1 does not auto-retry a query-only action after claimed failure: a future
destination-specific fencing contract is required. This avoids pretending a
local lease fences an already dispatched external request.

An active lease prevents another concurrent invocation. Expired leases permit
query or idempotent replay within TTL only, not arbitrary redispatch. Late
receipts from superseded workers are retained but cannot change progress;
an expired unsuperseded attempt may still report its matching receipt. Persist
intent before returning execute. On exception, the
SDK records unknown if possible; losing the process leaves the same uncertainty.
Operator abandonment is stored with actor/time/reason, cannot manufacture a
receipt or authorize unsafe redispatch, and never means completed.

## Persistence and retention

Use encrypted append-only workflow snapshots/events inside the current vault,
with atomic compare/read/append under SQLite BEGIN IMMEDIATE. No plaintext
dispatch DB, separate secret store or bypass of key rotation. Add a generic
transactional append primitive; first continuity use advances the vault to schema
3 while retaining older evidence. Old schema-2 products reject this store and must not be used
to resume it. A workflow format version other than v1 fails closed.
Capture mode must be full. Fresh service instances re-read lock/key state.
Workflow deletion leaves an opaque tombstone so the same workflow cannot be
re-created and replayed; deletion must remove exact arguments/results while
preserving the non-replay barrier. Exports and deletion use existing privilege
rules. Rotation retains semantics. Transaction tests cover competing writers.

## Integration and user views

Ship `atmem/continuity/client.py` as the reusable SDK. Host registers normal tool
callbacks; the SDK requests product decisions, executes/query callbacks and
submits receipts. No reference to benchmark files or oracle. Ship a LangGraph
node wrapper and installed examples in `atmem/continuity/`; checkpoints remain
native and contain host conversation state, not a competing action journal.
LangGraph is optional with documented pinned installation commands. Its separate
checkpoint database requires host filesystem protection. CLI/API setup and dashboard show
Done, Remaining, Needs confirmation, Last attempt, and Why it stopped. Resume
means re-run the documented host program; dashboard does not execute host tools.

## AtFlows wire contract and ownership

Canonical product wire version: `atmem.continuity.v1`, owned/versioned here by
AtMem and pinned by SHA-256 in AtFlows Spec 010 before integration tests.
Normal production instrumentation emits explicit opaque workflow/operation/run/
attempt IDs and events. No raw arguments/results/receipts or content hashes in
default telemetry. Authenticated ingestion binds scope to credential; untrusted
raw OTLP attributes alone never confer trusted joins. No inferred old links.
AtFlows owns event deduplication and projections, never recovery decisions.
Events have unique IDs; conflicting duplicate IDs are rejected. Charge identity
is explicit provider ID plus provider namespace, or a declared producer-attempt
ID for an observed single dispatch; no text/timestamp heuristics. Missing prices
or usage remain unknown. Totals show known sum and unknown count, with retry and
recovery overlap counted once. Telemetry outage cannot influence execution.

## Tests and evidence gates

Before product claims: scope/disabled/key-lock/rotation/retention tests, concurrent
attempts, all intent/receipt failure windows, TTL expiry, conflicting args and
stale receipts; installed SDK/example outside both repos; no benchmark imports,
environment/state repair or oracle access. Negative controls must detect forbidden
imports and leaked evaluator data. Then no-fault pinned public retail execution,
external process kills/response barriers and four-arm comparisons. Freeze test
counts and success rules before qualification; preserve all raw results. Keep
existing cumulative USD20 inference ledger; no paid comparison before gates.
Dashboard and documentation explain measured coverage without universal claims.

P001/P101 are P0 tasks. No product schema/implementation begins before read-only
review resolves blocking contract defects. Each later milestone gets code review.

## Review resolutions (normative, supersede ambiguous clauses above)

1. Role matrix: collector/admin create, enable, disable, abandon and grant;
   investigator reads; new `continuity_host` evidence role may begin/report/read
   only an explicitly bound workflow (`EvidenceScope.run_id == workflow_id`).
   It cannot list other workflows, create, enable, delete, grant or read general
   evidence. Host credential is held by trusted integration code, not prompts.
   Existing roles/operations retain prior semantics; add a distinct continuity
   operation rather than granting generic evidence reads to the host role.
2. Create requires caller-provided opaque `workflow_key`. Scoped key + identical
   definition replays create; conflict rejects. Controller returns opaque random
   workflow/operation IDs. The encrypted tombstone retains scoped workflow key
   and opaque workflow ID only, no arguments/hash. It is encrypted with the normal
   vault key hierarchy and survives normal rotation; no content HMAC required.
   A deliberately new workflow key creates new work and requires operator create
   permission; it is not an implicit retry mechanism.
3. Store schema becomes v3 (v1/v2 migrate additively). Older v2 binaries reject
   v3. All semantic fields stay encrypted; serialize read/compare/append using
   BEGIN IMMEDIATE and scan encrypted snapshots in sequence, so no semantic
   plaintext index is required. This local profile accepts linear reads pending
   measured optimization. Deletion removes all workflow snapshots, retains a
   tombstone and deletes unreferenced per-workflow key slots atomically. No claim
   of cryptographic erasure of historical backups. Existing delete_run must
   recognize continuity workflows and retain the barrier. Rotation is covered.
4. Leases last 120 seconds, controller UTC wall clock. Renewal requires current
   token and authorization. Keep rejected late results encrypted as evidence;
   they cannot alter authoritative state. No dispatch follows an expired token
   without a fresh product decision. Clock rollback blocks time-based replay;
   clock jumps do not justify N/Q redispatch. V1 permits no automatic N/Q retry.
5. Idempotency key is minted once per operation and stored before first dispatch;
   it is byte-identical across retries. Require retention > configured total
   tool timeout + 30-second safety margin; replay only when now + timeout + margin
   is before the original retention deadline. Trusted callback enforces timeout
   and key contract; tools unable to guarantee it use query/none. Bind capability
   and timeout in immutable definition. Persist wall time/deadline, never reset.
6. States: pending -> uncertain on execute; uncertain -> completed on validated
   current receipt, or remains uncertain; operator can abandon pending/uncertain
   without declaring success. Enabled/disabled is workflow state. No unknown ->
   pending transition and no "retry" escape hatch. Completed returns saved result;
   abandoned cannot execute. Operator reason is append-only supporting evidence,
   not success. Ready, completed, needs confirmation and abandoned are distinct
   user-visible outcomes. Optional Spec 007 projection remains separately pending
   until implemented; operation authority does not pretend tasks were updated.

Before AtFlows integration, pin a machine-readable wire schema (not prose hash)
with complete field allowlist and enum values in both products. Do not transmit
host credentials or raw results. This is a P101 gate even when AtMem code is ready.

Final clarifications: `continuity_host` grants with no workflow scope are rejected
at grant and use. Operator creates the workflow, then calls existing
`/v1/evidence/grants` with role `continuity_host` and `run_id=workflow_id`; existing
revoke removes access on the next request. A matching unsuperseded token and
run/attempt may record a late receipt after lease expiry, but cannot renew or
dispatch. A superseded token never changes progress. A receipt requires matching
operation ID and a nonempty destination effect ID, retains exact original result,
and is explicitly host-reported, not independent verification. Trusted tool
adapter is responsible for validating destination identity/arguments; it is not
model-supplied approval. Repeated begin always returns blocked, never reissues
execute; SDK does not auto-retry begin HTTP requests. A lost begin response may
therefore require query or operator investigation. V1 is sequential: operation
N+1 cannot start before all preceding operations completed; abandoned work stops
dependent work. UI reports unfinished dependencies separately from done work.
# Dynamic tool-call integration amendment

For ordinary agents that choose tool calls at runtime, add a narrow
`continuity_coordinator` credential. It has continuity authority in its fixed
tenant/subject/workspace scope, but no general evidence read, grant, key rotation
or deletion rights. Unlike `continuity_host` it is not bound to one workflow:
the host integration may create and enable one-operation workflows for the tool
calls it is explicitly configured to govern. This is a host-side credential;
never expose it in model prompts or tool argument schemas.

Ship `GovernedToolRunner` as product integration code, disabled by default. A
trusted application registry declares tools/capabilities/timeouts/retention. The
runner maps a stable host thread namespace + host tool-call ID to a deterministic
opaque workflow key. Argument or tool changes under that identity conflict. It
calls normal AtMem atomic create-and-activate/begin/outcome APIs; it must not implement its
own retry/reconciliation state machine. Enablement requires an explicit host
configuration as well as the credential. Each call is its own operation; the
host (e.g. LangGraph) owns ordering and conversation checkpoints.

This is not a new scheduler and does not turn the benchmark into one. A normal
application can use the same runner without importing evaluation code. The
AtFlows observer remains optional. Tool-call IDs must survive host restart;
regenerating IDs represents new work and cannot promise deduplication.

### Dynamic admission review resolutions (normative)

- Coordinator is bound to an explicit workspace, may create+enable atomically,
  and may inspect/begin/report only its own coordinator-created workflows. It
  cannot list, configure, abandon, grant, delete, or re-enable existing workflows.
  Idempotent create never changes enabled state. Only operators control an
  already-created workflow. Persist creator role/credential identity encrypted.
- Controller binds canonical sorted JSON definitions; JSON booleans and numbers
  are distinct. Model output cannot select capabilities, timeout or retention.
- Runner receives persisted message identity, tool-call identity, thread ID and
  stable application namespace from a synchronously durable host node (never
  Pregel's ephemeral checkpoint_ns). Its v1 key is a
  SHA-256 over a domain-separated JSON array of these identity components and
  a deployment namespace (no argument hashes exposed). No concatenation scheme.
  Arguments are taken from that durable message. Reused call IDs within one
  message are rejected; reuse across distinct persisted messages is distinct work.
- Disabled/retired/missing registry or unresolved outcome raises and halts the
  graph, never a normal model-visible tool error or ungoverned fallthrough. The
  governed node remains installed on resume; changing to an ungoverned graph is
  an explicit unsupported application change, not a recovery mode.
- Process calls from a persisted message sequentially. Host owns dependencies
  between these one-operation workflows. Durable message identity must exist
  before the first tool dispatch; supported invocation requires sync durability.
  Unknown state after a tool callback stops the graph. No model auto-retry.
- Replay/time travel keeps identity and reuses the prior effect. A deliberate
  new lineage/namespace is explicitly new work, never implicit crash recovery.
- Attempts use fresh random IDs, run ID is stable for that host invocation,
  result payload remains encrypted/replayable, callbacks get only the controller's
  original idempotency key and bound timeout. Telemetry excludes host identities.
- Limit each coordinator to 500 unfinished workflows in its authenticated
  workspace. Count latest states, not historical snapshots. Completed/abandoned
  workflows free capacity; deletion tombstones still prohibit identity reuse.
  This bounds outstanding work, not retained history or deployment capacity.
  Amended after the final read-only review: a lifetime cap would prevent normal
  continued use; one coordinator must not consume another's open-work allowance.
- Coordinator admission is exactly one operation per workflow. Limit retained
  canonical workflow/event bytes to 64 MiB per creator/workspace; reads remain
  available at capacity. Operator export/deletion of finished workflows frees
  retained capacity while tombstones preserve non-replay identity. This is not a
  physical disk quota or a bound on administrator-generated/general access logs.
  Admission reserves a final snapshot plus the maximum receipt for each granted
  attempt, including expired unsuperseded leases. Other work cannot consume that
  reservation; finishing the admitted attempt uses it. Actual disk/key failures
  must still surface uncertainty, never permission to repeat. Ordinary snapshot
  writes enforce the 2,000-revision cap with bounded completion/control headroom. Late rejected
  receipts append bounded events only, never full completed-workflow snapshots.
- Charge retained bytes to the workflow's creator, including writes by a bound
  host. Count exact appended canonical records inside the transaction and roll
  back before returning an over-cap authorization. Operator pause/abandon has a
  bounded reserved band; normal dispatch/renew/re-enable preserves room for its
  receipt. No-op pause and repeated abandonment write nothing.
- Coordinator workflow keys are namespaced by coordinator principal, separately
  from operator-created keys. Tombstones retain this encrypted creator binding;
  legacy tombstones without it block reuse conservatively. Renew credentials
  with the same principal ID to continue that principal's work.
