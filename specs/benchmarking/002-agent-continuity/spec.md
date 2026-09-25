# Agent Continuity Benchmark

## Owner correction: feature first, inert benchmark

The binding [product-first correction](product-first-correction.md) adds product
requirements PC-001–PC-006 and replaces the earlier benchmark-first sequence.
Recovery must be available through installed AtMem and supported host integration;
AtFlows must provide its observation/accounting through shipped interfaces.
The benchmark injects faults and measures only: no recovery, state repair or
missing feature compensation in its helpers/adapters. Original FR-010/SC-002
require preserving old artifacts/gap evidence, not completing unsupported arms
before implementing the feature. Recovery-specific user status is now in scope;
general UI redesign and release remain out of scope. Product acceptance requires
the documented example to work with benchmark code unavailable.

Created: 2026-09-25. Status: product-owned operation/receipt service, installed
LangGraph recovery, user status/dashboard and AtFlows observation implemented.
Installed crash acceptance and recorded-response four-arm retail qualification
are separate from fresh autonomous and held-out evaluation, which remain open.
No general production-gain claim. The original native pilot terminated normally
but received task reward zero; later qualification does not alter that result.

## Purpose and boundaries

Test whether an interrupted agent resumes correct work, avoids duplicate external
effects, uses currently authorized context, and leaves inspectable evidence at
acceptable overhead. Build the product capability and test it independently;
retain current artifact/gap evidence without attributing fixture logic to products.

The host runtime owns checkpoints, execution, retries and scheduling. AtMem owns
governed task-state decisions, memory eligibility and evidence. AtFlows owns
observation and cost projections, not execution or authorization. This feature
does not replace any runtime or promise exactly-once external effects.

Existing contracts remain authoritative: [governed task state](../../../docs/governed-task-state.md),
[execution evidence](../../020-durable-execution-evidence/spec.md), and
[constitution](../../../.specify/memory/constitution.md). Task lifecycles remain
open/paused/completed/cancelled/expired; item states remain
pending/ready/running/blocked/completed/skipped/failed. Unknown external outcome
is a separate observation, not a new lifecycle state. Governed task state stays
off by default; experiment arms explicitly enable it.

## User scenarios

1. **P1 ambiguous commit**: destination commits an operation; worker dies before
   receipt persistence. After restart, reconcile using the destination's actual
   capabilities, or explicitly block. Never infer failure from a timeout.
2. **P1 revoked permission**: authority changes while stopped. On resume, both
   baseline and AtMem receive the same current policy information. A superseded
   fact or revoked action cannot be justified by an old checkpoint.
3. **P1 truthful observability**: telemetry is duplicated, delayed, lost or falsely
   reports success. AtFlows exposes coverage and reconciles observed usage;
   telemetry cannot change task authority or prove a destination effect.
4. **P2 reproducibility**: another team reproduces all arms and failure cells from
   pinned public workloads, manifests and raw records without private Home data.

## Functional requirements

- **FR-001**: Use a pinned public tau-bench-family text retail suite first. Record
  upstream commit, task IDs, license, models, prompts, budgets and scoring rules.
  Run its selected suite without injected faults first. Label our fault extension
  separately; no claim of official upstream scores or leaderboard acceptance.
  Pin user-simulator model/prompt/temperature; persist its conversation outside
  the killed worker. Preserve each trial's history on restart, not identical
  transcripts across diverging arms. Report simulator usage/cost separately from
  agent overhead and include it in total experiment spend.
- **FR-002**: Create an independent destination process with an append-only effect
  ledger hidden from runtime, AtMem, AtFlows and model. Only the evaluator sees
  ground truth. Real process termination must not terminate the destination.
- **FR-003**: Inject synchronized failures before dispatch, in flight, after
  destination commit/before response, after response/before checkpoint, and after
  checkpoint. Verify the actual barrier; no timing sleeps as evidence. Record
  unmatched barriers and infrastructure failures, not silently discarded trials.
- **FR-004**: Compare four arms: durable runtime; runtime+AtMem; runtime+AtFlows;
  runtime+both. Freeze a competent baseline with durable operation identity,
  checkpointing, reconciliation and current-policy checks. All arms get identical
  tools, authority information, destination capabilities, tasks and fault seeds.
  Naive restart is a negative control, not the principal competitor.
  A capability/responsibility table identifies task-state, context and
  reconciliation owners per arm. AtMem governs task/item commitments and context
  in its arms; baseline equivalent state cannot become a second writer. Runtime
  dispatch/retry and destination reconciliation capabilities remain equal.
- **FR-005**: Exercise idempotency-key destinations, query-by-client-reference
  destinations, and destinations supporting neither. Declare key retention,
  query visibility and pending-operation semantics. Absence from a query is not
  permission to repeat an operation still possibly in flight. Safe unresolved
  blocking is distinct from successful completion.
- **FR-006**: Preserve workflow/task/logical-operation identity across restarts;
  assign new run and attempt identities. Tasks can span runs. Authenticate scope
  and explicit joins, never infer them from text or timestamps. Map to existing
  execution identity contracts rather than creating a competing authority.
- **FR-007**: Evaluate current AtMem through public supported interfaces only.
  Revalidate policy and canonical context after restart; test revocation,
  supersession and conflicting/missing evidence. Record unsupported capabilities
  as gaps; do not implement them in adapters and attribute gains to AtMem.
- **FR-008**: Score true duplicate/wrong effects, completion, lost required work,
  safe blocks, unsafe retries, unauthorized/stale context, evidence completeness,
  and recovery latency/resources/cost from independently observable truth. Report
  every arm/cell with denominators, missingness and uncertainty, not a sole score.
- **FR-009**: Correlate optional AtFlows telemetry via the versioned
  [contract](contracts/continuity-v1.md). Separate usage from priced estimates,
  count each charge once, expose unknowns, and test duplicated/dropped telemetry.
  AtFlows downtime must not silently become authorization or business success.
- **FR-010**: Freeze current-product artifacts and raw baseline evidence before
  fixes. Retain original and changed versions, diffs, configuration and all runs.
  Never relabel improved adapter behavior as a shipped product capability.
- **FR-011**: Use smoke fixtures only for harness correctness, never production
  claims. After disjoint pilot trials, preregister representative task coverage,
  repetitions, minimum meaningful effects, budgets, stopping rules and analysis
  before held-out execution. Include task-cluster uncertainty and paired trials.
  Split pilot/held-out task clusters and lock their ID digests at G0, before
  viewing pilot results. Public tasks may be model-contaminated: held-out means
  unseen by our tuning, not necessarily by model training.
- **FR-012**: Publish runnable manifests, sanitized raw events, result tables,
  licenses and limitations. Keep private real Home data out. Authorized AtMem
  evidence capture remains full fidelity under its existing storage controls;
  public exports are separate sanitized artifacts with redaction accounting.

## Success criteria / gates

- **SC-001 harness**: Each fault barrier is demonstrated with an external trace;
  oracle detects deliberately planted duplicate effects, lost steps, bad joins,
  stale context and telemetry accounting errors. Every trial has a disposition.
  Deterministic smoke requires 20/20 hits per reachable barrier, detection of
  every planted defect, and zero false positives on 20 clean controls. These
  harness checks are not production confidence estimates.
- **SC-002 baseline**: All four current-product arms have capability manifests and
  immutable raw records before any improvement run. Unsupported arms are clearly
  recorded, not simulated. Native no-fault results remain distinguishable.
- **SC-003 evaluation**: A held-out run meets preregistered coverage and stopping
  rules and reports all FR-008 metrics with uncertainty and capability strata.
  Publish ties and regressions. A system that blocks everything cannot win.
  Improvement requires preregistered completion and safety non-inferiority plus
  superiority on a primary endpoint with multiplicity control. Label evidence
  smoke, engineering, or production-scoped with workload/fault/capability limits.
- **SC-004 compatibility**: Any later product change requires existing scope,
  persistence, CLI, disabled-default and artifact gates plus both repositories'
  contract tests. No release or default activation is authorized by this spec.

## Non-goals and follow-on gates

No retrieval-ranking tuning, UI redesign, live payments, production user fault
injection, automatic release, or safety certification. Cross-machine recovery,
corrupt storage, concurrent workers and additional domains follow the first
validated suite and need separately frozen fault contracts. Claims apply only
to the measured workload and supported destination capabilities.
