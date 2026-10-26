# Frozen execution runbook — 048

This runbook and `routes.json` govern the execution-only rerun. Read them before
any launch, even in a new Codex session. `condition.json` is generated privately
from verified files; its identity and passing receipts are mandatory at dispatch.
Task completion is tracked separately in `tasks.md`. Never infer GO from a chat.

## Which prior run is the baseline?

- Published dataset revision `5ef528c499aa26b765fff9d8ed8f2c2e6ee52912`.
- ZIP SHA-256 `78788ad3455d04407c037706d3ff129d56eafff89beaac101f2a461cb58d7538`.
- Every one of its 6,047 recorded assistant completions uses
  `openai/gpt-5.6-luna`, high reasoning and a recorded 4,096 completion cap.
  Temperature, top-p and seed are absent throughout.
- The completed private campaign is
  `/Volumes/MEM/atmem-dolphinbench-20261020/campaign-atmem-2310b1-judge-only-20261022`:
  600 real task records, matching Luna/high, both state assessors disabled.
- **Do not reuse** `launch-full600-2310b1-20261022.py` or the abandoned
  `campaign-atmem-2310b1-full-20261022[-mem]` configurations. They name a Sol
  reader and enabled assessment in a different, incomplete condition. Similar
  directory names are not proof that a configuration produced the public result.

## Frozen responsibilities and routes

| Role | Executes where | Frozen implementation/settings | Paid API allowed? |
| --- | --- | --- | --- |
| History import | Local | Original chronological source episodes; reuse verified frozen checkpoints | No |
| Memory storage | Local | Published AtMem 2.3.10b1 wheel, exact payload; no learned write classifier | No |
| Retrieval | Local controller | Source-coherent lexical/semantic path; unchanged original budgets and discovery limits | No |
| Embeddings | Local Ollama | `nomic-embed-text:latest` at `127.0.0.1:11434`; exact digest in `routes.json`; truncation disabled | No |
| Initial/follow-up state assessment | Disabled | No assessor or automatic remote classification | No |
| Reader | Existing ChatGPT subscription | `gpt-5.6-luna`, high, 60 turns, 1,050,000 configured context | Subscription only; no API fallback |
| Judge | OpenRouter API, Azure only | `openai/gpt-5.6-sol`, medium, 8,000 completion tokens, JSON-object response | Yes, explicitly budgeted |
| App actions | Local simulated MCP server | Pinned upstream tools and isolated app state, not real Notes/GitHub/Google | No |

The reader's Chat Completions record has a 4,096 cap. The existing subscription
backend does not support explicit `max_output_tokens`; its native completion
behavior is preserved and recorded. Do not describe 4,096 as an enforced native
provider cap. Sampling controls/seed remain omitted to match the original;
hosted weights/kernels/provider defaults can change. Repeatability here means
verified artifacts/routes/inputs and replayable evidence, not bit-identical text.

Embedding digest is checked at startup and before scored dispatch/provider
forwarding. Missing local services stop execution; they never enable cloud
substitution. Reader and judge settings are checked against the actual outgoing
requests. Subscription hooks verify actual `chatgpt.com` model/reasoning identity.
Judge routing forbids provider fallback. Native auxiliary title/skill review
work is disabled. No automatic model upgrade is permitted.

## Input freeze checklist

- [ ] Exact published AtMem wheel and installed payload verified.
- [ ] Upstream manifest and fixture/source hashes verified at pinned commit.
- [ ] All three original persona checkpoints match through installed AtMem API.
- [ ] Isolated copy made with original database bytes and authority IDs preserved;
  location-only state rebasing recorded through the product serializer.
- [ ] Reader/judge identities, inference controls, original host identity and
  local memory options pinned; no assessor or paid retrieval route added.
- [ ] Local Ollama digest matches `routes.json`.
- [ ] The 20-ID selection revision 3 is pinned; historical 83/84/43 cohorts and
  passed controls remain identified evaluator-side, not disclosed to the actor.
- [ ] Fixture policy retains Morgan/085 and Morgan/130 as unavailable operations
  in the denominator; no grader-derived tool repair.
- [ ] Native/app interpreter, environment/payload inventory, source files, options
  and runbook pinned. Private API/OAuth keys are references, never public config.
- [ ] New output directory and a finite paid budget chosen. Initial pilot cap:
  **US$10 of incremental API spend**, principally judging. Subscription fees,
  local hardware/energy and Claude review billing are separate and not “free.”
  The future full-run cap is separately frozen at US$20; it does not authorize launch.

## Evidence order and launch

1. Run `qualify_profile`: actual native Hermes request captured without forwarding.
2. Run `qualify_execution`: synthetic real app bridge/state/log and crash checks.
3. Freeze the final candidate after implementation/review changes. Bind raw
   qualification artifacts to that identity with profile/apps/recovery receipts.
4. Pilot admission requires all three passing receipts less than 24 hours old,
   unchanged artifacts, exact options and all pinned files. Missing or changed
   evidence means STOP before calls. A drift does not get repaired in-place.
   Admission freshness is evaluated once at launch and bound to that process/run;
   unchanged source, receipts and artifacts are still checked during every dispatch.
   A run crossing the 24-hour boundary does not silently renew admission or fail
   solely because wall-clock time elapsed.
5. Launch through the installed-product wrapper:

```sh
python3 scripts/launch_dolphin_readiness.py \
  --condition /private/benchmark/condition.json \
  --receipts /private/benchmark/receipts \
  --output /Volumes/MEM/atmem-dolphinbench-20261020/NEW-PILOT-DIRECTORY \
  --env-file /private/configuration.env \
  --stage pilot
```

Paths above are examples, not permission to substitute an existing run directory.
The wrapper offers no model/endpoint/reasoning override. It preloads the installed
published product before orchestration imports and checks executed wheel bytes.

6. The pilot evaluates every fixed ID under the original rubric, then records
   actual costs, unresolved calls (including zero-cash unknown subscription usage), per-case outcomes, recoveries, regressions and
   cohort membership. A 19-case pilot cannot authorize a full run. Regressions
   block promotion for investigation; a failed report remains retained.
7. A full run additionally requires a complete passing pilot receipt and explicit
   `--stage full --confirm-full-run`. No full 600 run is authorized by this task.
   All 600 cases remain in its denominator, including known fixture limitations.

## Stop, recovery and drift rules

- Keep OS automation and real credentials isolated; do not enable Notes access,
  install a local CLI, change provider or authenticate a real account mid-run.
- Never switch local memory work to API inference after a local error.
- Each interaction records durable intent before the agent starts. Preserve
  returned state/log bytes even when the agent or exporter fails.
- A prior app workspace or uncertain intent blocks setup; do not clear `.inflight`,
  truncate logs or repeat an action to get a cleaner result.
- Retain failed attempts and budget reservations. Unknown paid charges remain
  reserved until reconciled. Do not treat timeout as a zero charge.
- A changed artifact/settings/route requires a new condition and qualification;
  completed rows from different conditions must not be mixed.
- Re-run focused qualification after code fixes. Record hardware/software and
  actual provider responses; a successful replay validates saved grading, not
  independent model reproduction or leaderboard acceptance.

## Current state

Implementation and qualification status, exact frozen condition paths/digests,
review findings and live pilot outcome belong in `verification.md`. If that file
does not establish all required gates, the decision remains **NO GO** for full.

## Preparation commands (before any model calls)

The current machine's private descriptor/options and copied checkpoints live in
`~/.local/share/atmem-dolphin-readiness-20261026/`. They are durable files outside
Codex caches. The original MEM image remains read-only. Use a new versioned
condition, receipts and qualification directory after any implementation change.
Do not hand-author passing receipt booleans. The issuer validates retained native
request/profile evidence and real app/crash results against the frozen sources.

Run the native profile qualifier under the same installed-product bootstrap used
by `scripts/launch_dolphin_readiness.py`; pass `--upstream`, `--app-python`,
`--runtime-root`, `--options` and a fresh `--output`. Run the app qualifier with:

```sh
python -m benchmarks.dolphinbench.qualify_execution \
  --upstream /path/to/pinned/dolphinbench \
  --python /path/to/qualified/arm64/apps/bin/python \
  --output /private/benchmark/NEW-app-qualification
```

Then, from a controller environment with repository imports available:

```python
from benchmarks.dolphinbench.readiness import freeze, issue_qualifications, admit
freeze("/private/benchmark/descriptor.json", "/private/benchmark/condition.json")
issue_qualifications("/private/benchmark/condition.json",
                     "/private/benchmark/NEW-profile-qualification",
                     "/private/benchmark/NEW-app-qualification",
                     "/private/benchmark/NEW-receipts")
admit("/private/benchmark/condition.json", "/private/benchmark/NEW-receipts", "pilot")
```

Do not copy an expired receipt to a new timestamp. Re-run qualification. On a new
machine, provision identical artifacts first; changed absolute bindings require a
new condition and qualification, not editing the old condition in place.

## Owner-requested 20-task amendment

The active selection is `pilot-selection-20-20261026.json`:6 Notes failures,
3 GitHub failures,2 fixture limitations,2 recovered-Notes passed controls,
2 other missing-action/log cases,2 traced-zero failures,2 traced-partial failures
and 1 other passed control. It is a deterministic post hoc subset of the preserved
60-task revision2 selection, not a representative20/600 sample. Reader max_turns
stays 60. Do not confuse reader turns with pilot task count.

The private descriptor is `candidate-descriptor-pilot20-v1.json`; condition is
`condition-pilot20-v4.json`; fresh qualification lives under `pilot20-v4/`.
Old60-task conditions/receipts cannot admit under the new source and selection.
The completed historical 390/600 record is unaffected.

Use the new AtSys config `.atsys/tasks/dolphin-readiness-pilot-20.json`, not the
old blocked60-task task. This command worker runs only the pinned launcher under
the controller's normal account permissions. The native benchmark agent remains
sandboxed. Automatic recovery uses an inspect-only command, never scored replay.
No silent 10-minute progress deadline is added: goalMonitoring=false and explicit
zero activity/progress deadlines; heartbeat and 12-hour attempt/24-hour task bounds
remain. Model-based read-only supervision is bounded to two calls. No automatic
repair or full600 launch is authorized.

The exact-command worker propagates stop/timeout signals to its isolated benchmark
process group and detects loss of its AtSys parent. Interrupted provider calls
remain uncertain and cannot be automatically replayed. Fresh receipts are issued
immediately before launch; handoff/validation must remain within their24h window.

The controller and qualification now share a private short Unix socket under
`/private/tmp`, independent of runtime/output path length. ExFAT AppleDouble
`._` sidecar files are excluded from task/marker enumeration; actual task files
and inflight markers remain enforced. The first20 startup failed before any
model/app call at socket bind; its empty app log and raw evidence are retained.
