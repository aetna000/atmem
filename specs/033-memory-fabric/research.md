# Research basis and decisions

Date: 2026-09-18. Status: initial primary-source survey and exploratory local
baseline, not a completed novelty review or a scheduler performance claim.

## Related work and limits

| Work | Established direction | Consequence for this project |
|---|---|---|
| [Homa, SIGCOMM 2018](https://arxiv.org/abs/1803.09615) | Receiver-driven transport priorities and short-message tail latency. | Borrow resource/admission ideas; do not claim Homa implementation or its transport results. |
| [Homa/Linux, ATC 2021](https://www.usenix.org/conference/atc21/presentation/ousterhout) | Kernel implementation and measured software-stack bottlenecks. | Instrument real bottlenecks before attributing gains to network scheduling. |
| [Shenango, NSDI 2019](https://www.usenix.org/conference/nsdi19/presentation/ousterhout) | Fine-grained CPU reallocation across latency-sensitive and batch work. | Fair service and useful batch throughput are existing systems concerns, not new inventions here. |
| [Caladan, OSDI 2020](https://www.usenix.org/conference/osdi20/presentation/fried) | Interference-aware CPU scheduling and dynamic resource allocation. | Static isolation is a baseline, not an assumed optimal solution; measure interference explicitly. |
| [Zanzibar, ATC 2019](https://www.usenix.org/conference/atc19/presentation/pang) | Authorization consistency amid ACL and content changes. | Revocation ordering is established work. The paper must compare semantics, not claim novel authorization solely from generation checks. |

These are publication-page/abstract-level checks, not full-paper reproductions.
Read full papers and examine further deadline scheduling, cancellation, admission
control and revocation literature before a novelty claim. The plausible AtMem
contribution is an evaluated combination in governed agent-memory delivery, not
priority queues, credits, epochs or access checks in isolation.

## Repository grounding

- `docs/current-status.md` documents 2.3.3 as local and single-writer, not
  multi-primary replication. No assumption that this experiment changes that.
- `atmem/control/manager.py:prepare` resolves mode/scope and delegated context;
  a scheduling layer must not widen authority or bypass its failure handling.
- `atmem/delegated/service.py:prepare` binds and verifies provider results.
  Scheduling must respect provider deadlines and exact-result contracts.
- `atmem/telemetry/retrieval.py` has per-stage profiling helpers, not a full
  queue/storage-contention measurement system.
- `pyproject.toml` packages only `atmem*`; standalone `research/` infrastructure
  does not alter the installed runtime package.
- `.specify/memory/constitution.md` requires authority, full-fidelity protected
  evidence, exact host claims and executable guarantees. No stale requirement in
  another spec grants permission to weaken these boundaries.

## Design decisions

1. Keep baseline retrieval strategy and bytes unchanged. Quality is a gate, not
   a knob to trade away for an apparent speedup.
2. Treat runtime authorization/evidence checks as required workload, not an
   optional overhead disabled in the winning configuration.
3. Distinguish withholding (correct refusal) from useful context delivered. A
   scheduler cannot win merely by expiring more work.
4. Keep deterministic policy outside AtBot. Advice can be studied later with an
   explicit operator path and rollback; it is not needed for P0.
5. Implement P0a measurement contracts first. Real baseline (P0b), authority
   semantics (P1), scheduler (P2), integrated opt-in path (P3) and paper (P4)
   remain explicit separate gates.

## Questions the baseline must answer

- Is interactive tail latency dominated by controllable queueing or service?
- How much contention comes from canonical/evidence writes and artifact I/O?
- Does independent bounded concurrency solve most of the observed interference?
- Where is the last enforceable disclosure boundary for each host adapter?
- Which real operations can yield safely without weakening atomicity?

## P0b exploratory local baseline (2026-09-18)

The runner in `research/memory_fabric/local_baseline.py` used temporary AtMem
homes with 40 synthetic active memories. Each trial offered 60 requests at
80 requests/s, Poisson arrivals from the recorded seed, a bounded queue of 24,
and the same deterministic 48 recall / 9 write / 3 artifact operation mix.
Every completed operation captured full encrypted evidence; synthetic PNG, WAV
and MP4 content was reconstructed byte-for-byte. No user memory, model call,
OpenClaw session, host hook or external endpoint was involved. These are
composed local component measurements, not end-to-end agent latency.

| Workers | Seeds | Completed/offered | Write errors | Median of per-trial p95 completion | Median of per-trial p95 queue wait |
|---|---|---:|---:|---:|---:|
| 1 | 17, 19, 23, 29 | 240/240 | 0 | 129.4 ms | 113.5 ms |
| 2 | 17, 19, 23, 29 | 231/240 | 9 | 71.7 ms, survivors only | 43.3 ms |

The medians are descriptive across four short trials, not confidence intervals
or a 1.8× scheduler claim. All eight Poisson trials met the 25 ms generator-lag
p99 gate, had no admission refusal, and recorded unknown release authorization:
verified useful goodput therefore remains unavailable. The 20 rps fixed-arrival
exploratory trials had roughly 27–32 ms p95 completion and negligible queueing;
there was little scheduler headroom there. The fixed-arrival seed labels repeat
the same arrival schedule and do not indicate independent workloads.

The two-worker failure is a decisive negative finding. All nine errors occurred
on write close/vector sync, with `SQLITE_CONSTRAINT_PRIMARYKEY` on
`vector_entries` or `RuntimeError` reporting that canonical memory changed
while embeddings were built. The seed-29 report retains the exact synthetic
exception messages. Some writes may have changed canonical state before the
close failed; outcome/evidence accounting deliberately does not call them
successful. Concurrency safety, failure recovery and evidence semantics need
resolution before parallel write scheduling is a valid optimization.

**Go/no-go:** go for further instrumentation and controlled simulation; no-go
for production scheduling, speedup claims, or a paper result. Next isolate
memory open/close, vector sync, and evidence stages; add cold/warm profiles,
frozen manifests and run-to-run uncertainty. Authority/revocation races and
OpenClaw exact delivery remain untested. The local CLI gateway status reported
`missing scope: operator.read`; the two pre-existing UI device credentials had
that scope, but changing or rotating them was unnecessary for this isolated
baseline and might disrupt the user's UI. A later host-profile benchmark needs
a separate correctly scoped CLI device, not a borrowed or rotated UI token.

### Write-isolation follow-up

The failure path is `Memory.close()` → `sync_default_vectors()` →
`SemanticIndex.build()`. Two concurrent writers to the same synthetic subject
can both work on one staged vector epoch; one then sees either a duplicate
`vector_entries` key or a changed canonical generation. Serializing the entire
write/open/close segment with one in-process lock removed these exceptions in
four 60-request Poisson trials, but completed 238/240 and refused 2; median
per-trial p95 completion rose to 308.4 ms and median p95 queue wait to
260.8 ms. A dedicated single-writer pool (one read/artifact worker, one writer)
also recorded zero write exceptions, but completed only 228/240 and refused 12;
median p95 completion was 521.9 ms and p95 queue wait 497.4 ms. All completed
operations retained reconstructable encrypted evidence. These are negative
pilot results, not a controlled speed comparison: trials were run sequentially
on a changing local host, and a later one-worker control itself reached 493 ms
p95. No new policy is accepted as better than baseline.

The lock and lane are **research-runner-only** in-process controls. Neither is
a cross-process AtMem storage fix, nor does either prove correct release-time
authorization. A defensible next design must preserve fresh recall after writes
while making canonical write + vector projection concurrency safe, then compare
policies in interleaved, host-stable trials with error/refusal rates as gates.

### Direct AtMem versus research scheduling prototype

Review correction: this historical pilot used expected-phrase presence for its
quality check, not full context-byte parity, and used different FIFO/candidate
dispatcher implementations. Its numbers are exploratory. The controlled
follow-up in [homa-review.md](homa-review.md) replaces those comparisons for
policy assessment; old raw reports remain preserved.

To answer the product comparison directly, a **one-worker** research prototype
was added to the same real local runner. It uses AtMem's unchanged memory and
encrypted-evidence code; only queue dispatch changes. It favors earliest-deadline
recalls, uses static class-level service-cost estimates (artifact 4 ms, recall
12 ms, write 40 ms), and reserves every fifth dispatch for waiting bulk work.
This is a local deadline/size heuristic, not the governed Memory Fabric data
layer. It has no revocation/release linearization or production integration.

Five paired, interleaved Poisson trials used seeds 37, 41, 43, 47 and 53,
60 requests/seed at 80 offered requests/s, 40 initial memories, one worker,
24 outstanding slots, an identical workload digest for each pair, and full
encrypted evidence with exact image/audio/video recovery. The corrected
workload labels recalls as interactive and writes/artifacts as bulk. An earlier
pilot mislabeled writes as interactive and is excluded from this comparison.

| Real local path | Completed/offered | Errors/refusals | Median per-trial p95 interactive recall | Median per-trial p95 bulk | Median per-trial p95 all |
|---|---:|---:|---:|---:|---:|
| Unchanged AtMem FIFO | 300/300 | 0/0 | 395.4 ms | 483.5 ms | 432.1 ms |
| AtMem + research deadline/size dispatch | 300/300 | 0/0 | 362.3 ms | 554.6 ms | 442.7 ms |

Interactive p95 improved in four of five paired trials (median paired change
about -36 ms), while bulk and overall p95 worsened. All trials met the frozen
25 ms generator-lag p99 gate; none had a post-deadline completion or failed
output parity check. The improvement is **limited to this interactive metric**
in this small exploratory workload. It does not establish statistical
superiority or useful authorized goodput, because release authorization and
actual OpenClaw delivery were not measured. The prototype's bulk reservation
and cost estimates were not optimized or validated on a held-out workload.
The host showed material timing variation in earlier runs, so uncertainty and
load sweeps are still required. No production AtMem path was changed.
