# First live retail pilot: retained failure, not a product comparison

Evidence level: **engineering-native-pilot**. One development task, no injected
failure, no AtMem or AtFlows arm, no held-out or production claim.
Run: [`native-task0-001`](../results/pilot-usd20-20260925/native-task0-001/).
The conversation terminated normally; **the benchmark task did not pass**.

## Protocol

Public Sierra Research tau2-bench text retail, commit
`b7ea9074c1cba482b30687fecdb5c8425fd6f619`, task `0`, MIT license. This task was
already design-exposed in the unchanged pilot split. Native LLMAgent,
UserSimulator and Orchestrator were used, with logged single-attempt direct HTTP
in place of LiteLLM provider dispatch. Both models: `gpt-4.1-2025-04-14`;
temperature 0; seed 20260925; maximum output 2048 tokens; 58 steps; 60 total model
calls; 600-second loop timeout; 90-second request timeout. Provider residual
nondeterminism remains possible. No private customer/Home data was used.

The user's USD20 authorization covers agent, simulator, grading, retries and
recovery together. Each call reserved USD2.20 before dispatch in the shared
durable ledger, using the full model-context upper bound. Known usage releases
unused reservation; unknown charges retain it. No implicit retries, alternate
models or replacement trial were used.

## Observed result

| Measurement | Result |
| --- | ---: |
| Scheduled native trajectories | 1 |
| Conversation termination | Normal user stop |
| Local task reward (DB × applicable NL component) | **0** |
| Database match | **False** |
| Actual natural-language assertions | 0 |
| Agent / simulator / grader API calls | 11 / 7 / 0 |
| Native tool calls / tool errors | 6 / 0 |
| Retained messages / completed-step snapshots | 25 / 23 |
| Simulation plus local grading elapsed | 29.022 seconds |
| Estimated agent inference cost | USD0.045506 |
| Estimated simulator inference cost | USD0.011818 |
| Estimated total inference cost | **USD0.057324** |
| Unknown charge reservations at end | 0 |
| Remaining allowance by ledger estimate | USD19.942676 |

**Provider invoice independently verified: false.** Cost is a usage estimate with
cached-input discounts, not a reconciled bill. Standard prices were checked on
2026-09-25 against
[official GPT-4.1 documentation](https://developers.openai.com/api/docs/models/gpt-4.1):
USD2/M input, USD0.50/M cached input, USD8/M output. Elapsed time excludes imports,
checkout validation and setup; it is not restart-recovery latency. One run cannot
provide repeated-trial confidence intervals.

Agent usage: 54,513 input tokens (46,592 cached), 796 output tokens.
Simulator usage: 5,617 input tokens (1,024 cached), 265 output tokens.
Task 0 lists NL_ASSERTION in its reward basis but has no NL assertions. Its NL
evaluator returned a vacuous 1 with no grader call; that is not meaningful
language/policy-quality evidence.

## Why the task scored zero

The scenario asks for a clicky full-size keyboard with RGB backlighting, with
**no backlight as the fallback** if that combination is unavailable. The catalogue
reports the exact RGB variant unavailable. The agent offers the available
no-backlight and white-backlight variants. The simulated customer explicitly
chooses **white backlight**, then confirms the exchange. The agent processes
that confirmed selection successfully at the tool boundary.

The retained exchange call contains keyboard variant `6342039236` (white
backlight). The pinned reference action expects `7706410293` (no backlight).
The thermostat selection matches (`7747408585`). The native database evaluator
records a mismatch rather than treating the positive closing message as success.

This supports a **simulated-customer deviation from its assigned preference**.
It does not establish that AtMem or AtFlows failed, or that either would fix it:
neither product participated in this live trajectory. The prompt, user choice,
tool arguments and grading output are retained for inspection. Do not change
the expected answer or discard the trial after seeing this result.

## Retained evidence and validation

- `manifest.json`: source/dependency/harness hashes, exact role prompts, limits,
  seed, price snapshot and authorization snapshot.
- 18 request and 18 response files: public-corpus content, raw successful provider
  bodies, usage, response/HTTP request IDs and latency.
- 23 `step-*.json` files: native conversation and agent/simulator state snapshots.
- `trajectory.json`, `status.json`, `accounting.json`: observed trajectory,
  grading, dispositions and independent per-attempt accounting.
- `SHA256SUMS.json`: all **63** listed artifact hashes verified after completion
  by the implementation agent's local validation script, not by Claude.

Raw bundle size: approximately 2.41 MB. An exact-match scan for configured secret
values found no credential matches in JSON artifacts. This limited check is not
a sensitive-data certification. Customer/order data comes from the public corpus;
review before external publication. These are research exports, not an AtMem
encrypted evidence-store compliance demonstration. No HTTP error responses occurred
in this run. The error policy omits bodies that might echo credentials and retains
explicit omission reasons, classifications and digests.

40 local pre-spend tests passed, including native retail, budget concurrency and
restart, transport and fake-model orchestration. The rehearsal plants one NL
assertion only in its fixture to exercise grading; live source/task data is
unchanged. Claude reviewed source read-only before execution; it did not run
tests independently. Its post-run report review was also read-only and did not
re-validate artifacts. No remote CI, commit, push, release or publication is implied.

## Reporting and next gates

A defensible article finding: **a normally completed conversation and successful
tool call do not prove task correctness; retained evidence exposed a simulator
preference deviation.** This is a case study, not an AtMem superiority result,
pass-rate estimate or official leaderboard score.

Next: native-versus-wrapped no-fault validation; all four current configurations;
restart/context/evidence/telemetry boundaries; repeated qualification; then
preregistered held-out comparisons. Keep simulator protocol and ground truth
unchanged across arms. Remaining budget does not replace those engineering gates.
Preregister simulator-adherence annotations alongside reward without excluding
trials. Different arm trajectories can elicit different simulator deviations;
equal simulator configuration does not guarantee equal impact across arms.

The shared live SQLite ledger is Git-ignored and retained locally at
`../results/pilot-usd20-20260925/spend.db`; its JSON export is `accounting.json`
in the run bundle.
**Do not delete/recreate it to resume this authorization.** The authorization's
`authorized_not_executed` value is the immutable pre-execution snapshot; this
report and `status.json` record the subsequent execution.
