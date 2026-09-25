# Continuity experiment contract v1 (proposed)

Canonical owner: AtMem benchmarking/002. AtFlows spec 010 consumes this contract;
it does not redefine execution authority. Freeze its digest in each run manifest.

## Identity and records

An envelope carries schema_version, experiment_id, trial_id, arm, scope_id,
workflow_id, task_id, logical_operation_id, run_id, attempt_id, producer_id,
producer_epoch, producer_sequence, event_id, event_time and ingest_time. Optional
references: parent_attempt_id, retry_of, task_revision, policy_generation,
context_delivery_id, evidence_ref, trace_id/span_id. State the exact mapping to
existing Spec 007/020 identities before implementation. Unknown links stay null.
Reject cross-scope joins and conflicting duplicate IDs; identical duplicates
are idempotent. Event time alone does not establish cross-process causal order.

Logical operation identity survives crashes and is durably recorded before
dispatch. Attempt identifies one invocation; run identifies a process execution.
Task and run relationships are many-to-many. A benchmark namespace is not an
authorization credential. Only authenticated producers may attach scoped joins.

## External outcomes and destination classes

Observed outcome: unknown / confirmed_succeeded / confirmed_failed, with receipt
reference, observer and assurance. This experiment vocabulary does not extend
AtMem lifecycle enums. A tool's success text is not destination verification.

- I: durable idempotency key, payload binding and declared retention. Test same
  key/different payload rejection and expired-key uncertainty.
- Q: stable unique client reference plus read API; visibility and pending status
  are declared. Retry only after definitive non-commit and no in-flight writer,
  not merely a temporary not-found.
- N: neither capability. Ambiguous commit requires safe block/escalation; no
  universal exactly-once or autonomous-completion claim.

Destination receipts available to agents differ from the hidden evaluator ledger.
The hidden ledger includes commits, payload digest, effect ID, operation ID and
commit sequence. Its API is unreachable by experimental arms.

T002 must verify legal existing state transitions: unknown external outcome does
not mean failed or completed; retain the existing in-progress state, or propose
a supported blocked transition for safe escalation. Confirmed failure can permit
a fresh attempt for the same operation under runtime policy. AtMem alone commits
its task revisions. Unsupported blocker/transition representation is a gap, not
a new enum or an adapter-maintained replacement authority.

## Metrics and denominators

Report task completion = valid final tasks / all eligible scheduled tasks;
duplicate effect rate = extra committed effects / intended logical operations;
wrong effect rate = invalid committed effects / intended logical operations;
forgotten work rate = unjustifiably omitted required operations / required
operations. Separately report pending work behind a valid block, safe-block and
escalation fractions, unsafe retry count, and fault-not-reached fraction.
Primary unnecessary-block rate = unnecessary blocked logical operations /
intended logical operations in the task, with that denominator fixed by the
workload oracle before arm execution. Count each blocked operation once. Tasks
with zero intended operations are excluded at G0 for all arms. Also report the
descriptive ratio unnecessary blocks / all blocks (undefined if no blocks): oracle
must establish that definitive safe resolution was available through that arm's
public I/Q interface at the time, not merely known to the hidden ledger.
That public-evidence rule defines unnecessary blocking for both metrics. The
primary blocked numerator counts only distinct operations mapped to the intended
set; unmapped blocks are reported separately. The same pre-execution intended
operation count denominates duplicate, wrong-effect and unnecessary-block rates.
Duplicate/wrong numerators retain every bad effect, including unrequested effects;
these are effects-per-intended-operation rates and can exceed one. Publish mapped
and unmapped counts separately rather than hiding rogue actions. The G0 zero-write
exclusion applies to this first write-workflow cohort; report excluded task IDs
and limit completion claims to that cohort, not the entire upstream domain.
Report all scheduled trials, including infrastructure failures, and additionally
conditional results for reached barriers; no hidden denominator filtering.

Context violations / delivered context items includes stale, superseded and
unauthorized items independently; report delivery coverage to prevent a zero
delivery strategy scoring as useful. Evidence coverage = reconstructable required
boundaries / required observed boundaries; classify missing and conflicting data.
Report workflow/task validity against upstream assertions as well as our oracle.

Latency: no-fault end-to-end, restart-to-terminal (completed or blocked reported
separately), and total including downtime, p50/p95. Resource usage: CPU, peak RSS,
storage, model/tool calls and tokens. Independent call/usage ledger is the cost
oracle; unavailable real provider bills are explicitly unavailable, not invented.

Each charge has an immutable charge_id, operation/attempt references, usage,
currency, price source/version/time, estimated amount or unknown reason. Retry
and recovery are overlapping tags: summed total deduplicates charge_id. Missing
usage/prices are unknown, not zero. Repeated work is not automatically waste;
only oracle-proven redundant actions support that label. Compare AtFlows observed
coverage and totals to the independent ledger, including loss and duplication.
The harness assigns charge IDs before dispatch; propagate where public interfaces
support it and record unsupported correlations. Provider-internal unobservable
retries remain a coverage limitation. Report known subtotal plus unknown count,
never a complete total when charges are missing. User-simulator charges are
separate from agent execution but included in total experiment spend.

## Preregistration and comparison

Pin runtime/product/wheel/source hashes, upstream workload/license, environment,
profiles, policy schedule, model snapshot, prompts, seeds, fault schedule,
destination configuration and this contract digest. Pair arms by task/fault seed,
randomize run order, isolate/reset destination per trial, and prevent cross-arm
memory reuse. Shared baseline and workload tooling receives equal fixes in all
arms, with frozen pre-fix data retained. Product-specific adapter changes are
reported as a separate experimental configuration.

G0 maps write-class tools to effects. Fault target is the k-th write-class call
at barrier b, selected by recorded seed; pairing is (task, repetition, k, b), not
wall-clock time. Report actual operation/tool identity because trajectories may
diverge: ordinal pairing is not a claim of identical actions. An unreachable
target is fault_not_reached, retained in scheduled-trial results. Simulator state
survives the worker crash; initial simulator configuration/seeds are matched,
but responses can diverge with agent conversation. Never force an invalid shared
transcript. Record residual provider nondeterminism.

After pilot variance estimates, freeze sample counts, task families, bootstrap
task-cluster confidence intervals, non-inferiority margins for safety/completion,
minimum useful overhead/quality effects, and stopping rules. No tuning on held-out
tasks; resource exhaustion is a reported incomplete study, not selective stopping.
Do not select a winner by completion alone or by blocking alone. Report a frontier
of completion, safety, context integrity and overhead; null results are valid.

Primary AtMem comparison: runtime+AtMem versus runtime. Primary benefit endpoints
are duplicate+wrong effects and unnecessary blocking; completion and safety are
non-inferiority gates. Freeze margins and a Holm-corrected testing family before
held-out runs; other metrics/cells are descriptive unless preregistered. AtFlows
primary endpoints are coverage, accounting accuracy and overhead in a separately
declared corrected family. Outcome comparisons to matching non-AtFlows arms are
non-interference checks, not attributed execution gains. Resource-induced outcome
changes are reported as regressions/uncertainty, not assumed impossible.

Frozen G2 product artifacts run in G5 alongside any preregistered changed arms.
Amendments must precede held-out execution; subsequent tuning needs a new held-out
split/study. All results carry smoke/engineering/production-scoped labels.
