# AtMem action guard: routing, completion and commit checkpoint

Updated: 2026-10-31. Branch `feat/dolphin-action-routing`, based on
`research/dolphin-execution-audit-20261025` at `3dc4e2d`.

**Status: implemented, unit-tested, replayed offline and smoke-tested in the
real Hermes plugin host. Not qualified, not piloted, not scored.** No model,
application or grading call was made for the replay. The published result stays
390/600; the fixed20 diagnostic stays 13/20. Launch admission remains bound to
`dolphin-mcp-only-v1`; the new `dolphin-routed-v1` condition needs its own
qualification receipts before any dispatch.

## Why this exists

The fixed20 pilot recovered failures by *hiding* local tools (an MCP-only
profile). Real users keep Notes, a terminal and real GitHub next to connected
applications, so the product needs to choose the route itself. The audit also
showed three separate failure modes that hiding does not address:

1. **Wrong route.** All 35 untraced Notes failures loaded the `apple-notes`
   skill and ran `memo notes` after `tool_search "notion create page note"`
   returned no lexical match for `create_doc` (morgan/016 is the typical trace).
2. **No write at all.** Requests to create/send/review ended with a draft or a
   read-only trace. Seven traced partial PR reviews called `get_pr` but never
   `review_pr` (lesson L03).
3. **Remembered constraints not applied at the write.** morgan/023 and
   riley/156 still fail in the fresh five-task rerun. Neither request states the
   failing requirement: "decline the non-urgent Friday call" and "brunch at Salud"
   must come from memory. riley/156 never searched memory before
   `create_calendar_event`; morgan/023 searched once and received fragmentary
   evidence that did not state the Friday rule.

## What was built

| Component | File | Behavior |
| --- | --- | --- |
| Policy | `atmem/action_guard.py` | Stdlib-only. Classifies the request text, unwraps `tool_call` wrappers, decides allow/block, records attempted/accepted/failed connected writes and produces a completion verdict. |
| Router | same | For an action request only, refuses a local route (`skill_view` of apple-notes/github/notion/google-workspace/…, `memo`, `gh`, `osascript`, `imsg`, `open -a`, document `write_file`) when a configured connected application has a write tool for the requested destination; reads (`gh pr list` for a question) and unrelated skills stay allowed. Explicit local requests ("in Apple Notes") are allowed. The refusal names the routed tool. Bounded to 6 refusals per turn so it cannot loop. |
| Route memory | same (`RouteMemory`) | Records a local route only after an actual tool result shows a sandbox/permission/auth failure, with the result hash and excerpt; later sessions refuse that route even without a connected alternative. Owner-only JSON per Hermes profile. |
| Completion check | same | Each write result is accepted, failed or unconfirmed; acceptance needs an affirmative marker (`ok:true`, an id, exit 0) at a result/structuredContent/MCP-text layer, and several writes in one wrapper need an itemised result. `completed` needs an accepted write matching any destination the request names explicitly; a mix of accepted and unconfirmed writes is `partial`. Explicit local requests are reported as `completed_local`/`unverified_local` without a warning. Finished turns are released; sessions are capped. |
| Commit checkpoint | same | When memory tools are visible, the first call to each connected write tool is held once (nothing is sent) with an action-specific memory query built from the call's own arguments (recipient, title, weekday from ISO dates). The retry passes. |
| Hermes plugin | `atmem/adapters/hermes/action_guard_plugin.py` | `stage(home)` writes `plugins/atmem-action-guard`; enable with `plugins.enabled`. Uses `pre_llm_call` (request-specific route note, injected into the user turn), `pre_tool_call` (block directive), `post_tool_call`, `transform_llm_output` (appends `NOT COMPLETED` and writes `.atmem/action-guard/outcomes.jsonl`). |
| Benchmark condition | `benchmarks/dolphinbench/execution_profile.py` | `dolphin-routed-v1`: the ordinary inventory (terminal, skills, deferred tool search) plus the staged guard. Dispatched by driver/adapter/gateway via `apply_profile` / `validate`. |
| Offline replay | `scripts/replay_action_guard_dolphin.py` | Runs the router and completion check over recorded transcripts. |

## Offline replay over the published 600 transcripts

Inputs: public `submission.zip` (sha256 `78788ad3…d7538`), its `tests.json`
(sha256 `e5673894…5d2af`) and the audit ledger (sha256 `fd343ac8…08369`).
Output: [replay.json](evidence/dolphin-action-guard-20261031/replay.json). The
commit checkpoint is disabled in replay (it holds every first write by design).

| Original cohort | Tasks | First detour refused | Flagged NOT COMPLETED |
| --- | ---: | ---: | ---: |
| pass | 390 | 36 | **0** |
| traced partial | 43 | 11 | 8 |
| traced zero | 84 | 7 | 2 |
| untraced zero | 83 | 45 | 82 |

- **Notes:** 35/35 untraced Notes-error failures are refused at their first
  detour (`skill:apple-notes`) and redirected to `create_doc`.
- **GitHub auth:** 6/6 untraced GitHub-auth failures are refused at `skill:github`.
- **Completion:** action intent is detected in 83/83 untraced failures; 82 are
  flagged. The unflagged one is morgan/129, whose booking calls were accepted
  but whose backend log was lost (L13), which is the correct verdict.
- **Traced flags are correct:** all 10 traced tasks flagged NOT COMPLETED only
  read data and never made the required write (e.g. `get_pr` without `review_pr`).
- **No false notices:** every passing task is `completed` (355) or
  `no_action_requested` (35); none receives a NOT COMPLETED or PARTIALLY COMPLETED notice.
- **Regression risk:** 36 passing tasks would have had a detour refused, mostly
  `skill:github` (23). They passed after eventually using the connected tool, so
  the refusal removes a detour, but a live pilot must confirm no control regresses.

A refused detour is not a passing task: replay cannot know what the model would
have written instead. Content quality is unmeasured.

## Real Hermes smoke test

Hermes v0.21.5 (`d0288be5`) with a scripted OpenAI-compatible endpoint and a
stdio MCP application (`create_doc`, `list_docs`) plus a memory server:

- Detour script: the route note naming `create_doc` reached the user turn;
  `skill_view apple/apple-notes` and `memo notes -a` were refused with the
  redirect (memo never ran); the final answer received the NOT COMPLETED notice;
  the outcome record listed both refusals.
- Write script: `create_doc` accepted, verdict `completed`, no notice.
- Checkpoint script: the first `create_doc` was held, `memory_search` ran, the
  application received exactly one `create_doc`, verdict `completed`.

Hermes wraps MCP tool results in an untrusted-data envelope, including the
checkpoint notice; the route note therefore states the checkpoint in the user
turn. Smoke-test hazard: running `hermes` with a fresh `HERMES_HOME` triggers its
first-run update, which rewrote the shared launchers under
`~/.hermes/hermes-agent/.hermes/bin/` to that home's toolchain. They were
restored; future smoke tests should use the harness runtime invocation instead.

## Independent review

Codex `gpt-6.1-sol` (medium) reviewed the first commit read-only and requested
changes: affirmative-acceptance tri-state results (P1), destination-matched
completion and partial reporting (P1), no false warning for explicit local
actions (P2), no redirect of reads/unrelated skills (P2) and session lifecycle
bounds (P2). All five were fixed with regression tests and the replay re-run. A second review
confirmed three resolved and found four remaining defects: per-target operation
outcomes (a success to one recipient no longer clears a failure to another),
destination cues under polite phrasing, prerequisite reads (`gh pr diff`) only
redirected to a connected read tool, and itemised single-call batches. All four
were fixed with regression tests; replay numbers are unchanged. A third review found
two more: distinct created items merged into one outcome, and compound commands
(`gh pr diff && gh pr review --approve`) receiving the read exemption. Created
items are now keyed by identifying fields (or full arguments), the read exemption
needs every command component to read, and Hermes wrapper-validation rejections
(`tool_call …`, never dispatched) are classified `undispatched` rather than as
failed operations. Replay numbers are unchanged. A fourth review found the
single `&` background separator and title-sensitive keys for updates with a
stable record id; both were fixed with tests, replay unchanged. A fifth review found that
two creates in one shared destination (same repo) collapsed; operation identity now
separates record ids (updates), destinations plus identifying fields (creates) and
destinations alone (sends, so corrected messages still match). Replay unchanged. A sixth review found
repo-scoped issue numbers and parent-scoped creations (`add_slide` in one deck)
colliding; record ids are now scoped by repository and creations combine parent,
destination and item identity. Replay unchanged.

## Routed pilot v1 failure

The first routed AtSys attempt stopped on morgan/023: the route note injected into
the user turn violated the pilot's byte-identical user-boundary check, so nothing
was saved or graded. In the benchmark profile the plugin now leaves the user turn
and the final answer untouched (`route_context=false`, `completion_notice=false`);
qualification checks the boundary on every actual native request. The guard's
refusals and outcome records are unchanged.

## Limitations

- **No in-turn retry.** Hermes exposes no stop hook for non-code turns
  (`pre_verify` fires only after file edits), and the benchmark requires one
  user message per task. The guard prevents detours and reports NOT COMPLETED;
  it cannot force another model step after a final answer.
- **Checkpoint is unmeasured.** It costs one extra model step per write tool
  and depends on retrieval actually surfacing the rule. morgan/023's recorded
  search returned fragments without the Friday rule, so retrieval quality, not
  only the checkpoint, decides that case. Do not claim 023/156 are fixed.
- **Rule-based classification.** Intent and route patterns are deterministic
  regular expressions derived from the public transcripts. They may miss new
  phrasings and must be evaluated on the next run, not tuned to grader labels.
- **Route memory is local to a Hermes profile.** It is not yet stored in the
  AtMem engine's governed memory or shared across hosts.

## Next steps before any scored use

1. Qualify `dolphin-routed-v1` with fresh actual tool-array, plugin-load and
   synthetic write receipts; extend launch admission for it.
2. Pilot the same fixed20 IDs under `dolphin-routed-v1` with memory held fixed;
   report recoveries and control regressions separately from the MCP-only pilot.
3. Run the checkpoint as a separate condition, so routing and checkpoint effects
   are not conflated.
4. Investigate fragmentary `memory_search` results (morgan/023) as a retrieval
   issue under a frozen execution profile.
5. Obtain the owner's explicit decision before any full 600 run.

## Owner-authorized routed fixed20 preparation — 2026-10-31

The launch gate now selects profile-specific checks. MCP-only retains its
original eager-tools/disabled-skills checks. Routed admission requires a fresh
native scripted endpoint capture (zero model calls), ordinary terminal/skills/
deferred inventory, the actual staged plugin payload with `checkpoint:false`,
a refused `memo notes` detour and one synthetic connected document write with
persisted state and independent log. Existing app/crash/recovery checks remain
mandatory. The installed 2.3.10b1 memory product is unchanged; staging loads only
the repository-pinned execution plugin without replacing that installed package.

New task configuration: `.atsys/tasks/dolphin-routed-fixed20.json`. It uses a
separate private `routed-fixed20-20261031-v1` condition and MEM output directory,
a USD10 incremental API ceiling, one durable launch intent and inspect-only
retries. The wrapper counts saved executions and grades and writes a Markdown
terminal report plus a machine outcome, including partial/failure outcomes.
Independent validation still rejects missing evidence or control regressions.
Preparation is not submission or a new score. Full600 remains unauthorized.

## Routed fixed20 v3 result — 2026-10-31

AtSys `task-745978af-98a8-455c-b97b-c75e851f6076`, completed and independently
validated: **12/20 passed, 9 recoveries, 0 control regressions**, API cost
USD 0.076858 (judge only; reader on subscription). Report:
`specs/048-dolphin-execution-readiness/atsys/routed-fixed20-v3-report.md`.

Compared with the MCP-only fixed20 pilot (13/20, same IDs, models and memory):
routed passed morgan/152 and morgan/162 that MCP-only failed, and failed alex/102,
alex/132 and morgan/129 that MCP-only passed. None of those three involved a
refused detour; all ended without the required write: alex/102 wrote its PR
review in the answer without `review_pr`, alex/132 wrote the note in the answer
without discovering `create_doc` through deferred tool search, and morgan/129 did
not book after failing to find the travel policy. In this benchmark profile the
request-specific route note (which names the connected write tool) is disabled to
keep the user turn byte-identical, and app tools are deferred rather than eager.
Delivering the route note through the system prompt, or keeping connected app
tools eagerly visible while local tools remain, is the next measured change.
One 20-task run per condition is small and post hoc; differences of one or two
tasks are within run-to-run variation and are not a claim either way.
