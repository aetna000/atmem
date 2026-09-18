# Homa-inspired dispatcher review and frozen experiment

Date: 2026-09-18. Research branch only; no production code or deployment change.

## Findings on the first prototype

1. Every-fifth-job selection reserves a count, not service time. Cheap artifacts
   can repeatedly outrank an older expensive write even during the bulk slot.
2. Unique earliest deadlines dominate the size tiebreak. The old workload's
   identical relative deadlines effectively order recalls FIFO.
3. Whole database operations cannot be preempted like network packets. More
   queue logic cannot eliminate the service time of an already-running write.
4. Different executors for FIFO and candidate confound the comparison.
5. Expected-phrase presence is weaker than byte-exact output agreement.
6. Tiny fixed operation cycles and noisy short trials cannot establish a
   broadly beneficial policy. Bulk throughput and tail latency are distinct.

## Primary-source research

- [Homa protocol, FIFO scheduling](https://github.com/PlatformLab/HomaModule/blob/main/protocol.md):
  SRPT is paired with reserved service for the oldest message at receiver grants
  and sender pacing. Incoming bytes and NIC queues are also controlled.
- [Homa draft, FIFO grants](https://github.com/johnousterhout/homa-rfc/blob/main/draft-ousterhout-tsvwg-homa-00.md):
  describes a roughly 5% oldest-message bandwidth safeguard. This motivates an
  experiment; it does not establish an appropriate database service fraction.
- [Homa/Linux, ATC 2021](https://www.usenix.org/system/files/atc21-ousterhout.pdf):
  packet scheduling/receiver flow control and software overhead both matter.
  Its measurements cannot be transferred to a Python/SQLite queue.
- [Shreedhar and Varghese, DRR](https://web.stanford.edu/class/ee384x/EE384X/papers/DRR.pdf):
  deficit accounting addresses variable service sizes, unlike job-count shares.
- [pFabric, SIGCOMM 2013](https://people.csail.mit.edu/alizadeh/papers/pfabric-sigcomm13.pdf):
  rank-based size scheduling motivates a baseline; it does not supply our
  missing application transaction/preemption boundaries.
- [Aequitas](https://research.google/pubs/aequitas-admission-control-for-latency-critical-rpcs-in-datacenters/):
  reinforces measuring admission behavior alongside latency under overload.

The implementable analogy is shortest **estimated service** plus a measured
service-time safeguard for oldest work. Message bytes and database cost are
separate quantities. This remains non-preemptible shortest-job ordering, not
an implementation of Homa or true SRPT.

The [current receiver implementation](https://github.com/PlatformLab/HomaModule/blob/main/homa_grant.c)
adds two useful details: `homa_grant_check_fifo` schedules limited grant
increments at intervals derived from link bandwidth and the FIFO fraction;
`homa_grant_find_oldest` skips fully granted or unresponsive messages that have
already accumulated excessive outstanding grants. A CPU/storage analogue needs
bounded work grants and cancellation/fencing; repeatedly selecting a hung
atomic database operation cannot supply equivalent progress guarantees. These
mechanisms belong at safe work boundaries, not inside arbitrary SQL transactions.

## Claude consultation loop

Claude CLI ran read-only: first with tools disabled over a supplied design,
then with only Read enabled over the actual implementation. No shell, editing
or MCP tools were available to the reviewer. It did not execute tests.

Accepted: shared dispatcher; A/A noise measurements; open-loop admission and
complete refusal accounting; past-only per-kind/size estimates; exact context
oracle; independently scoped writes; explicit service debt; executable paired
analysis; write/artifact guardrails individually; source-manifest checks;
best-effort git identity; stage residuals; complete calibration requirement.

Not accepted literally:

- Refusals are terminal refusals, never censored work or fabricated horizon
  latencies. The all-offered completion bound and outcome gates expose them.
- A smaller negative-debt cap forgives overservice and favors oldest work; it
  does not cause the underservice alleged in the first critique. Its bounded
  credit inheritance across successive oldest jobs is tested/disclosed.
- Vector sync here occurs synchronously during close. The reviewer initially
  assumed it was asynchronous; source inspection contradicts that assumption.
- Artifact jobs already perform encrypted durable evidence/artifact writes.
  Opening an unrelated Memory handle would introduce artificial work. Their
  distinct service and per-kind metrics remain visible.

## Candidate and comparison contract

`scheduling.py` implements FIFO, legacy, shortest-estimated-service with a 5%
oldest-service debt, and a secondary fixed 40% bulk-service debt variant.
Actual service seconds are charged, including mandatory evidence capture.
Overservice credit is capped at 5 ms; classes do not bank idle credit. A new
oldest job can inherit at most 5 ms of old credit, equivalent to 100 ms of
other service at a 5% accrual rate, plus atomic-task blocking. These are service
accounting statements, not unconditional wall-time bounds.

`homa_experiment.py` uses one common bounded dispatcher with one worker for all
policies, warmed read fixtures, disjoint read/write subjects in the same store,
full encrypted evidence and recovered text/media checks. Read results must
match a precomputed oracle over the unchanged read corpus. All offered work,
errors, refusals, generator lag, and atomic operation stages are reported.
Input-byte admission caps exclude already loaded fixtures and temporary
encryption/base64 copies; they are not total-process memory limits.

`run_fairness_suite.py` freezes one calibration, priors, offered rates, seeds,
source digests, policy settings and randomized order before held-out execution.
Five held-out seeds cover three mixes and low/high offered load. Ten same-FIFO
trials measure A/A noise. `analyze_fairness.py` evaluates paired ratios and
10000 seed-bootstrap draws, with per-kind bulk non-regression/outcome gates.
Five-seed intervals remain descriptive pilot uncertainty. No retuning is
allowed on these held-out results. The 40% bulk share is a fixed secondary
ablation, not a workload-matched optimum.

No claim of authorization-at-release, actual host delivery, safe reorder of
dependent reads/writes, hard deadline enforcement or production fairness is
made. P1 and integrated P2/P3 gates remain open.

## Adversarial mechanism check

In a deterministic simulation with one old 50 ms write and a continuing stream
of 500 one-ms bulk tasks, the legacy dispatcher starts the old write at 500 ms.
The oldest-service safeguard starts it at 1 ms; FIFO starts it at 0 ms. All
policies complete 501 tasks in the same 550 ms total service time. This exposes
and fixes that starvation pattern in the model; it is not product throughput.

## New measured results

Frozen suite: `research/memory_fabric/results/homa-fairness-v2/manifest.json`.
Raw files and executable summary are in that directory. The v1 directory has
only a draft calibration/manifest created before review corrections; no v1
held-out policy measurements were run. No evaluated policy was retuned.

Seventy measured trials offered **11,200** operations; **11,186 completed**, 14
were refused at the bounded queue, and there were **zero worker errors**. All
11,186 captured envelopes reconstructed successfully, including 679 exact
media recoveries. Four trials failed the preregistered 25 ms p99 generator-lag
gate; they remain in the dataset and cannot support comparative claims.

The controlled low-load mixed scenario had no refusals, worker errors, read
oracle mismatches or invalid generator trials. Each row below aggregates five
paired trials (800 offered operations per policy); values are medians of the
per-trial metrics, not pooled-request percentiles.

| Policy | Recall p95 | Bulk mean completion | Completion |
|---|---:|---:|---:|
| AtMem with common FIFO dispatcher | 124.5 ms | 51.3 ms | 800/800 |
| Shortest estimated service + 5% oldest safeguard | 198.1 ms | 80.0 ms | 800/800 |
| Same, plus fixed 40% bulk-service reservation | 126.1 ms | 53.6 ms | 800/800 |

Neither candidate passes the frozen acceptance criteria. Across five paired
seeds, the low-load recall ratio's descriptive bootstrap interval spans
0.827–1.849 for the oldest-service candidate and 0.810–1.235 for the bulk-share
candidate. The A/A FIFO ratio interval itself is 0.787–1.145. These short local
trials do not demonstrate an improvement or a precise regression magnitude.

All scenarios, raw geometric means of paired ratios (below 1 is better for
latency, above 1 better for throughput), retained even when invalidated:

| Scenario | Candidate | Recall p95 ratio | Bulk mean ratio | Bulk throughput ratio | Interpretation |
|---|---|---:|---:|---:|---|
| Mixed, low load | oldest safeguard | 1.250 | 1.076 | 0.994 | No demonstrated gain |
| Mixed, low load | bulk-share ablation | 1.011 | 0.857 | 1.001 | No demonstrated gain |
| Mixed, high load | oldest safeguard | 1.420 | 1.576 | 0.985 | One paired FIFO trial fails lag gate |
| Mixed, high load | bulk-share ablation | 1.439 | 0.561 | 0.984 | Bulk/recall tradeoff; lag gate failure |
| Write-heavy | oldest safeguard | 0.377 | 1.326 | 1.010 | Oracle assumption invalid; extra refusal |
| Write-heavy | bulk-share ablation | 1.000 | 1.166 | 0.999 | Oracle assumption invalid; lag gate failure |
| Interactive-heavy | oldest safeguard | 1.013 | 0.921 | 1.013 | Paired lag failures; no reliable gain |
| Interactive-heavy | bulk-share ablation | 1.020 | 0.329 | 1.041 | Paired lag failures; no reliable gain |

The ratio of medians and the geometric mean of paired ratios are different
statistics; do not derive one table from the other or advertise either without
the sample counts, intervals and validity notes.

### Read-oracle failure and diagnostic

248 recalled blocks in write-heavy trials differed from the pre-run oracle,
including FIFO results. The diagnostic in
`research/memory_fabric/diagnose_recall_drift.py` reproduced the cause without
any scheduler: insert 70 unrelated-subject records into the same FTS corpus,
and a query's context changes from the expected fact alone to that fact plus
two additional same-subject facts, while its subject generation stays at 40.
SQLite BM25 statistics use the shared corpus; filtering returned rows by subject
does not isolate those statistics. A stable subject is therefore insufficient
to guarantee a stable retrieval snapshot. This is not evidence of cross-subject
content disclosure, and a digest mismatch alone does not measure relevance loss.

The raw reproduction, including synthetic before/after contexts, is
`results/cross-subject-ranking-diagnostic.json`. Write-heavy timings must not
support a quality-preserving speedup claim. Future exact parity tests need
snapshot-equivalent full ranking state, or an offline reference replay of each
actual read snapshot. Do not weaken the check back to substring matching.

### Where service time went

Across FIFO evaluation runs, measured service totaled 104.97 seconds:
54.43 s protected evidence capture (51.9%), 19.81 s operation execution (18.9%),
16.67 s Memory opening (15.9%), 14.03 s close/vector sync (13.4%), and a small
unattributed remainder. These are composite measured stages; evidence capture
includes storage and encryption, not pure cryptographic CPU time.
Forced oldest-debt dispatches consumed about 10.1% of candidate service, despite
a nominal 5% accrual fraction: whole atomic operations overshoot the share.

### Recommendation

Keep FIFO as the default. Retain the oldest-service mechanism as a research
anti-starvation primitive, but do not ship either tested policy as a speedup.
Next study bounded, independently safe work units for large artifact/index
tasks, with one canonical commit/release boundary and retained evidence. A
batch can yield only after its current atomic unit has completed; never insert
preemption inside a transaction or release stale authorized data. Profile
evidence/store setup reuse separately: reducing mandatory service overhead can
benefit both classes, whereas reordering alone usually trades their wait times.
These follow-ups require new manifests and fresh evaluation seeds, not tuning
against this completed held-out suite.

Final Claude source review: no blocking flaw identified for an exploratory
atomic-operation benchmark. Remaining cautions: the artifact lane has few
samples; five seeds weakly estimate a tight 5% non-regression bound; A/A noise
must constrain interpretation; policy values should be checked against the
manifest; a sealed analyzer is inconvenient to fix later. Evaluation had
started by receipt of this review, so no bound, workload, sample count, code or
policy is changed to improve acceptance. Parameter equality will be checked
read-only. A negative or inconclusive result is retained. Reviewer agreement
is not a statistical or governance proof.

Validation: 61 focused protocol/runner/scheduler tests passed, including bounded
admission/refusal accounting and missing-throughput analysis. All measured
policy settings were independently checked equal to their frozen manifest.
The full research source is archived beside the reports; a post-run source
supplement records files such as `protocol.py` that were not in the initial
source seal. No production files or running services were modified.
