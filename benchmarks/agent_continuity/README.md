# Agent Continuity Benchmark — implementation in progress

This directory implements the **offline harness foundation**, not the complete
Agent Continuity Benchmark or a production claim. Governed by
`specs/benchmarking/002-agent-continuity/` and AtFlows spec 010.

## What runs today

- Genuine worker-process kills at eight synchronized barriers, with a destination
  process that stays alive and an evaluator-only ledger channel.
- LangGraph SQLite checkpoints plus a durable dispatch journal: a competent
  baseline, not a deliberately weak restart implementation.
- I (idempotency), Q (query) and N (neither) destinations; lost requests, fenced
  aborts, expired keys and delayed query visibility. Absence alone never licenses
  a retry while a prior request could still be in flight.
- Current AtMem task service/host-boundary adapter: explicit fixture enablement,
  scoped task binding, receipt-backed completion, blocked uncertainty and restart.
- Current AtFlows OTLP fixture generator and independent baseline inspection tests
  in its repository. This is not yet an authenticated live AtFlows arm.
- Independent duplicate/wrong-effect scoring, durable-status dispositions,
  missing/pending work counts, descriptive timing, cost-accounting unit tests and
  a seeded task-cluster bootstrap utility. No significance or superiority claim.

The runtime journal provides recovery in both tested arms. **These smoke cases
do not measure an AtMem-specific continuity advantage.** The deliberate naive
control proves the evaluator catches a duplicate even when the worker says success.

## Isolated quick start

Requires Python 3.12 for the pinned runtime/workload track. Nothing changes the
installed AtMem daemon, Home, package defaults or AtFlows server.

```sh
task_work=$(mktemp -d)
uv venv --python python3.12 "$task_work/venv"
uv pip install --python "$task_work/venv/bin/python" -e '.[dev]' -r benchmarks/agent_continuity/requirements.txt
"$task_work/venv/bin/python" -m pytest tests/benchmarking/test_agent_continuity.py -q
"$task_work/venv/bin/python" -m benchmarks.agent_continuity.runner --output "$task_work/smoke" --include-atmem
```

For twenty repeats per smoke cell:

```sh
"$task_work/venv/bin/python" -m benchmarks.agent_continuity.runner --output "$task_work/qualification" --repetitions 20 --capabilities I
```

Each output contains the complete randomized schedule, raw `trials.jsonl`,
`summary.json`, `manifest.json` and `SHA256SUMS.json`. Trial subdirectories hold
fixture checkpoints only. Output directories cannot be reused silently. Tokens
used by the fixture HTTP server are never included in the exported records.
No model calls or paid APIs are used. LangSmith tracing is explicitly disabled
inside the worker. Keep the outputs; nothing deletes them automatically.

AtFlows baseline characterization (from that repository):

```sh
bun install --frozen-lockfile
bun test tests/continuity/current-product.test.ts
bun tests/continuity/inspect-current.ts "$task_work/atflows-fixture" < tests/continuity/fixtures/receipt.json
```

That test deliberately records **current gaps**, including absent usage becoming
zero and duplicate-span rejection. It is not a conformance test for the intended
future behavior. Pricing-network refresh is disabled and a fresh local DB is used.

## Public workload and freeze

`protocol-lock.json` pins Sierra's tau2-bench repository commit and retail base
suite, verifies input bytes against that commit, and reserves customer-clustered
pilot/held-out IDs before any public-corpus run. No task answers are copied into
the worker. The manifest builder uses evaluator labels only for cohort selection;
an actual agent adapter must never receive those labels.

The initial split was corrected after Claude found alias leakage. Its original
record remains `protocol-lock.initial.json`; **no public tasks had run before the
correction**. The active split is 23 pilot / 81 held-out / 10 excluded zero-write
tasks. Public benchmark exposure/model contamination remains a limitation.

`baseline-artifacts.json` preserves the first built wheel hashes and original
protocol digest. Later records must not overwrite that history. The runtime
dependencies are benchmark-only. The upstream MIT license and exact source paths
are recorded in the lock; no upstream code or corpus is redistributed here.
`baseline-artifacts.current.json` binds the same unchanged runtime wheels to the
corrected protocol. `installed-artifact-smoke.json` records basic isolated version
checks, not a complete clean-install compatibility gate. Network access is used
only by explicit setup/lock-building; the smoke trial path has no hosted model.

Read the final validation record in `reports/implementation-status.md` before
quoting results. Development runs before the explicit `fault is not None` fix
had invalid clean controls and must not be treated as passing qualification.

## Required before a public result

1. Complete the native retail adapter and no-fault upstream equivalence gate.
2. Finish current-policy/context and standalone evidence adapters and characterize
   gaps; integrate current AtFlows without inventing producer authentication.
3. Execute all four current-product arms on the pilot, preserving every outcome.
4. Preregister primary comparisons, sample sizes, uncertainty, multiplicity,
   safety/completion margins and cost limits before touching held-out tasks.
5. Propose only evidence-backed product fixes, then rerun frozen and changed arms.

No live evaluation, production-level score, winner, encrypted-evidence compliance,
power-loss durability, adversarial OS isolation, release or deployment is claimed.
