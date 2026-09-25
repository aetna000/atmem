# Agent continuity implementation milestone reviews — 2026-09-25

## Product implementation reviews (P1–P3)

Reviewer: Claude Opus 5.5 CLI, read-only supplied source, no tools, hooks disabled.
These are static reviews, not independent execution or unconditional sign-off.

- P1: corrected hashed lease-token disclosure, exact run/attempt binding,
  capture-mode transitions and read-only polling growth. Follow-up found no
  blockers for the bounded profile subject to a real two-process race gate;
  that test passes with one execute decision and one blocked decision.
- P2: reject unexpected controller actions; require bounded JSON receipts with
  original results; preflight document size; do not let logout errors conceal a
  minted credential. Observer delivery now has a wall-clock bound. Query-only
  publisher intentionally does not reinterpret an execute conflict as success.
- Dynamic host: require actual synchronous, file-backed LangGraph checkpoints;
  persist assistant identity before dispatch; reject non-assistant tool messages;
  use application namespace rather than ephemeral Pregel task identity; propagate
  uncertainty as a graph-stopping exception. Checkpoint replay and partial-batch
  tests pass on LangGraph 1.1.5 and 1.2.12. Semantic re-requests with new identities
  are explicitly new work, not covered by invocation deduplication.
- Final product review identified a lifetime 500-call limit. Corrected it to
  latest unfinished workflows per creator/workspace; completed work frees
  capacity without releasing its replay identity. Regression covers this.
- P3: corrected partial-price accounting and cross-attempt charge binding,
  added scoped lookup indexes, bounded ingest body, precise HTTP error classes,
  stale-view clearing and six-decimal dollar display. Outer HTTP dispatcher
  already enforces investigator reads: installed HTTP test verifies cookie/
  bearer separation, viewer denial and pending-password denial (21 assertions).
- AtFlows standalone observer added with four Python tests: linked usage,
  application exception propagation, no execution change during outage, and no
  semaphore leak on rejected JSON. Static follow-up review remains recorded
  separately when complete.

Validation so far: 713 existing task/evidence tests, 53 control-plane tests;
27 continuity tests before the latest capacity regression, then 22 service/
integration tests including that regression. No paid inference in this phase.
Installed direct publisher survived both receipt crash windows; installed
LangGraph qualification and final artifact hashes are separate evidence gates.

### Final follow-ups

- AtFlows observer: applied proxy isolation, hostname/acknowledgement validation,
  cumulative error count and documented bounded-wait/global-slot semantics.
  Claude's follow-up: no hard blockers for the documented best-effort observer.
  Declined the earlier claim that lost AtFlows events consume AtMem capacity:
  these are separate stores; telemetry never controls AtMem authority.
  Six standalone tests now include actual HTTP proxy/redirect/acknowledgement
  checks. Existing OTLP integration passes 26 checks on the isolated server.
- Workload graph: Claude found no recovery compensation or concrete blocker.
  Added reply-count/identity assertions. Declined returning uncertainty as an
  ordinary ToolMessage: shipped product intentionally stops the graph to prevent
  a model's fresh-ID repeat. This is a visible product difference in faulted runs.
  Host message UUID is ordinary checkpointed identity, identical across arms,
  not semantic deduplication or an evaluator recovery journal.
- Authority availability follow-ups: enforce retained history capacity against
  creator even for bound-host writes; exact transaction accounting; bounded
  late events rather than full snapshots; reserve receipt/operator-stop revision
  capacity; isolate coordinator keys from operator keys. Tests also verify
  deletion physically frees retained history and leaves the replay tombstone.
  Final source review continues after these corrections; do not infer approval
  of changed source from an earlier verdict.

- Final byte-reservation review: Claude found no blocker in the arithmetic,
  conditional on append ordering and globally unique workflow IDs. Verified
  `EvidenceStore.documents()` orders by sealed-object sequence and creation
  generates UUID4 workflow IDs (workflow keys, not IDs, are principal-namespaced).
  The new competing-admission/max-receipt test passes; product/HTTP/integration
  suite is 33 passed. The installed build-004 gate caught an incorrect rig CLI
  invocation (`python -m atmem`); corrected to the shipped `atmem.cli` entrypoint.
  Failed build-004 attempts are not counted as acceptance passes.

## P0 product-first correction review

### Inert public retail and fresh-pilot follow-ups

- Public four-arm no-fault replay now checks all loaded evidence against its
  checksum manifest, exact model options, identical graph topology and six real
  governed operations in each AtMem arm. The evaluator uses its own credential;
  a coordinator's attempted global listing was correctly denied403. Corrected
  run007 passes18native requests and6tools in each arm.
- External receipt-loss review: added explicit native successful-store-change
  gate, SIGKILL/topology checks independent of Python assertions, serialized
  tool-response counter, source-change guard and installed/cassette provenance.
  Run003 independently observes one repeated request for baseline/AtFlows and
  zero for AtMem/both; native store changes after restart are zero in every arm.
  This demonstrates request protection, not duplicate exchanges or completion.
- Fresh no-fault paid-pilot review: retained separate registration and cumulative
  ledger; no broker/recovery feature introduced. Verify installed file hashes,
  preserve completed conversations if grading fails, explicit role labels and
  comparison eligibility, source-integrity result rather than dropped summary,
  sanitized failure frames, loopback observation and immutable public prompts.
  Declined exporting raw exception text (credential risk) and reserving240
  full-context calls upfront (outside authorized budget). Registered partial-
  schedule limitations instead; each dispatched call still reservesUSD2.20.
- Final transport follow-up: Claude reports conditions resolved, no new blocking
  issues for the attached bounded-pilot source. Confirmed caller has one transport
  per arm shared by all roles and one cumulative ledger. Exact model and explicit
  default tier are now checked before settlement; missing/changed tier retains
  full unknown reserve. Timeout wording corrected to socket/idle, not a hard
  wall-clock guarantee. Transport/budget/native tests31pass,1opt-in skip.

Published-artifact compatibility: AtMem2.3.6 creates actual schema2 evidence;
build005 preserves it, keeps schema2 on normal open, upgrades only on first
continuity use and makes the old reader explicitly refuse schema3. Product gates:
60pass/1platform skip; existing task/evidence713pass; AtFlows23Bun tests328assertions,
6installed SDK tests,21installed HTTP assertions, TypeScript passes. These are
functional/compatibility evidence, not production workload success rates.

Owner explicitly requires product features before benchmark evaluation; the rig
cannot supply recovery. Claude reviewed the correction and AtFlows plan with
`--tools '' --strict-mcp-config --no-session-persistence` and hooks disabled.
Review was text-only, not independent source execution. Verdict: ready for P0
detailed contracts, not P1 implementation. Findings: shared identity ownership,
telemetry disclosure, authority during outages, external fault injection, named
host/migration gates, audited human resolution, charge deduplication and concrete
isolation checks. These are now mandatory P0 exit gates in
`product-first-correction.md`; none is marked implemented.

One recommendation was adjusted: AtMem need not mint every host run/attempt ID;
host-neutral contracts permit host-issued IDs with authenticated scoped binding.
AtFlows cannot invent or infer those joins. Earlier reviews below cover historical
fixture milestones only and do not approve product continuity features.

Follow-up text-only Claude review: **conditional approval to proceed to detailed
contracts**. Additional P0 exit requirements recorded: task/phase timing, declared
tool capabilities, stale-worker fencing, unavailable evidence keys, retention/
deletion semantics, qualification criteria/budget allocation and cross-repo
contract version ownership. These block P0 exit, not contract drafting. No product
implementation approval/completion is inferred from this review.

Canonical record for AtMem benchmarking/002 and AtFlows Spec 010. Existing
planning/first-foundation reviews remain separate historical records.

## Review boundary

Claude CLI 2.1.281, model `claude-opus-5-5`, received the relevant source/tests or
plan diffs on stdin. Every call used `--tools '' --setting-sources ''
--strict-mcp-config --mcp-config '{"mcpServers":{}}' --no-session-persistence`.
Final retail follow-ups used `--effort medium`. Claude had no repository tools,
write access or independent test execution; approvals are reviews of supplied
source. Tests were executed separately by the implementation agent. No provider
keys, environment-file contents, private Home or held-out reference actions were
sent. These reviews are not performance evidence or independent reproduction.

## Planning alignment

Verdict: approve bounded M1/M2 after safeguards. Applied requirements:

- Preserve baseline production code; the non-exported OTLP handler is tested by
  starting the unmodified server, not by adding an export or a replacement route.
- Strip provider credentials/dotenv; enforce offline tripwires; label their limits.
- AtFlows T002a precedes consumer T007a; canonical review record lives here.
- Separate offline tool parity from autonomous agent no-fault equivalence.
- Keep paid runs and held-out evaluation behind their existing gates.

One suggested auth correction was rejected after source inspection:
`apps/server/src/server.ts` routes `/v1/traces` through an Origin check to
`handleOtlpRoute` without dashboard login. The tested no-Origin request succeeds
without credentials. Dashboard/API authentication is real but is a separate route;
we do not claim the entire product is unauthenticated.

## M1 — pinned native retail tool process

First code verdict: not approved. Fixed unchecked bytecode/import shadowing,
expanded audited network/process events, bounded JSON IPC in place of pickle,
requestor validation, cleanup and provenance. Added planted bytecode, untracked
module, shadow, symlink, network and subprocess regression tests.

One follow-up CLI call stalled for roughly ten minutes and was terminated; no
approval is attributed to it. Subsequent review found the local Git object tree
needed an independent anchor. Added `retail-source-lock.json` without altering
the historical protocol lock/results. Upstream `git --no-replace-objects fsck
--full --no-reflogs` passed and no replace refs were present; `ls-tree` disables
replace objects and the resulting SHA-256 tree/policy/tools stamp must match the
AtMem-owned lock. An independent-pin mismatch test fails closed. Journal calls,
responses and state hashes are cross-checked. Upstream dependency constraints
are enforced before replay; temporary-environment LiteLLM/psutil mismatches were
corrected before final evidence generation.

Final verdict: **APPROVE for bounded M1 offline tool parity**. Remaining scope:
pilot reference actions are evaluator plumbing, not agent decisions; Python
audit hooks are tripwires rather than a hostile/native-code sandbox; concurrent
malicious source swap-and-restore is out of scope. No full task-family parity,
simulator recovery, production correctness or upstream score is claimed.

The final compatibility-only import uses `tomli` on Python 3.10; upstream execution
still requires its declared Python 3.12–3.13 range. CI configuration supplies the
pinned checkout, but no remote CI result is claimed for these unpushed changes.

## M2 — unmodified AtFlows HTTP observation

Initial verdict: approve after fixing output draining, home fallback isolation
and over-broad guard/pricing labels. Applied changes:

- Drain stdout/stderr through shutdown; handle signals and terminate only owned
  processes. Python's timeout terminates its owned process group.
- Use explicit fixture data/database/instance paths; deny `os.homedir()` fallback.
  No HOME or CODEX_HOME variable is repurposed. Integration setup APIs are not called.
- Report guarded attempts detected, exact covered vectors and non-sandbox limits.
  Unknown costs stay evaluator-unknown; raw product zero values are retained.
- Scope provenance to tracked source, include Bun version and lockfile, and state
  that installed node_modules bytes are not independently hashed.
- Keep dropped spans in the denominator; name attribute comparisons accurately;
  hash the nested raw observations as well as the public report.

Final verdict: **APPROVE for bounded M2 HTTP fixtures**. Non-blocking follow-ups:
broader ESM/Bun-native guard coverage, explicit guard-loaded sentinel and improved
sanitized failure diagnostics. These limits do not become production promises.

## Progression rule

### Cross-artifact closeout

Claude requested four final consistency corrections: explicitly disclose that the
tomli fallback's Python 3.10 collection path was not run; use guarded-path tripwire
wording rather than imply complete egress isolation; carry the newly approved model
into plan/tasks while leaving spend/prompts/limits unlocked; and label OS temporary
files as non-durable. All four are applied. The existing AtMem dependency already
declares tomli for Python <3.11. Final 117-test validation was on Python 3.12.2.
Claude's closeout verdict was **approve after those corrections, without requiring
another full review**. The actual workflow filename matches its path filter, and
AtMem-only CI's missing cross-repository probe environment is explicitly disclosed.

### Remaining gates

M1/M2 close only their named substeps. T001/T005/T007, G2 and G5 remain open.
Next: full agent/user-simulator orchestration and its persistence/authority/cost
boundaries, then the current-product four-arm pilot. Models, prompts, explicit
egress and spend limits must be agreed and frozen before paid benchmark execution.
Each later implementation milestone needs another read-only review and tests.

Validation and public fixture artifacts:
[milestone report](../../../benchmarks/agent_continuity/reports/milestones-20260925.md).

## M3a — independent spend and export ledger

User subsequently approved USD20 total benchmark inference spend and requested
retained raw results for reporting/articles. Added `pilot-authorization.json`
without changing the historical protocol/split locks. Claude read-only verdict:
**approve bounded M3a**, no concurrency/restart blockers. Applied atomic schema
transaction recommendation. Unknown settlements intentionally retain the whole
reservation permanently; later billing reconciliation is not implemented. Tests
cover serial/concurrent reservations, duplicate dispatch/settlement, restart,
cap mismatch, unknown usage, overrun latch, cross-role total and export hashes.
This is accounting metadata, not an AtMem evidence-store implementation.

## M3b — one native no-fault public task

Initial Claude verdict: **not ready for execute**. Corrected pre-spend basis/model
validation, added full fake-sender native rehearsal, latched transport failures,
and retained sanitized HTTP status/request ID/error classification/body digests.
Raw error/malformed response bodies are explicitly omitted because they may echo
credentials. Raw successful public-corpus responses remain retained.

Source inspection confirms task 0 reward basis is DB plus NL_ASSERTION, but its NL
list is empty. The offline rehearsal plants an assertion only in its fixture to
exercise all three paid roles; this fixture is not benchmark performance evidence.
Runtime source/task data are not changed. Rehearsal verifies a completed
conversation with failed task reward zero. A no-provider dry run passed.

Final Claude static verdict: **approve exactly one task-0 paid native pilot** after
green spend/transport/native-rehearsal/retail tests. Failure means stop/review, no
automatic rerun. Applied non-blocking role reset and independent accounting export
cleanup improvements. No AtMem/AtFlows comparison or official upstream score is
approved or claimed. Follow-up gates remain open. Provider invoices are not
independently verified. Every later milestone still requires read-only review.

Execution record: final pre-spend suites passed **40 tests** (none skipped), then
one task-0 run dispatched 18 model calls. Normal user-stop termination, native DB
reward zero, no actual NL assertions, estimated USD0.057324 total and no unknown
reservations. All 63 run-artifact checksums verified. No replacement trial was
run. See `benchmarks/agent_continuity/reports/native-pilot-20260925.md` for the
observed simulator preference deviation, raw evidence and remaining gates.

Post-run Claude report review: **no blockers**; arithmetic and claim boundaries
consistent with supplied facts, not independently reproduced. Applied requested
clarity on who verified hashes, accounting export filename, price-check date and
the unused error-body policy. Did not adopt the suggestion that simulator drift
necessarily penalizes all arms equally: diverging conversations can differ in
simulator adherence, which should be annotated without post-hoc trial exclusion.
# Live broker and current interruption regression — 2026-09-25

Claude CLI read-only review identified itself as Opus 5.5 (`claude-opus-5-5`).
After corrections it reported no blocker in live_broker/live_transport: broker
exit drains charged calls; waiting requests cannot dispatch after closing;
worker disconnect cannot refund usage; there is no response cache or recovery.
Its remaining drain-test recommendation was implemented. The focused broker,
transport, spending, product-boundary and observation-metric suite passes 45 tests.

Installed-wheel recorded fault rerun005 passes all four measured boundaries:
baseline/AtFlows each make one rejected repeat, AtMem/both stop before dispatch,
all have zero further store changes. Actual restart waits exceed 125 seconds.
Raw bundle: `results/public-retail-fault-20260925-005`. Attempt004 failed package
metadata isolation before trials; it is retained and not counted as passing.

Fresh no-fault paid pilot001 remains immutable: native task rewards 1/0/0/0,
all normal terminations, total estimated new cost $0.226608; cumulative $0.283932.
These mixed single-task outcomes are not a product improvement claim.

The new `retail_live_fault.py` is **draft, not paid-qualified**. A requested
read-only pre-spend Claude review stopped with session-limit exhaustion, reset
advertised for 14:30 Australia/Sydney. No review approval is inferred. No fresh
fault or held-out calls were dispatched. P006–P008 remain open; the next gate is
that review, corrections and independent boundary validation before spending.
