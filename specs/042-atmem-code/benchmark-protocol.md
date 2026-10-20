# AtMem Code coding-outcome evaluation protocol

**Status:** Phase 0 protocol only. Phase 9 execution is deferred by the owner. No outcome, score or production benefit claim is authorized by this document.

**2026-10-19 scoped authorization:** The owner subsequently authorized the
separate [SWE-bench Lite cold-start pilot](swebench-lite-pilot-20261019.md).
That thirty-task native-versus-structure campaign is not a VibeMemBench run,
does not resume the paused Click token-optimization goal, and cannot establish
experience-memory efficacy. The earlier deferral remains applicable to the
broader campaign below, not to this newly authorized pilot.

[Spec 043 Click replay](../043-click-historical-replay/spec.md) is a separate
engineering pilot with its own requirements, capability gates and future
budget/egress authorization. It neither replaces this campaign nor closes the
strong-baseline/held-out gates of FR-013 or T033. The pending product expansion
is Spec 042 FR-017–FR-028 / T043–T060; no feature is implemented by the harness.

## Source and availability gate

The primary intended benchmark is [VibeMemBench, arXiv:2609.23570v1](https://arxiv.org/abs/2609.23570). The paper describes 111 executable coding targets from 90 repositories and 3,634 prior trajectories. Its targets were selected after an oracle-experience uplift check in a reference setting, so its result is conditional on useful prior experience being available; it cannot estimate average benefit on arbitrary coding work.

The paper links [AlibabaResearch/DAMO-ConvAI/VibeMemBench](https://github.com/AlibabaResearch/DAMO-ConvAI/tree/main/VibeMemBench). At 2026-10-14, inspected Git commit `188835d4f9948563a6b9c8ac50cd0f3ae4021ed6` exposes only `VibeMemBench/README.md` with `Coming`. The task archive, history archive, executable grader and their dataset license could not be inspected or pinned. **No VibeMemBench run may be claimed until those artifacts and their redistribution/egress terms are available and hashed.** The paper's CC BY 4.0 license is not assumed to license the unreleased task data.

## Frozen design choices, to apply when artifacts become available

1. Maintain a development subset and an untouched held-out subset split by repository, not merely by target row. The exact IDs and hashes are recorded before any held-out run. If the upstream release fixes its own split, retain it and disclose any overlap.
2. Each target starts from the same repository commit, earlier-trajectory cutoff, solver/model version, tools, permissions, sandbox and budget in all arms. The target patch, hidden tests and future issues are evaluator-only and never enter formation or retrieval.
3. Compare memory-off, native host memory, AtMem memory-only, graph-only, AtMem combined and a technically comparable competing-memory/structural control. A directly injected verified experience is an oracle upper-bound arm, not an AtMem result.
4. AtMem must ingest the permitted earlier trajectories through its real capture/formation path and retrieve its own records during a new session. No hand-written or oracle-selected record is silently inserted into the product arm.
5. The primary outcome is executable task resolution. Secondary outcomes are fully metered input/output tokens and cost, agent steps, wall-clock and p50/p95 context latency, errors/refusals, memory capture rate, useful-context delivery, stale/wrong-context injection, indexing/build overhead and resource use. Attribute a failure to capture, formation, retrieval, packaging, delivery or solver use when the receipts permit; never infer a downstream cause solely from a final fail.
6. Report paired per-task outcomes and uncertainty, with each host/model shown separately. Use repeated paired runs or justify a single run; do not pool different agents as if they were one configuration.
7. Separately preregister an unfiltered sample of real repository issues to measure ordinary-work benefit, irrelevant-memory overhead and harm. Do not pool its results with VibeMemBench's experience-selected targets.

## Manifest required before a Phase 9 run

The runner must reject an incomplete manifest. Required fields: corpus and artifact license; immutable upstream commit and per-file checksums; target IDs and split; target repository revisions; prior-history cutoff per target; grader commands and images; host/model/plugin revisions; AtMem commit and configuration; competing baseline versions; hardware/OS; budgets; egress approval; seeds/repetition policy; primary metric; raw receipt and result locations. No placeholders may be represented as final values.

## Product-development diagnostic without a benchmark claim

Phases 1–8 can run focused real-session integration tests: record which observed turns were admitted, which durable facts formed, which exact memories retrieval selected, what bytes the host accepted, and whether a later coding task used them. These are functional diagnostics, not VibeMemBench scores or evidence of general coding improvement. They should identify *why* useful memory is lost before Phase 9 begins.
