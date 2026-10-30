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
| Router | same | Refuses a local route (`skill_view` of apple-notes/github/notion/google-workspace/…, `memo`, `gh`, `osascript`, `imsg`, `open -a`, document `write_file`) when a configured connected application has a write tool for that destination. Explicit local requests ("in Apple Notes") are allowed. The refusal names the routed tool. Bounded to 6 refusals per turn so it cannot loop. |
| Route memory | same (`RouteMemory`) | Records a local route only after an actual tool result shows a sandbox/permission/auth failure, with the result hash and excerpt; later sessions refuse that route even without a connected alternative. Owner-only JSON per Hermes profile. |
| Completion check | same | `not_completed` unless a connected write was accepted (decoded `isError`/`ok:false`/non-zero exit are failures; host untrusted-data envelopes are unwrapped). |
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
| pass | 390 | 37 | **0** |
| traced partial | 43 | 11 | 8 |
| traced zero | 84 | 7 | 2 |
| untraced zero | 83 | 46 | 82 |

- **Notes:** 35/35 untraced Notes-error failures are refused at their first
  detour (`skill:apple-notes`) and redirected to `create_doc`.
- **GitHub auth:** 6/6 untraced GitHub-auth failures are refused at `skill:github`.
- **Completion:** action intent is detected in 83/83 untraced failures; 82 are
  flagged. The unflagged one is morgan/129, whose booking calls were accepted
  but whose backend log was lost (L13), which is the correct verdict.
- **Traced flags are correct:** all 10 traced tasks flagged NOT COMPLETED only
  read data and never made the required write (e.g. `get_pr` without `review_pr`).
- **Regression risk:** 37 passing tasks would have had a detour refused, mostly
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
