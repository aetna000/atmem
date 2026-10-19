# SWE-bench Lite cold-start pilot — 2026-10-19

Owner authorization: “ok ok do the SWE-bench for me”. Separate campaign from
the paused Click optimization goal. No product tuning, release, GPU rental,
API fallback, disk cleanup or favorable-task replacement is authorized here.

## Frozen first-stage scope

Thirty public SWE-bench Lite test identities: six each from Django, SymPy,
Matplotlib, scikit-learn and Sphinx. Use dataset revision
`b0dde1093fe417d83b7184254edf8199c1f0dff5` and upstream grader commit
`02e7a74ffd0b707aab73d203fe87bdc7c76afc8e`. Select using identity-only SHA-256
ordering with the seed in `benchmarks/code_replay/swebench_pilot.py`. Retain the
complete ordered cohort before reading any selected reference patch or hidden
test. No replacement for environment failures. Sphinx has prior repository
exposure; this is an engineering pilot, not untouched confirmation.

First compare **no persistent memory** with **AtMem structure**, using the
installed private preview, the same Claude subscription/model/medium effort,
identical base source, isolated tools, test environment and budgets. Alternate
arm order by frozen task slot. One attempt per arm, no outcome-based retry.
Thirty tool calls, 300 seconds, 500,000 total input-plus-output tokens and a
$2 provider-estimated cost ceiling per attempt. A subscription interruption
stops further dispatch; do not switch to billable API credentials.

SWE-bench does not supply a prior-session experience corpus. Native-memory,
experience-only and combined-memory efficacy require a separate legitimate
historical workload and matched access protocol. Empty experience is not
presented as an experience-memory benefit test. Do not insert target solutions,
oracle summaries or manually selected lessons into AtMem.

## Execution gates

- Windows WSL2/x86-64 Docker is the task executor. No GPU required. Keep at
  least 48 GiB physically free on the Windows backing drive; one container at a
  time; no deletion of existing images or owner files. Mac orchestrates Claude.
- Resolve and retain exact Docker image identities. Validate the selected base
  and upstream grader with unchanged-base and reference-patch controls before
  any model attempt. These controls are not model successes.
- Reference patches, test patches, grader files, future Git objects and owner
  files must be inaccessible to the solver. Model tools see only a source
  snapshot and legitimate public tests; no host shell or network tool.
- Retain exact prompts, streams, tool calls, results and final patches through
  the existing encrypted AtMem evidence boundary. Missing usage stays missing.
  Do not replace exact evidence with only hashes or public summaries.
- Graph context and tool use must be observed, not inferred from configuration.
  A clean memory-off comparison is required; forced graph consultation, if used,
  must be a separately labelled condition, never silently introduced mid-run.

## Reporting

Primary metric is full issue resolution under upstream FAIL_TO_PASS and
PASS_TO_PASS grading. Report all thirty selected tasks, environment attrition,
normal failures, timeouts and provider interruptions. Separately report paired
eligible counts, input including cache reads/creation, output, provider-estimated
cost (not a subscription invoice), solver wall time, indexing/preparation and
actual graph delivery/use. Preserve initial and terminal outcomes. Do not call a
30-task subset a SWE-bench leaderboard score or claim experience-memory efficacy.

The public manifest may contain task identities, source revisions and resource
metadata. Evaluator content and model transcripts remain in encrypted internal
evidence; only encrypted benchmark archives may be moved to MEM.

## Execution record and non-retry continuation

The first selected task is `sympy__sympy-17139`. A grading-adapter fault before
any model invocation incorrectly assumed the upstream resolution was an Enum;
the actual function returns a string. Its failed preflight is retained, the
adapter now supports either representation, and the same task's unchanged and
reference controls qualify. The first failed control's raw output was lost on
the adapter exception and is explicitly **not** full-fidelity control evidence.
The two subsequent successful controls retain their exact output. No model
attempt was repeated.

The native attempt completes and resolves the issue under the official grader.
The default installed AtMem graph cannot prepare this full repository: its
protected source-generation limit is 6,000,000 bytes. This is a product
preparation failure, not a model's incorrect answer or a reason to change the
indexed files. Keep it as an end-to-end failed AtMem cell, with no invented
model latency, cost or token count.

The first controller stopped on that setup exception. An explicit, separately
retained continuation changes only failure accounting: skip terminal cells,
never repeat a started model cell, and retain/count further AtMem indexing
preparation failures while proceeding through the same thirty identities.
Original controller source bytes and its lock are preserved; the continuation
captures complete new controller source and retains the identical product
wheel, worker, MCP tools, source selection, model, budgets and upstream grader.
No product limit is raised and no task is replaced. Both the first stop and the
continuation must be included in reporting.

Task execution uses one live task container. During AtMem preparation its
bounded optional extractor may also run briefly; this is additional indexing
overhead, not simultaneous agent-task execution. Claude's ephemeral config and
logs live on the existing volatile benchmark RAM volume. Captured streams and
results are retained in the encrypted internal evidence store.

## Official prepared-runtime correction

Further preflight exposed a controller error, not a product or solver outcome:
resetting/cleaning an upstream task image removes configuration and runtime
preparation that its official evaluator preserves. Sphinx's prepared pytest
reporting was consequently lost; passing reference tests could appear
unparseable. Separately concatenating stdout and stderr also destroys the
ordering expected around upstream test-output markers. The first protocol is
stopped; its two model attempts and every failed control remain diagnostic
evidence, not the primary pilot comparison. Do not select the better score.

The corrected run uses the **same thirty identities and sampling seed**, in
`swebench-lite-official-runtime-20261019`. Verify the prepared image HEAD instead
of hard-resetting/cleaning it. Retain prepared tracked configuration and runtime
files. Use upstream `exec_run_with_timeout` on an unchanged materialized
`/eval.sh`, matching the official evaluator's ordered Docker output. No test,
reference solution, scoring rule or product source limit is changed. Container
bootstrap/grading uses standard Docker capabilities; model command processes
remain UID/GID 1000, offline, without mounted owner paths or privilege escalation.
The tracked source is converted into a single-commit solver snapshot so no
future Git history is disclosed. Prepared-image verification has a regression
test ensuring it never issues `git reset` or `git clean`.

The corrected runtime must qualify reference and unchanged controls before
agent dispatch. The earlier two model attempts are kept outside its scores,
not silently overwritten or treated as equivalent runtime conditions. This
remains an exposed engineering pilot; no untouched confirmation claim applies.
