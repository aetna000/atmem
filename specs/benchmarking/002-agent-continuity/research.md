# Research and decisions

The user's “From Agent Memory to Agent Continuity” article motivates this work.
It is a proposed direction, not evidence of current restart guarantees.

## Starting workload

- [Sierra tau2-bench](https://github.com/sierra-research/tau2-bench): candidate
  public text retail workflows and final-state assertions. Resolve the exact
  revision, suite naming, license and redistribution rights during harness setup;
  repository names and upstream benchmark versions must not be conflated.
- [Agent durability lab](https://github.com/sjarmak/agent-durability-lab): candidate
  methodological reference for fault barriers and oracles, not an established
  leaderboard or a substitute for representative tasks. Verify provenance and
  license before reuse.

No existing leaderboard admission is promised. Our controlled failure extension
must not be represented as an official upstream benchmark run.

## Why start with the ambiguous commit?

It reveals whether recovery knows the difference between a failed request and an
unknown external effect. However, checkpointing and idempotency are runtime and
destination capabilities. A well-built baseline may equal AtMem; that is a useful
result. AtMem-specific tests then add changing permissions, canonical context and
evidence continuity, without denying those information sources to the baseline.

## Alternatives deferred

LoCoMo/LongMemEval retrieval scoring does not judge external effects. Retrieval
fusion and graph tuning are separate experiments. A dashboard is a later view of
validated data, not the first deliverable. Pure synthetic workflows may calibrate
the harness but cannot satisfy the constitution's production evidence gate.

## Risks

Fair policy equivalence, reproducible crash placement, hidden-oracle isolation,
provider variability, price uncertainty and task-cluster dependence are mandatory
protocol concerns. Pin them before held-out runs. Evaluate current code before
filling unsupported gaps; otherwise there is no honest before/after comparison.
