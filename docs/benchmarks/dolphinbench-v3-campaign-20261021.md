# V3 full-campaign protocol — 2026-10-21

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
