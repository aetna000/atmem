# Scheduling Governed Agent Memory Under Deadlines and Changing Permissions

Created: 2026-09-18. Branch: `research/memory-fabric`.
Status: research specification; no production scheduler or performance claim.
Source: `RandD/AtMem_Memory_Fabric_Implementation_Plan_2026-09-18.pdf`.

## Overview

Investigate whether resource-aware scheduling can improve on-time delivery of
authorized agent context during mixed interactive and background workloads,
without weakening evidence, retrieval quality, deletion or useful throughput.
AtMem remains the authority; AtBot is an optional offline advisor, never a
dispatch dependency. Homa is inspiration, not an implemented transport or a
source of transferable performance numbers.

The first experimental system has one canonical authority and controlled local
workers. Network workers, distributed canonical replication, new transports,
learned scheduling and default activation are outside this initial scope.
The proposed contribution is the joint treatment of scheduling, revocable
authority, explicit withholding and evidence. Novelty remains unverified until
related-work research and experiments are complete.

## User scenarios

1. **Researcher (P1)** compares unchanged local execution with controlled queue
   policies using the same workload, capacities and capture settings. Every
   offered request is accounted for, including failures and unfinished work.
2. **Owner (P1)** revokes access or deletes a record while recall waits or runs.
   No response released after the authoritative change may contain that record.
3. **Operator (P1)** cancels a request while a worker finishes. Capacity is
   reclaimed exactly once, and a late reply cannot cause context delivery.
4. **Background user (P2)** sees imports progress under interactive traffic.
   Accepted bulk work receives its declared service reservation; overload is
   explicitly rejected rather than hidden in an unbounded queue.
5. **Investigator (P2)** reconstructs why context was delivered or withheld using
   AtMem alone, subject to current access privileges and capture configuration.

## Requirements and acceptance scenarios

- **FR-001 — Isolation.** Research execution is explicit and uses disposable
  synthetic homes. No normal CLI/dashboard/adapter default, schema, retrieval
  strategy, package version or user's running service changes. Test imports and
  disabled-path behavior; no hosted model or AtBot is required.
- **FR-002 — Accounting.** Versioned benchmark reports distinguish synthetic
  simulation, component measurements and real integrated measurements. Record
  every offered request's scheduled arrival, actual admission, start, terminal
  time and outcome. Account for completed, refused, expired, cancelled, errored
  and horizon-censored requests without silently dropping any denominator.
  Observed completion and verified on-time delivery are separate: nullable
  authorization/evidence/parity fields cannot be silently treated as true.
- **FR-003 — Reproducibility.** Use seeded open-loop arrival schedules, fixed
  dataset/policy/configuration digests, monotonic local timing, environment and
  source revision metadata. Report generator lateness separately. Preserve raw
  synthetic measurements and exact percentile definitions. No user content or
  credentials enter public benchmark files.
- **FR-004 — Stage attribution.** Measure actual local recall, writes and
  full-evidence capture before optimizing. Attribute queueing, storage/lock waits,
  retrieval, evidence/encryption and final preparation where measured; label
  uninstrumented stages unknown rather than zero. Do not infer a database or
  network bottleneck from response bytes.
- **FR-005 — Authority.** Future queued envelopes carry trusted scope and
  authority generations, not caller-asserted permission. Revalidate before
  worker content access and at the final AtMem-controlled disclosure boundary.
  Linearize final authorization and release relative to revocation/deletion;
  a check followed by an unprotected send is insufficient. If this cannot be
  guaranteed at a host boundary, withhold or label the unsupported guarantee.
  Mutation ACK defines revocation visibility; previously disclosed content
  cannot be retroactively recalled. Test revocation before grant, during work
  and racing with disclosure, including delete/update/read ordering.
- **FR-006 — Lifecycle.** Define queued, active, draining and terminal states.
  Terminal logical outcomes are immutable; late worker completion cannot reopen
  delivery. Use distinct request, attempt, chunk and receiver-generation IDs.
  Cancellation ends delivery eligibility immediately, but active resource
  credits remain charged until the worker stops or its generation is fenced.
  Duplicate completion/cancel/retry cannot double-release capacity. Failed
  writes never claim rollback or no side effects without transactional evidence.
- **FR-007 — Resource bounds.** Separately cap queued messages/bytes, active
  slots, active bytes and expensive computation. Size and service-cost estimates
  are distinct; enforce actual byte bounds when estimates are wrong. Oversized
  work is chunked, rejected or uses a declared bounded path. Never reset a lease
  and admit replacement work while an unfenced old worker still consumes it.
- **FR-008 — Fairness.** Reserve service across lanes and tenants before ordering
  within an eligible allocation. Publish reservation, burst allowance, maximum
  chunk/non-preemptible duration and queue bounds. A wait bound is conditional
  on those assumptions and admitted load; no finite completion guarantee is
  asserted under arbitrary overload or hung workers. Test sustained fast load,
  malicious tiny deadlines, oversized estimates and tenant imbalance.
- **FR-009 — Deadline and quality.** Expired requests are withheld, never counted
  as successful context deliveries. Deadlines use one monotonic clock locally;
  cross-machine clocks are outside the initial implementation. Scheduling must
  not truncate candidate sets, change ranking/top-k/budgets or omit evidence to
  improve latency. On equivalent snapshots, successful outputs equal baseline
  exact context bytes. Changed authority may correctly change/withhold output.
- **FR-010 — Evidence.** A future integrated path retains exact authorized
  request/context/artifacts and terminal reasons in the existing protected
  evidence system under its configured capture mode. Scheduling metrics are
  additional evidence, not a hash-only substitute. Prepare, authorize, release
  and host-confirmed exposure remain distinct. Durable authorization precedes
  release; unavailable evidence capture fails closed where required. Recovery
  reports indeterminate external delivery honestly and never invents success.
- **FR-011 — Fair comparison.** Compare local path, shared FIFO, isolated lane
  pools, EDF, estimated-size scheduling, weighted-fair/deficit-round-robin and
  combined policy at identical resource budgets. Separate mechanism ablations
  for admission, revalidation, chunking and credits. Exact remaining service is
  permitted only as a labeled simulator oracle, not a practical baseline.
- **FR-012 — Statistical protocol.** Freeze workloads and gates before final
  held-out runs; use independent seeds/repeats, randomized variant order,
  confidence intervals and separate cold/warm measurements. Compare on-time
  authorized goodput and end-to-end latency at matched offered load. Include
  failure/miss/censor rates, bulk progress and evidence completeness. Failed
  samples have outcomes, not fabricated successful-delivery latencies.
- **FR-013 — Evidence-bound claims.** Publish negative as well as positive runs.
  The source PDF's 50% queue-wait improvement and <=5% throughput loss are
  hypotheses, not release gates or established results. A paper must state
  deployment, scale, limitations and measured versus simulated results. No
  production, multi-node or broad novelty claim from a queue simulation alone.

## Success criteria

- **SC-001:** Reports reconcile all offered requests and pass deterministic
  accounting, invalid-input and open-loop timing tests; simulation output is
  unmistakably labeled as not product performance.
- **SC-002:** A real baseline identifies measured and unknown stages, with full
  evidence/encryption settings disclosed; no latency-gain claim precedes it.
- **SC-003:** Adversarial/model tests and eventual real-boundary integration tests
  show zero unauthorized or post-deadline releases and zero credit-accounting
  violations in the published suite. Tests are evidence, not universal proof.
  Publish interleaving bounds, tested case counts and injected fault coverage.
- **SC-004:** At matched load, report goodput, latency and fairness tradeoffs
  against strong baselines. A negative result is a valid research outcome.
- **SC-005:** Before activation, existing scope/delegation/evidence/host contract
  regressions pass and a supported encrypted-store-only reconstruction succeeds.

## Compatibility and exclusions

Python 3.10–3.13, local-first operation and optional dependencies are preserved.
No replacement canonical store or cryptographic profile; no migrations in P0.
Reuse Specs 010 (storage), 013 (identity), 019 (provider governance), 020
(evidence), 023 (revocation), 031 (retrieval). This spec does not mark their
pending capabilities complete. Existing stale privacy-minimization language
does not override the current full-fidelity constitution. New scheduling never
widens delegated authority or silently falls back to native memory after a
delegated failure. Dashboard work follows measured integration, not P0.
