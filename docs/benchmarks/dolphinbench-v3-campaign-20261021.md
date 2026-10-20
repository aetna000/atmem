# V3 full-campaign protocol — 2026-10-21

## Current condition: published Luna reader settings, unchanged V3 memory

Run directory: `campaign-atmem-v3-matched-luna-high-20261021`.
The published Hermes/Luna/Mem0 configuration in the pinned upstream release uses
`reasoning_effort=high`, `max_turns=60`, `context_length=1050000`.
The initial medium/20-turn condition was not reader-matched and was stopped at
70 graded Morgan tasks (33 passes), with its remaining in-flight evidence
preserved. Its complete raw traces and scores are cloud-archived and excluded
from the new condition; no task result is selected or adopted.

The full 600-task condition now matches those three published reader settings.
The actual Responses request is checked for `reasoning.effort=high` before
network I/O. The judge remains fixed Sol-medium/8000. Memory formation,
retrieval, source snapshots, scope isolation, rendering and governance are
unchanged. This is a correction to the comparator protocol, not a memory change
selected from task failures. It does not make the public benchmark a sealed
test, and no untouched-test or causal matched-Mem0-rerun claim is made.

Published reference: Mem0 424/600, with 37.7-second median latency; Morgan
156/200, Alex 132/200, Riley 136/200. The reference is the published run, not a
fresh control run. The agent transport differs (our subscription versus its
Azure Foundry) and costs cannot be compared as equivalent API charges.
Configuration JSON and its SHA are included in the new run identity. Eighteen
transport/export regression checks pass, including both reader configurations.

Morgan090 was executed and saved before a lazy grader import found missing
`markdown_it` in the isolated controller. The declared upstream requirement is
`markdown-it-py>=3.0,<5`; installing 4.2.0 (and mdurl 0.1.2) resolves it without
changing a rubric or rerunning an action. The separate finalizer uses the same
parser version. `scripts/check_dolphin_grader_environment_20261021.py` verifies
the declared participant dependencies across the split controller/app runtimes,
imports every grader module, checks Markdown behavior, and validates all 600
released check configurations without inference. Both controller and finalizer
preflight receipts are retained under the run's `repairs/` directory. Resume
reuses the saved execution and all completed grades verbatim.

```bash
ATMEM_HOME=/Volumes/AtMemDolphin/v3-full-r2-product-home \
TMPDIR=/Volumes/AtMemDolphin/tmp \
TIKTOKEN_CACHE_DIR=/Volumes/AtMemDolphin/cache/tiktoken \
/private/tmp/atmem-dolphin-controller-v3-20261021/bin/python -I -c \
'import sys; sys.path.append("/Users/javadtaghia/gitlab/aetnamem-dolphinbench-2.3.9"); from benchmarks.dolphinbench.campaign_v3 import main; main()' \
--output /Volumes/AtMemDolphin/campaign-atmem-v3-matched-luna-high-20261021 \
--baseline-from /Volumes/AtMemDolphin/campaign-atmem-v3-full-r2-20261021 \
--reader-reasoning high --reader-max-turns 60 --reader-context-length 1050000 \
--env-file /path/to/private.env --confirm-paid-grading
```

## Preserved medium/20 condition: product API without the desktop RPC deadline

Run directory: `campaign-atmem-v3-product-api-full-20261021`. This condition
retains the exact original frozen histories, research wheel, retrieval budgets,
model settings, rendering, native execution and grading rules described below.
Only preparation transport changes: the benchmark host calls the installed
product's authenticated `HermesService.dispatch(..., "prepare-turn", ...)`
in-process. The ordinary SDK response validator and native provider renderer
still run; authorization and lifecycle remain product-owned. No context is
generated or repacked by the controller. All elapsed preparation time is included
in task latency. This is not a latency/reliability claim for desktop HTTP hooks.

The preceding HTTP condition below is preserved, not combined into this result.
Multiple ten-second `unavailable_or_denied` outcomes were network deadline
failures, not semantically insufficient evidence. A read-only direct product
diagnostic for blocked Morgan003 returned `authorized` with 32 candidates.
The controller was interrupted at the ten-task checkpoint, before further model
work. No prior task execution or grade is adopted into this new condition.
The earlier errors, scores, raw traces and cloud copies remain available.
This transport correction does not alter source facts, retrieval, grading or
model instructions. Seventeen export/transport checks pass, including preservation
of scoped authentication and SDK rejection of malformed in-process responses.
The in-process response traverses an identical JSON serialization round trip
before SDK validation (including tuples becoming arrays). An initial unscored
qualification caught that missing conversion; its original identity and failure
are retained. Resumption before baseline adoption preserves the existing cloud
verification chain; no scored task was executed in that failed qualification.

Effective-call export also represents omitted optional arguments whose defaults
the actual application server logs explicitly. Defaults must be literal values
proven from the pinned `mock_mcp/repair*.py` function signatures. The exporter
may expand only those omitted defaults to match the independent backend log;
it refuses changed explicit values, unknown/required fields and conflicting
signatures. Model text, results, usage, original wire calls, app logs and grading
inputs are untouched. Each expanded canonical call retains its reversible
original and signature/source SHA provenance. Morgan005 stopped before grading
on omitted `cc=None`; its saved execution is repaired without rerunning any action
by `scripts/reconcile_dolphin_defaults_20261021.py`. Earlier grades stay fixed.

```bash
ATMEM_HOME=/Volumes/AtMemDolphin/v3-full-r2-product-home \
TMPDIR=/Volumes/AtMemDolphin/tmp \
TIKTOKEN_CACHE_DIR=/Volumes/AtMemDolphin/cache/tiktoken \
/private/tmp/atmem-dolphin-controller-v3-20261021/bin/python -I -c \
'import sys; sys.path.append("/Users/javadtaghia/gitlab/aetnamem-dolphinbench-2.3.9"); from benchmarks.dolphinbench.campaign_v3 import main; main()' \
--output /Volumes/AtMemDolphin/campaign-atmem-v3-product-api-full-20261021 \
--baseline-from /Volumes/AtMemDolphin/campaign-atmem-v3-full-r2-20261021 \
--env-file /path/to/private.env --confirm-paid-grading
```

## Preserved HTTP condition: wire-faithful one-shot API context

Run directory: `campaign-atmem-v3-system-full-20261021`. Adopt the cloud-verified
13,539 history records and exact frozen product checkpoints from the earlier
`campaign-atmem-v3-full-r2-20261021` baseline; do not adopt any task execution.
Source ingestion is inherited, not represented as an independent rerun.

The native prefetch preparation attempt stopped on the first task because Hermes
attached context to the user field, violating the benchmark's exact-user boundary.
Its full execution remains archived and ungraded. It contributes no selected
outcome to this condition. No task answer was used to tune retrieval or memory.

For each fresh one-shot Hermes session, the installed AtMem native product
provider performs its ordinary scoped RPC, sufficiency decision and rendering.
The returned context is forwarded unchanged through Hermes's supported
`ephemeral_system_prompt` setting. Native user-side prefetch and built-in memory
are disabled to avoid duplicate injection; delegation is disabled because the
submission format represents one conversation. Native agent execution, session
search and simulated app tools remain in use. This is an **API-context delivery
condition**, not a score for the ordinary native-prefetch hook.

Qualification uses the unmodified upstream `Runner._execute`, not just the
adapter directly. It requires an exact original user message, actual provider
instructions containing the complete native prologue, a recalled company answer,
a real simulated inbox call and unchanged frozen product memory.
It also applies the unmodified `grading_calls` validator to the independent
application log. Modern Hermes unary `tool_call(calls=[entry])` envelopes are
exported in the upstream-supported `tool_call(entry)` shape. IDs, arguments,
model text, tool-result bytes, order and usage remain unchanged; reversible
envelope receipts accompany exports and the original API bodies remain intact.
Hermes rejects batches of multiple local MCP tools; those rejected requests are
retained unchanged, never converted into fictitious executed actions.
The first saved task stopped before grading on this serialization mismatch. Its
recording is repaired reversibly by
`scripts/reconcile_dolphin_unary_export_20261021.py`, without rerunning the model
or its actions. Previous run identity, original task row and the exact two changed
controller-source hashes are retained. No memory/model/rubric settings change.
Thirteen export and native transport regression checks passed for this repair.
The Hermes auxiliary converter ignored `developer` rows; the compatibility bridge
now maps a homogeneous instruction prologue to Responses `instructions` and
asserts exact equality before each provider call. Mixed instruction priorities
fail explicitly. This follows the [official instruction/message mapping](https://developers.openai.com/api/docs/guides/text#message-roles-and-instruction-following).
Earlier failed qualifications and their raw bodies are retained, not counted as
accuracy results. No benchmark prompt, rubric, source fact or expected answer is
added by the bridge.

Already uploaded immutable history/case artifacts retain their first independently
verified cloud copies. Further checkpoints upload new artifacts and rehash mutable
manifests, instead of rereading all prior full exports. History traversal is skipped
only once all original history and observation-receipt paths are verified and all
three product checkpoints are frozen. New payloads still undergo secret screening,
upload and exact-revision download verification.

```bash
ATMEM_HOME=/Volumes/AtMemDolphin/v3-full-r2-product-home \
TMPDIR=/Volumes/AtMemDolphin/tmp \
TIKTOKEN_CACHE_DIR=/Volumes/AtMemDolphin/cache/tiktoken \
/private/tmp/atmem-dolphin-controller-v3-20261021/bin/python -I -c \
'import sys; sys.path.append("/Users/javadtaghia/gitlab/aetnamem-dolphinbench-2.3.9"); from benchmarks.dolphinbench.campaign_v3 import main; main()' \
--output /Volumes/AtMemDolphin/campaign-atmem-v3-system-full-20261021 \
--baseline-from /Volumes/AtMemDolphin/campaign-atmem-v3-full-r2-20261021 \
--env-file /path/to/private.env --confirm-paid-grading
```

The sections below retain the earlier preparation and storage history. Where a
delivery description differs, the current scored-condition definition above is
the governing configuration. The product wheel and V3 engine are unchanged.

## Memory path and release identity

This condition uses the memory APIs behind the historical **AtMem 9/30 versus
Mem0 OSS 7/30** result: authorized `Memory.form_context_episode`, then frozen
`Memory.prepare_context_v3` with `context-fast`, 200 candidates and 32,000 context
bytes. The earlier beta's score is not inherited by this run. Stable 2.3.8 and
2.3.9 have identical V3 engine files; the stable versions retain the later
approval-conflict fix. Agent and judge settings have changed since that beta.

The Hermes bridge now offers an explicit administrator-selected `context-v3`
binding. Existing bindings still default to their original control-plane path.
V3 source imports require a scope-bound grant and an encrypted household. Source
identity conflicts, secret screening, scope checks, shadow/inactive delivery,
revocation and monotonic freeze remain enforced. V3 checkpoints hash actual source
bytes, units, ranges, relationships, coverage, vectors and generation state.
Telemetry is excluded; physical FTS internals are not claimed tamper-complete.

Artifact: **unreleased research wheel based on 2.3.9**, SHA-256
`8a7e972c03bea5cc7eb143daeb6b57c4e13b1baff4613df00d32fa2ff49df345`.
No tag, PyPI release, default user installation or website deployment is changed.
The benchmark need not wait for 2.3.10. Distributing the changed Hermes integration
to customers requires a separately published release and its normal gates.

## Frozen experiment

| Component | Configuration |
| --- | --- |
| Corpus | DolphinBench `81cb6f8405b40a9e76089cef650806a80af06ea2`; all released hashes authenticated |
| History | 13,539 observations; three isolated, empty persona stores; chronological within each persona |
| Ingestion | Local V3 episode formation; no model calls; host acknowledgements are not generated assistant answers |
| Concurrency | Three independent persona batches; join writers before each archive |
| Action gate | Product V3 sufficient status required before model invocation, as in the historical adapter |
| Agent | Installed Hermes `d0288be5b3330d2442e3907185b8e9d0958297bb`; Luna, medium reasoning, 20 tool turns |
| Agent authentication | Existing Hermes ChatGPT OAuth subscription; no paid API fallback |
| Agent transport | Native Hermes Chat Completions path, using Hermes's existing Codex Responses compatibility converter in a controller-only bridge |
| Completion limit | Codex OAuth does not support an explicit output-token cap; record requested and actual provider settings rather than claim it enforces 4,096 |
| Judge | Actual Azure-hosted Sol via Azure-only OpenRouter; medium; 8,000 completion tokens; unchanged upstream prompts/rubrics |
| Judge alias | OpenRouter wire name `openai/gpt-5.6-sol`; fixed submission identity `gpt-5.6-sol`; both original wire bodies and canonical records retained |
| Tests | All 600; fresh native profile and isolated simulated apps per task; frozen memory; all failures retained |
| Historical comparison | Prior 9/30 versus 7/30 remains separate; no full matched Mem0 rerun is represented as completed |

The agent receives no user OAuth credential, paid API key, source database,
answer files or grader. It receives only a local gateway credential, its scoped
AtMem credential and its simulated-app connection. Hermes model title upgrades
and automatic background skill review remain disabled through supported settings.
The supported host spill threshold is 33,000 characters so it does not replace
the product's bounded V3 context with a truncated preview/file pointer.

Export policy, fixed before scored results: preserve the original native-request
ZIP, and produce a separate actual-provider-settings ZIP. The latter omits only
Luna completion-cap fields that the actual archived Responses requests prove were
not forwarded. Model, applied medium effort, prompts, tools, outputs, usage,
grades and the fixed Sol judge settings are unchanged. The transformation is
reversible against an explicit receipt; both artifacts must pass the unmodified
upstream validator/replay before delivery. An unsupported requested cap is not presented as an
applied provider limit. See `scripts/package_dolphin_actual_settings_20261021.py`.

Subscription access is not described as free or unlimited. Operator accounting
records zero incremental agent API charges, actual provider-reported tokens,
and any unreported failed attempts separately; subscription fees are not allocated
per call. DolphinBench can compute its own pricing estimates from those tokens.
Sol API charges and uncertain requests remain in the operator's hard budget.
Up to US$249 is reserved for this condition plus US$1 for all preparation,
including the actual Sol replay diagnostic (US$0.001136). Combined ceiling: US$250.

## Qualification before scale

- Installed native V3 fixture: an original Morgan history message retained;
  fresh-process recall delivered the company evidence to Hermes; a real
  simulated inbox tool call executed; the frozen V3 checkpoint stayed unchanged.
- Actual OAuth agent: answered the company question using V3 context. A separate
  transport-only read executed `list_inbox`; this unscored diagnostic does not
  require personal-memory sufficiency and does not relax the full-run gate.
- Actual Sol-medium judge: a non-benchmark diagnostic response was recorded and
  replayed identically through the unmodified upstream replay implementation.
- Product regression tests cover legacy behavior, scope, encryption requirement,
  source identity, secrets, shadow mode, V3 byte limits, freeze/restart and evidence
  tampering. Installed tests explicitly preload installed AtMem before pytest and
  disable the repository's `pythonpath` setting; `-I` alone does not override that
  pytest configuration. Earlier pytest-only reports remain source-regression
  evidence, not proof of installed imports. Native CLI qualifications already
  used the installed wheel independently of pytest.

Two external-workspace native binaries failed their wheel RECORD hashes/code
signatures during preparation. They are infrastructure failures, not task scores.
Executable runtimes now use isolated internal temporary directories with native
RECORD verification; datasets and evidence remain on MEM. Working databases
initially remained there, then were staged offline as documented below.
No user runtime, global login, release installation or unrelated disk data was
replaced. Only managed dependencies were staged, never user memory/auth files.
The subsequent benchmark-only working-database staging is recorded below.

## Execution and recovery

Use the installed benchmark controller, isolated Home and external temporary
storage. The full entry point refuses a changed research wheel or missing native
V3/Sol qualification. It records immutable corpus/runtime/artifact/source identities
before full ingestion. `--resume` accepts only that exact condition and reuses
completed interactions/grades; uncertain native generations are not blindly replayed.

```bash
ATMEM_HOME=/Volumes/AtMemDolphin/v3-full-r2-product-home \
TMPDIR=/Volumes/AtMemDolphin/tmp \
TIKTOKEN_CACHE_DIR=/Volumes/AtMemDolphin/cache/tiktoken \
/private/tmp/atmem-dolphin-controller-v3-20261021/bin/python -I -c \
'import sys; sys.path.append("/Users/javadtaghia/gitlab/aetnamem-dolphinbench-2.3.9"); from benchmarks.dolphinbench.campaign_v3 import main; main()' \
--output /Volumes/AtMemDolphin/campaign-atmem-v3-full-r2-20261021 \
--env-file /path/to/private.env --confirm-paid-grading
```

Execution source: `e0c97a4`. The first launch completed its isolated live
qualification but the upstream runner refused initialization because nested
qualification receipts preceded `run.json`. No benchmark histories/tasks or
Sol grading ran there. It remains archived separately. The controller correction
creates the upstream identity first; the new `r2` directory is a fresh condition,
not a retried or selected task result. Product wheel and model settings did not
change. All final installed gates passed: 93 product/native contract tests and
6 transport/replay tests (overlapping older reports are not summed).

After 3,040 histories, an operator-only helper opened one idle encrypted database
connection per persona and set each helper connection to SQLite `query_only`.
It holds no read transaction and issues no queries during the run. This avoids
checkpointing the WAL on every last-connection close. Commit synchronization,
encryption, episode formation, chronological order and retrieval are unchanged;
all databases remain on MEM. The exact start count and helper identity are saved
in `repairs/idle-database-connections-20261021.json` and archived. Ingestion timing
before/after this storage operation must be reported separately; no homogeneous
full-ingestion latency claim is made. The helper was stopped before offline SSD
staging; it is not part of the scored task phase.

At Morgan history `001215`, the controller received `observation_uncertain` and
stopped before any scored task. Its original in-flight marker and failure archive
were preserved. The source's deterministic episode identity was absent from the
database; the exact original observation subsequently succeeded through the same
scoped, idempotent product API. No model inference was replayed. The wrapper did
not expose the underlying original exception, so its precise cause is unconfirmed.

A live relocation attempt refused to move any file because database handles
remained open. Only after controller exit were the three encrypted working
databases staged to a private internal SSD directory. Raw file checksums, SQLCipher
`quick_check`, V3 row counts and the ordinary product constructor all passed;
originals remain on MEM. Existing logical database paths point to the working
copies. Product authority/configuration, source order, synchronization and model
settings are unchanged. `repairs/ssd-working-databases-20261021.json` and
`repairs/history-001215-reconciliation.json` record the operations. All 600 scored
tasks use the post-staging condition. Evidence/archives remain on MEM and Hugging
Face; full-ingestion timing is not a homogeneous storage comparison. The same
run resumes without replaying previously completed histories or task answers.

Raw requests, actual provider Responses bodies, normalized native exchanges,
tool results, usage, rulings, costs and V3 source/evidence exports are archived to
the private [AtMem evidence repository](https://huggingface.co/datasets/atmem/dolphinbench-evidence-20261020).
Every uploaded batch is downloaded at its exact commit and verified by size and
SHA-256 before generated profiles are removed. V3 exports preserve source bytes
and typed state, not encryption keys; rebuilding FTS is required. They are not
advertised as bit-exact encrypted-database backups.

Final packaging uses the unmodified upstream ZIP validator and judge replay,
not a hand-written substitute. Network-transport acceptance and maintainer
verification are external publication states; the disclosed OpenRouter route
must not be labelled a direct Azure subscription deployment. No leaderboard
upload is performed automatically. Complete raw action traces remain available
for an additional official grading pass without rerunning the agent if requested.
