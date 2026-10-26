# Dolphin pilot recovery implementation — 2026-10-26

The owner authorizes bounded harness repair and an evidence-preserving supervised
continuation of the same20. Earlier read-only/no-repair/inspect-only retry policy
is **superseded within this scope**; historical task definitions and evidence are
retained. The implementation worker does not launch scored work, call reader or
judge models, modify private env files, commit or push. Root owns review,
qualification/freeze, private/MEM writes and actual supervised execution.

## Implementation and boundaries

`tool_defaults._same` compares finite JSON trees recursively, keeping bool and
string types distinct and comparing int/float without coercing integers to float.
It rejects nonfinite numbers, missing/different keys, reordered list elements,
wrong targets and true value differences. Export preserves raw gateway/native
messages and independent logs. An effective export may use the independently
observed JSON number representation only after proving exact numeric equality;
its normalization receipt retains the original entire call reversibly. Signature
defaults still require pinned AST provenance. No explicit semantic value changes.
The upstream validator uses serialized argument keys, so numeric representation
normalization is necessary even after proving equivalence. App call order remains
strict; exact MCP metadata methods are excluded because they are protocol
operations without independent application log entries. No mutation is exempted.

`pilot_recovery.py` provides:

- Historical condition verification against the retained original manifest and
  every before-repair source snapshot. This is **not** execution admission.
  Ordinary `load_condition` still rejects historical source after edits.
- Scientific equality over the complete condition except the source-manifest
  pin. Selection/options/wheel/checkpoints/routes/settings/bindings/rubric and
  budget remain identical. Source changes are limited to explicit harness/export/
  recovery/launch files in `REPAIR_SOURCES`; removals and other changes fail.
- A separate immutable epoch, original-parent artifact inventory and copies,
  original-condition provenance per execution/grade, exclusive creation, and
  explicit two-HARNESS-revision lineage with auditable old/new SHA-256 pairs. A second bounded repair can import a
  completed portion of the first epoch, retaining provenance and reporting three
  revisions. Further repair epochs require escalation. Never cherry-pick rows.
- Exact023/085 execution and grade copies; no `_execute`, `_apps` or `_grade`
  invocation for completed imported grades. Parent files are never changed.
- Offline129 export from exact requests/responses and API lifecycle session,
  successful native process, original dated user boundary, gateway/budget hashes,
  independent state/log snapshots matching original intent, native tool results,
  and both persisted booking objects. No provider/tool execution or grading.
  `outcome.completed:false` remains unchanged. Only a reproducible, hash-bound
  recovery receipt permits the report to accept that exception.
- Native shutdown observation when applicable. For this actual129 installed API
  context mode, pinned original `context-delivery.json` establishes that no
  native memory provider/shutdown hook applied. No shutdown witness is invented.
  Its native result records41748ms; this excludes controller overhead and is
  labelled accordingly, rather than claimed as exact adapter latency.
- SQLite inheritance by copying DB/WAL bytes to a disposable directory, backing
  up that copy and checking source pins. No original SQLite connection or
  sidecar mutation. New requests share the full inherited ledger and USD10 cap;
  inherited rows cannot be removed/changed. Unresolved charges, overruns or
  reservations stop continuation before new calls. Sidecar hashes are retained
  where relevant; original SHM is not copied or opened by SQLite.
- A nonblocking per-epoch lock and persistent O_EXCL dispatch/grade intents.
  Crash after an accepted booking cannot dispatch it again; unknown grading
  requests also cannot be retried automatically. Preflight refuses incomplete
  intents, inflight/returned uncertainty and existing unsaved app workspaces.
  Fresh listener/admission/PID state and provider/judge recording trees are created
  per launch, never inherited live.

The trusted Homebrew3.14 parent uses a fixed offline parsing command in the
frozen product3.12 interpreter for release metadata; it never mixes incompatible
ABI dependencies or dispatches models/apps. The original execution runner still
loads the complete authenticated upstream release.

The real launcher, pilot entry and forwarding gate enforce fresh ordinary
admission plus epoch verification before startup and every dispatch. During a currently admitted launch, request
guards permit only reservations created since that launch, counting their full
bounds. Startup and between-task checks still require zero unresolved calls.
Unknown failures/overruns and inherited/stale reservations always stop. Reports
re-verify inherited pins/proofs and ledger accounting. A complete report retains
regressions and blocks pilot promotion if a passed control regresses. Original
390/600, cohorts83/84/43 and conditional390/517=75.4% remain unchanged. This
post hoc20 is not a holdout, a single-harness experiment or a new600 score.

## Inputs and exact offline CLI

Run from this checkout. `recovery-inputs.json` is root's evidence map. The actual
parent remains read-only:

```
/Volumes/MEM/atmem-dolphinbench-20261020/readiness-pilot20-atsys-20261026-v2
```

The historical bundle format is:

```json
{
  "condition": {"path": "/retained/condition.json", "sha256": "..."},
  "source_manifest": {"path": "/retained/source.json", "sha256": "..."},
  "snapshots": [
    {"original": {"path": "/original/module.py", "sha256": "..."},
     "retained": {"path": "/retained/module.py", "sha256": "..."}}
  ]
}
```

Every original source entry must appear once. The old non-source scientific
input pins must still verify. Root prepared the actual bundle under
`/Users/javadtaghia/.local/share/atmem-dolphin-readiness-20261026/recovery-parent-v4`.
No private env file is read by these offline commands.

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/javadtaghia/miniconda3/bin/python -m benchmarks.dolphinbench.pilot_recovery verify-history \
  --bundle /Users/javadtaghia/.local/share/atmem-dolphin-readiness-20261026/recovery-parent-v4/historical-bundle.json
```

`proofs-129.json` contains pinned `api_witness`, `independent_state`,
`independent_log` and either `shutdown_witness` or the original `context_delivery`
that disables the native provider. Native process, intent, outcome, raw gateway
records and journal snapshots come from the unchanged parent. An actual native
provider without a successful shutdown proof remains blocked. Missing or
inconsistent evidence is reported precisely;129 must never be replayed.

After root review, tests, installed ARM zero-call qualification and a **new**
freeze, the trusted parent executes this preparation command (not the coding
worker; the paths require private/MEM writes):

```sh
/opt/homebrew/bin/python3 -m benchmarks.dolphinbench.pilot_recovery prepare \
  --bundle /Users/javadtaghia/.local/share/atmem-dolphin-readiness-20261026/recovery-parent-v4/historical-bundle.json \
  --condition "$NEW_CONDITION" --receipts "$NEW_RECEIPTS" \
  --parent /Volumes/MEM/atmem-dolphinbench-20261020/readiness-pilot20-atsys-20261026-v2 \
  --output "$NEW_EPOCH" \
  --proofs /Users/javadtaghia/.local/share/atmem-dolphin-readiness-20261026/recovery-parent-v4/proofs-129.json

/opt/homebrew/bin/python3 -m benchmarks.dolphinbench.pilot_recovery verify \
  --condition "$NEW_CONDITION" --output "$NEW_EPOCH"
```

`NEW_CONDITION`, `NEW_RECEIPTS` and `NEW_EPOCH` are explicit new absolute paths
chosen by root. Preparation refuses an existing destination; a failed partial
preparation is retained and requires a different epoch directory. It makes zero
model/app calls, does not grade129 and never imports old listeners as live.

## Qualification, freeze and continuation — root only

Use the same installed ARM runtimes/bindings from the historical descriptor.
Do not append x86 miniconda site-packages to an ARM Python. Root first runs:

```sh
/opt/homebrew/bin/python3 -m benchmarks.dolphinbench.qualify_profile \
  --upstream "$UPSTREAM" --app-python "$APP_PYTHON" \
  --runtime-root "$RUNTIME_ROOT" --options "$UNCHANGED_OPTIONS" \
  --output "$NEW_PROFILE_QUALIFICATION"

/opt/homebrew/bin/python3 -m benchmarks.dolphinbench.qualify_execution \
  --upstream "$UPSTREAM" --python "$APP_PYTHON" \
  --output "$NEW_APP_CRASH_QUALIFICATION"
```

Both perform real synthetic qualification with zero reader/judge calls. After
all source edits, root freezes its unchanged scientific descriptor via
`readiness.freeze(descriptor_path, NEW_CONDITION)` and issues new receipts via
`readiness.issue_qualifications(NEW_CONDITION, NEW_PROFILE_QUALIFICATION,
NEW_APP_CRASH_QUALIFICATION, NEW_RECEIPTS)`. Those functions refuse changed
source/runtime/options or incomplete qualification. Old receipts cannot qualify
new source. Freeze only after review has stabilized all source bytes.

Following successful epoch preparation/verification and independent review,
root's trusted supervised runner may execute exactly:

```sh
/opt/homebrew/bin/python3 scripts/launch_dolphin_readiness.py \
  --condition "$NEW_CONDITION" --receipts "$NEW_RECEIPTS" \
  --output "$NEW_EPOCH" --env-file "$PRIVATE_ENV_PATH" \
  --stage pilot --resume-epoch
```

This launcher selects the frozen installed-product interpreter and dependencies.
The env argument is a path for the trusted parent runtime; the implementation
worker must never open/print that file.023/085 grades stay byte-exact;129's saved
execution is never rerun and can be graded once if not already graded. Only the
remaining17 untouched selected tasks may execute. No ingestion, full600, app
reset or replay of an unknown action/provider call is permitted. Existing
successful grades are skipped. Uncertain execution/grade intents block restart.
A completed run takes a report-only path before provider/product startup.

For inspection, use `pilot_recovery verify` above. For a completed report,
`benchmarks.dolphinbench.pilot_readiness --condition "$NEW_CONDITION" --receipts
"$NEW_RECEIPTS" --output "$NEW_EPOCH" --report-only` uses ordinary admission and
reproducible recovery proofs; a control regression writes the complete report
then refuses a promotion receipt. No command here authorizes full600.

## Usable bounded supervisor handoff

`atsys/recovery-task-template.json` is an unsubmitted template, not a control-
policy change or nested AtSys task. It declares `allowRepair:true`, Codex
workspace coding repair, at most2 retries and an inspect-only `resumeArgv`.
`recovery_supervisor.py` never executes a supplied workload command. It checks
scope, exact tests/current source, fresh ordinary receipts, real native/app/crash
qualification (using the qualification issuer's full validation), inherited
proofs and a new immutable epoch. It writes a fixed launcher argv for the trusted
parent to review and execute outside the coding sandbox. No arbitrary shell,
blanket approval or automatic hash update exists.

Record tests on the final source (root must run the process inspection test
outside this restricted coding sandbox):

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /Users/javadtaghia/miniconda3/bin/python -m benchmarks.dolphinbench.recovery_supervisor test \
  --receipt "$NEW_TEST_RECEIPT"
```

Root materializes `atsys/recovery-request.json` using this contract:

```json
{
  "attempt": 1,
  "changed_paths": ["benchmarks/dolphinbench/tool_defaults.py"],
  "unknown_side_effect_or_charge": false,
  "tests": {"path": "/absolute/test-receipt.json", "sha256": "..."},
  "condition": "/absolute/new-condition.json",
  "receipts": "/absolute/new-receipts",
  "output": "/absolute/new-epoch",
  "env_file_path": "/private/env-path-only"
}
```

Then the template's safe resume command is:

```sh
/Users/javadtaghia/miniconda3/bin/python -m benchmarks.dolphinbench.recovery_supervisor handoff \
  --contract specs/048-dolphin-execution-readiness/atsys/recovery-task-template.json \
  --request specs/048-dolphin-execution-readiness/atsys/recovery-request.json \
  --output specs/048-dolphin-execution-readiness/atsys/recovery-handoffs
```

Each attempt/epoch is exclusive and cannot grant another dispatch. For a second
repair, supply snapshots of the immediately preceding condition/source and use
that prior epoch as `--parent`; completed additional work and charges are
inherited, never rerun. Unknown side effects/charges, incomplete or tampered
proofs, true argument mismatch, scientific/model changes, or exhausted repair
count require escalation. Do not clear markers or reissue original argv.

## Verification and remaining operational limits

Focused acceptance lives in `tests/benchmarking/test_dolphin_pilot_recovery.py`:
finite numeric precision/type/order/target tests; real upstream offline exports;
original grades/parent bytes; missing/tampered proofs; changed scientific config,
selection and source scope; stale admission and actual CLI denial; crash after
accepted action/unknown grade; SQLite sidecar preservation and inherited cap/
row protection; locks; initial and second repair epochs; old60 rejection;
complete recovered report with control-regression promotion refusal.

Implementation test results and actual retained offline replay validation are
recorded below after the final run. These are harness checks, not a live pilot
score. Current restricted sandbox denies `/bin/ps` in the existing test
`test_atsys_stop_terminates_isolated_benchmark_descendants`; root must run that
unchanged process-group check outside this sandbox. No gate is waived. New
installed ARM qualifications, source freeze, real epoch creation/continuation,
Claude acceptance and any commit/push remain root-owned work.


## Interim review disposition

The root-provided in-progress Opus review identified9 blockers. The final
implementation addresses: API-context shutdown proof, explicitly retained MCP
metadata, closed SQLite connections/DELETE-mode standalone backup and hot-journal
refusal, sorted manifest-bound signatures, independent argument/result/state
matching (plus upstream validation), nonempty ledger/gateway bijection, immediate
returned-execution preservation, fresh per-launch recording trees, and live-
reservation-aware forwarding checks with strict between-task reconciliation.
Source transitions retain old/new digest pairs; JSON evidence decoding rejects
duplicate keys and nonfinite values. A partial preparation intentionally remains
as evidence; its missing final transition cannot admit execution and root must
choose a new destination. This is a disposition of interim findings, not a claim
that root's final independent review/qualification has passed.

## Final implementation-worker verification

2026-10-26, final source, with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` and
`/Users/javadtaghia/miniconda3/bin/python`:

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /Users/javadtaghia/miniconda3/bin/python -m pytest -q --tb=short \
  tests/benchmarking/test_dolphin_pilot_recovery.py \
  tests/benchmarking/test_execution_readiness.py \
  tests/benchmarking/test_dolphinbench_campaign_gate.py \
  tests/benchmarking/test_dolphin_campaign_resume.py \
  tests/benchmarking/test_dolphinbench_gateway.py \
  tests/benchmarking/test_dolphin_tool_defaults.py \
  tests/benchmarking/test_dolphinbench_export.py
```

Result: **171 passed,1 failed in53.76s**. All67 new recovery tests passed,
including actual retained023/085/129 offline export, no provider/app dispatch,
both epoch imports, cumulative cost/coverage and regression report refusal.
The sole failure is the unchanged existing process-group test:
`test_atsys_stop_terminates_isolated_benchmark_descendants` encounters sandbox
`EPERM` for its group signal and `/bin/ps`. This check remains required; root
must rerun it outside the coding sandbox. No passing test receipt or promotion
receipt is claimed for this run.

Separately verified196 historical source snapshots and actual129 reconstruction
with zero provider/app calls and recorded native duration41748ms; actual023/085
exports remain accepted and grades unchanged. A real Homebrew3.14 parent using
the fixed frozen ARM3.12 offline parser successfully loaded all3 personas without
mixing native dependency ABIs. `git diff --check` passed.

No scored workload, reader/judge model call, private env-file read, original
result/grade write, AtSys task submission, commit or push was performed by this
implementation worker. Final independent review, new real ARM qualification,
new freeze/epoch and supervised remaining17 execution are pending with root.

## Active automatic parent

The executable parent, sealed contract, active AtSys task and protected repair
scope are documented in [Automatic recovery](atsys/AUTOMATIC-RECOVERY.md).
In the instructions above, root-owned execution is performed by that trusted
parent command worker; it does not require a human to type each qualification,
freeze or continuation command. Unknown side effects or charges still block
replay. The former handoff-only template is historical; use the active
`.atsys/tasks/dolphin-pilot20-qualified-recovery.json` configuration.
