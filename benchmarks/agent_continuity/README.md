# Agent Continuity Benchmark — implementation in progress

## Current product-first evidence

The shipped-package implementation now lives in `atmem/continuity/`, not this
directory. [User setup](../../docs/continuity.md) includes a persistent LangGraph
example and the **Decisions → Resume work** view. AtFlows has authenticated
continuity events and **Activity → Resume work** with reported cost/missing prices.

- [Installed LangGraph crash acceptance](results/product-acceptance-20260925-005/summary.json):
  actual process kills before/after receipt storage; both resumed with one
  published document, using a saved result or a destination query respectively.
- [Public retail four-arm replay](results/public-retail-parity-20260925-007/summary.json):
  baseline, AtMem, AtFlows and both matched all 18 recorded native model requests,
  six native tool calls, conversation and final store state. Same graph topology.
  Raw public-corpus results are compressed alongside checksums. This is no-fault
  integration qualification, not a fresh autonomous score or measured uplift.
- [Public retail interrupted exchange](results/public-retail-fault-20260925-003/README.md):
  baseline/AtFlows repeated the request once; AtMem/both withheld the uncertain
  repeat. Native store rejected repeats, so none created a second exchange.
- [Fresh four-arm pilot](results/public-retail-live-20260925-001/README.md):
  four new model conversations,68paid calls,estimatedUSD0.226608. All ended
  normally; native task scores1/0/0/0. Report all outcomes without inferring a
  success-rate advantage from one exposed task per configuration.
- Old smoke fixtures below remain historical design evidence. They are not used
  to implement recovery in the installed packages or the new retail graph.

Fresh faulted/held-out evaluation and production-wide gain claims remain gated.
No paid inference was used for product acceptance/replay checks; the separately
registered fresh pilot and its original raw responses have their own bundle.

> **Correction, 2026-09-25:** the current smoke worker implements recovery in
> benchmark code (`runtime.py`). Its results are design-fixture evidence, not
> proof of installed AtMem recovery. Product implementation now comes first;
> the replacement benchmark will only inject faults and measure. See
> [the corrected plan](../../specs/benchmarking/002-agent-continuity/product-first-correction.md).
> Do not use the quick start below as user-facing recovery enablement.

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
"$task_work/venv/bin/python" -m benchmarks.agent_continuity.runner --historical-fixture --output "$task_work/smoke" --include-atmem
```

For twenty repeats per smoke cell:

```sh
"$task_work/venv/bin/python" -m benchmarks.agent_continuity.runner --historical-fixture --output "$task_work/qualification" --repetitions 20 --capabilities I
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
are recorded in the lock; no upstream implementation is redistributed here.
The later M1 bundle retains a small pilot tool-output excerpt with the upstream
MIT notice; it contains public fixture data, not private user records.
`baseline-artifacts.current.json` binds the same unchanged runtime wheels to the
corrected protocol. `installed-artifact-smoke.json` records basic isolated version
checks, not a complete clean-install compatibility gate. Network access is used
only by explicit setup/lock-building; the smoke trial path has no hosted model.

Read the final validation record in `reports/implementation-status.md` before
quoting results. Development runs before the explicit `fault is not None` fix
had invalid clean controls and must not be treated as passing qualification.

## Required before a public result

### Implemented offline milestones

`retail.py` now calls the pinned upstream retail tools in a separate process and
compares outputs/final state with direct native execution of pilot reference
actions. This is **tool-boundary parity, not an autonomous agent evaluation**.
It does not close the upstream no-fault-equivalence gate. Reference actions are
evaluator-only and held-out development replay is refused. Wall-clock
`ToolMessage.timestamp` is the sole excluded response field. Source/data bytes,
tool schemas, environment metadata and results are recorded; in-tree bytecode,
extra executable modules and import shadowing cannot replace verified source.

The new retail CI job supplies the pinned checkout. AtMem CI does not currently
supply an AtFlows checkout/Bun for the cross-repository HTTP integration test, so
that test skips there. M2 evidence comes from the recorded local run and AtFlows'
own probe suite, not from a green AtMem-only job. Python 3.10 collection of these
new modules has not been verified; native retail execution requires 3.12–3.13.

Optional setup (Python 3.12; separate benchmark environment recommended):

```sh
python -m pip install -r benchmarks/agent_continuity/requirements-retail.txt
git clone https://github.com/sierra-research/tau2-bench.git /tmp/continuity-tau-checkout
git -C /tmp/continuity-tau-checkout checkout --detach b7ea9074c1cba482b30687fecdb5c8425fd6f619
python -m benchmarks.agent_continuity.retail --upstream /tmp/continuity-tau-checkout --task-id 0 --output /tmp/retail-tool-parity.json
```

Choose unused output locations; existing results are never overwritten.

`observation.py` drives the **unmodified AtFlows server** on ephemeral loopback
ports, with a fresh fixture DB and explicit instance directory. It sends fixture
OTLP spans, repeats one, intentionally drops one, and compares retained rows with
the independent delivery schedule. This tests the no-Origin, no-credential OTLP
route, not authenticated producer identity. Dashboard login is a different route.
Coverage calculations belong to the evaluator, not a new AtFlows capability.

```sh
python -m benchmarks.agent_continuity.observation --atflows /path/to/atflow --output /tmp/continuity-http-probe
```

The AtFlows checkout must include Spec 010's test probe and have its existing Bun
workspace dependencies installed. Its tracked runtime must match the frozen
current-product baseline. Installed `node_modules` bytes are not independently
hashed; Bun version, lockfile and tracked source are reported. No source version
is silently substituted. A missing dependency is a failed prerequisite.

Both probes strip provider credentials and dotenv loading. Test-only network
tripwires reject attempted external access; they are not a hostile-code/native
sandbox. AtFlows home-directory fallback is forbidden by its probe. No real Home,
existing daemon, integration config or production database is used. Temporary
fixture artifacts are retained for inspection. No benchmark model call occurs.

The original 61-cell smoke bundle remains immutable. These milestones do not
replace it or upgrade it to public-corpus or production evidence. See
`reports/milestones-20260925.md` for current validation and remaining work.

### Remaining gates

1. Complete the native retail adapter and no-fault upstream equivalence gate.
2. Finish current-policy/context and standalone evidence adapters and characterize
   gaps; integrate current AtFlows without inventing producer authentication.
3. Execute all four current-product arms on the pilot, preserving every outcome.
4. Preregister primary comparisons, sample sizes, uncertainty, multiplicity,
   safety/completion margins and cost limits before touching held-out tasks.
5. Propose only evidence-backed product fixes, then rerun frozen and changed arms.

No production-level score, winner, encrypted-evidence compliance, power-loss
durability, adversarial OS isolation, release or deployment is claimed.

## Budgeted native pilot and article evidence

First live result: [native pilot report](reports/native-pilot-20260925.md).
One conversation completed; task reward was zero. Raw failure evidence is retained.

`pilot-authorization.json` records the user's USD20 total inference authorization,
shared by agent, simulator, grading, retries and recovery. `spend.py` reserves each
attempt before dispatch. Restarts cannot reset an existing ledger; missing ledgers
fail closed. Unknown charges permanently retain their maximum in this pilot.
Provider invoice reconciliation is not implemented. The cap relies on the pinned
standard text pricing and a conservative bound, not provider-side billing controls.

`native_pilot.py` first rehearses pinned upstream orchestration. Default is dry-run:

```sh
python -m benchmarks.agent_continuity.native_pilot --upstream /path/to/pinned-tau2 --output /unused/dry-run
```

After review and authorization, initialize the shared ledger **once** with
`python -m benchmarks.agent_continuity.native_pilot --initialize-budget`. Add
`--execute --env-file /path/to/approved.env` to the dry-run command to dispatch.
The explicit file's OPENAI_API_KEY takes precedence over the inherited variable;
no file is sourced as shell code and dotenv interpolation is disabled.
Do not delete/recreate the ledger or its authorization directory between trials.
Keep the budget directory backed up outside OS temporary storage. Never upload its
live SQLite database; use the checksummed accounting export.

The first native-only task is the already design-exposed pilot task 0. No injected
fault, AtMem arm, AtFlows arm or held-out result is implied. Model-call transport
is direct single-attempt HTTP, replacing upstream LiteLLM dispatch but preserving
native agent/user prompt construction and orchestration. All model roles and
explicit retries share the same allowance. No retry is automatic.

Each output directory preserves the exact manifest/prompts, request/response JSON,
raw successful provider response, step snapshots, complete or partial trajectory,
DB/NL grading, status, accounting and checksums. Failed HTTP calls preserve status,
request ID, error type/code and body digest. Their raw message/body is deliberately
omitted because providers may echo credentials; the omission reason is recorded.
These are public-corpus experiment exports, **not AtMem's governed evidence store**.
No claim of encrypted product evidence is made by these files.

Articles must link a retained run and distinguish completed conversations from
correct task outcomes, known cost estimates from unknown reservations, and a
single development trajectory from a pass-rate estimate. Task 0 lists NL_ASSERTION
in its reward basis but has no actual NL assertions; the vacuous pass is not a
meaningful language/policy-quality measurement. Failed/incomplete runs stay in
the record. Do not publish automatically or claim product gains from this pilot.
