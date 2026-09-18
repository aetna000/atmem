# Memory Fabric research implementation plan

## Technical context

AtMem 2.3.3 / AtBot 0.1.0; Python 3.10–3.13, existing canonical local
storage and protected evidence. No new runtime dependency. Current preparation
is in `atmem/control/manager.py`; delegated preparation in
`atmem/delegated/service.py`; timing helpers in `atmem/telemetry/retrieval.py`.
Do not mistake the existence of a backend interface for distributed guarantees.

## Architecture and decisions

1. Build research tools under `research/memory_fabric/`, outside the installed
   `atmem` package. They operate only on synthetic data in temporary homes.
2. First deliver a validated open-loop schedule and report-accounting library.
   This is benchmark infrastructure, not the scheduler and not P0 completion.
3. Measure the unmodified local API using a later real runner. Keep local-path
   and worker-queue experiments distinct; trace the synchronous caller queue
   and database waits instead of inventing a distributed FIFO baseline.
4. Model authority/release and worker-resource lifetimes separately. Logical
   expiry/cancellation does not immediately return physical worker credits.
5. Prototype policies only after P0 establishes a real source of contention.
   One authority serializes mutations/release commitments; workers may compute
   from scoped inputs but cannot independently disclose context or mutate
   canonical truth. Exact authority/release integration is a P1 design gate.
6. Persist real evidence through the existing protected store. Public research
   reports contain synthetic timings and fixture data only. Do not add a
   plaintext production trace store or weaken existing provider retention rules.
7. AtBot advice, distributed workers and dashboard controls are later stages,
   not prerequisites for the first experiment or a reason to change defaults.

## Proposed files

- `research/memory_fabric/README.md`: safe invocation and honest status.
- `research/memory_fabric/protocol.py`: seeded arrival schedule, validated
  observation contract and complete outcome accounting (P0a).
- `tests/test_memory_fabric_protocol.py`: exact accounting and invalid-input
  cases; no machine-dependent speed assertions (P0a).
- `research/memory_fabric/local_baseline.py`: real local fixture runner (P0b).
- `research/memory_fabric/lifecycle.py`: reference authority and resource state
  model, never production authority (P1).
- `research/memory_fabric/simulation.py`: deterministic policy comparison (P2).
- `research/memory_fabric/results/`: synthetic raw results and manifests only,
  separated by measurement type and source revision.
- `research/memory_fabric/scheduling.py`: research queue ordering with measured
  service debt; no authority/release implementation.
- `research/memory_fabric/homa_experiment.py`: common one-worker execution for
  direct queue comparisons with full-byte read oracle and protected evidence.
- `research/memory_fabric/run_fairness_suite.py` and `analyze_fairness.py`:
  freeze calibration, workloads, source and trial order; evaluate paired
  uncertainty and per-kind bulk guardrails. Exploratory, not P1/P3 approval.
- `specs/033-memory-fabric/homa-review.md`: primary-source research, independent
  review dispositions, experimental limitations and results.
- `specs/033-memory-fabric/experiment-protocol.md`: preregistered measurements.
- `specs/033-memory-fabric/research.md`: related work and bounded design claims.
- `specs/033-memory-fabric/review.md`: reviewer findings and dispositions.

## Phases and gates

### P0a — Protocol scaffolding (first bounded implementation)

Generate deterministic open-loop arrivals and validate per-request observations.
Report nearest-rank completion latency, offered-work outcomes, goodput and
unfinished work separately. Fail loudly on missing/duplicate/inconsistent rows.
No sleeps or runtime scheduling policy is introduced. Unit tests use synthetic
observations; they cannot establish real performance or safety at host boundaries.

### P0b — Real baseline, before scheduler work

Use the existing public memory and protected-evidence APIs with synthetic text
and original image/audio/video fixtures in disposable homes. Measure cold setup
separately from steady recall, store and evidence capture. Record hardware,
worker counts, capture/encryption settings, input sizes and throughput; expose
unknown stage attribution. Build fixed-arrival load generation with explicit
queue limits and generator lag. No live user home, remote provider or paid API.
Stop and reconsider scope if queueing is not material.

### P1 — Correctness model and boundary design

Define the authorization linearization point, evidence-before-release contract,
mutation visibility and cancellation/credit state machines. Exhaust small
interleavings: revoke/delete/cancel/grant/finish/retry/receiver restart/evidence
failure. Define barriers for dependent writes/reads. Authorize fetched bytes at
use time; a stale generation never becomes an implicit grant.

### P2 — Controlled scheduling experiments

Use identical worker/byte/compute budgets for FIFO, isolated pools, EDF,
estimated-size, DRR and combined policies. Bound queues and reserve bulk/tenant
service, with conditional wait bounds. Sweep admitted load and estimate error.
Keep simulator results separate from wall-clock runner results. Revalidate
exact output parity against unchanged retrieval on stable snapshots.

### P3 — Integration and evidence

Only after P0–P2 review, design an opt-in integration against the actual control
and evidence APIs. Run real revocation/delivery races and delegated host tests;
prove evidence reconstruction and fail-closed unavailable capture. No simulated
invariant result substitutes for a real integration test. Add dashboard trace
drill-down only against real data, preserving current roles and navigation.

### P4 — Publication

Freeze manifests before held-out measurements, publish all runs, uncertainty,
failure outcomes and limitations. Article is Markdown starting with an H1;
inline math uses `\( ... \)`, display math uses `$$ ... $$`. Include method,
related work, hypotheses, results, ablations, threats to validity, artifacts and
limitations. Do not draft a results narrative until results exist. Paper scope
may be a systems experience report if broad novelty cannot be established.

## Validation

Run focused research tests followed by existing retrieval, evidence and delegated
contract regressions appropriate to touched boundaries. Performance gates are
separate from correctness tests and require real measured data. No package or
release action is authorized by this plan. Source PDF remains unchanged.
