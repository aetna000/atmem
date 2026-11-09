# Implementation plan — Spec 050

Status: implementation started; see `implementation-evidence.md` for completed
work, the tested host-boundary fix and remaining integration. Governing requirements: `spec.md`; source
review: `research.md`. The implementation remains opt-in and is not released.

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
7. **Enforce/monitor:** the Hermes hook checks the specific pending invocation; a real
   blocked-call receipt differs from a would-block observation. Compare regressions,
   suspend/revoke and collect a new outcome without automatic promotion or retraining.

This is a governed feedback loop, not a second memory database and not a training
service. Built-in `atmem/invariants/` continues to verify product guarantees; runtime
user policies live in a separate explicit namespace and cannot change those guarantees.

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

Hermes is the first enforcement surface because it already has a concrete before-tool
plugin. Pin the supported Hermes version and installed artifact in conformance evidence
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
2. Encrypted outcome chain, independent verification, diagnosis and per-agent reporting.
3. Versioned profile qualification and review; shadow-only until statistical gates pass.
4. Typed rules plus Hermes enforcement, explicit activation, revocation and recovery.
5. Consented example export, dashboard/CLI parity, cross-platform installed-artifact gates.
6. Review evidence and choose release scope. No training, promotion or publication is
   automatic. A failed gate stops the affected activation, not useful offline diagnosis.

## Verification and release

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
