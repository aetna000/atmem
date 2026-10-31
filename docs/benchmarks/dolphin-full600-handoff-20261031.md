# Handoff: full 600-task DolphinBench run with AtMem routed-v4 (verified/source-linked standing facts)

Prepared 2026-10-31 19:30 AEDT for the next agent (Codex). Owner: Javad. The owner has
authorized one full 600-task run through AtSys. Read this whole file before acting.

## 0. Comply with the repository first

You are working in the AtMem repository. **Follow `AGENTS.md` exactly**, in particular
"DolphinBench restart and launch prerequisites". Before any launch, read:

- `AGENTS.md`
- `docs/benchmarks/dolphin-lessons-and-readiness.md` (lessons L01–L22)
- `docs/benchmarks/dolphin-action-guard-20261031.md` (what changed today, results, limits)
- `specs/048-dolphin-execution-readiness/{spec,plan,tasks,verification,runbook}.md`
- `specs/048-dolphin-execution-readiness/atsys/README.md` and `AUTOMATIC-RECOVERY.md`

Hard rules (non-negotiable): never patch fixtures or grader inputs; never grant real
Notes/GitHub/Google access; never disable benchmark isolation; never change the frozen
reader/judge/memory settings; never replay or reset a possibly completed action; never
delete evidence; never invent charges; report the result as self-tested, not official.
The published 390/600 stays the public result until reviewed.

## 1. Where everything is

| Item | Location |
| --- | --- |
| Code under test | worktree `/Users/javadtaghia/gitlab/atmem-action-routing-i3`, branch `feat/dolphin-action-routing-i3`, pushed to `origin/feat/dolphin-action-routing` (PR aetna000/atmem#28) |
| Profile | `dolphin-routed-v4` in `benchmarks/dolphinbench/execution_profile.py` |
| Standing-fact stores (pinned inputs) | `benchmarks/dolphinbench/standing_facts/{morgan,alex,riley}.json` |
| Private readiness base | `~/.local/share/atmem-dolphin-readiness-20261026/` |
| Validated condition | `condition-routed4-fixed20-20261031-i3.json`, receipts in `routed4-fixed20-20261031-i3/receipts/` |
| Validated 20-task pilot | `/Volumes/MEM/atmem-dolphinbench-20261020/routed4-fixed20-20261031-i3` — 17/20, 14 recoveries, 0 regressions, AtSys `task-a4560b4a-0fab-4515-aa72-b76713efa446` |
| Full-run worker / validator | `specs/048-dolphin-execution-readiness/atsys/run_full_routed.py`, `validate_full_routed.py` |
| Full-run AtSys config (prior attempt) | `.atsys/tasks/dolphin-routed4-full600.json` |
| Stopped full attempt (do not reuse) | `/Volumes/MEM/atmem-dolphinbench-20261020/routed4-full600-20261031` (AtSys `task-b1d19f14-…`, stopped by owner) |
| Per-action report | `scripts/report_dolphin_per_action.py` |
| $0 subscription reconciliation | `scripts/reconcile_subscription_failures.py` (owner-authorized) |
| Canary option | `scripts/launch_dolphin_readiness.py --stage pilot --canary TASK` |

Published package note: AtMem **2.3.11b1** (PyPI/npm beta/GitHub prerelease) contains the
same action-guard and standing-facts code with more honest wording ("source-linked,
unverified interpretations; check the source"). The benchmark loads the guard and facts
from the **i3 worktree**, not from the installed package, and the frozen memory product is
the **2.3.10b1** wheel. The 17/20 was measured with the i3 wording. Do not mix the two.

## 2. Things that will bite you (all happened today)

1. **Receipts expire 24 h after issue and are re-checked at every task boundary.** The i3
   receipts were issued ≈ 15:00 AEDT 31 Oct, so they expire ≈ 15:00 AEDT 1 Nov. A run that
   is still going at expiry fails mid-run. The 600 run takes ≈ 8.4 h (0.84 min/task).
2. **One-launch intent blocks reuse.** `routed4-fixed20-20261031-i3/receipts/atsys-full-launch-intent.json`
   belongs to the stopped attempt; `run_full_routed.py` refuses another launch with that
   receipts folder. Do not delete it; preserve it.
3. **Stopped attempt has an uncertain record.** `routed4-full600-20261031/tests/*/004.inflight`
   was interrupted. Never replay or reuse that output; a new run needs a new output path.
4. **`atsys task stop` did not kill the benchmark process group.** After any stop, check
   `pgrep -fl routed4-full600` and terminate the launcher's process group if needed.
5. **Running `hermes` with a fresh `HERMES_HOME` rewrites the shared launchers** in
   `~/.hermes/hermes-agent/.hermes/bin/`. Use only the harness runtime invocation. Verify
   `env -u HERMES_HOME hermes --version` at the end.
6. **Do not edit pinned files in a worktree while a run uses it.** Admission re-hashes the
   pinned sources at every task boundary; an edit aborts the live run. Do new work in
   another worktree.
7. **Do not run qualification while a run is live.** Qualification stages the shared
   native runtime (`~/.local/share/atmem-dolphin-readiness-20261026/native`).
8. **A single subscription 502 blocks the report.** One reader call can end as
   `subscription_failure_usage_unknown` ($0 receipt, usage unknown). The frozen accounting
   then refuses the report. The owner authorized `scripts/reconcile_subscription_failures.py`
   for exactly this case (it preserves the original accounting); then run the frozen
   `pilot_readiness --report-only` path (or `--stage full` equivalent) and let AtSys retry
   inspect-only. Never reconcile anything else.
9. **MEM is ExFAT.** Every small file costs 128 KB and macOS writes `._*` sidecars; ignore
   them. 20 tasks ≈ 568 MB, so 600 ≈ 17 GB. Free now: ≈ 25 GB. Do not delete benchmark
   folders; `campaign-atmem-2310b1-judge-only-20261022` is the published baseline.
10. **Codex sandbox.** The exact-command worker needs the controller's private paths and
    MEM; the benchmark agent keeps its own native sandbox. Do not loosen the latter.
11. **`codex exec` with a piped stdin waits for input** — use `< /dev/null`.

## 3. Budget and resources (checked 31 Oct)

- Judge (paid, OpenRouter Azure-only Sol/medium): ≈ $2.90 expected for 600 (pilots cost
  ≈ $0.096 per 20). Condition cap $20. Owner added a card to OpenRouter.
- Reader: Luna/high via the owner's ChatGPT subscription (≈ 3,700 calls; $0 API).
- Embeddings/memory: local Ollama and frozen local memory.
- Time ≈ 8.4 h; AtSys worker/task timeouts set to 86,400 s.

## 4. Recommended path (fresh, clean)

Fresh receipts give a full 24 h window and re-validate the condition right before the run.

1. Read §0. Confirm `git -C /Users/javadtaghia/gitlab/atmem-action-routing-i3 status` shows
   no tracked changes and HEAD contains `b2246bf`.
2. Create a new descriptor/options for a new identity (e.g. `routed4-fixed20-20261101-v5`)
   by copying the i3 descriptor and options (profile `dolphin-routed-v4`, options
   `execution_profile: dolphin-routed-v4`).
3. Qualify with zero model calls, exactly as in `specs/048-…/verification.md` (latest
   sections): `qualify_routed --profile dolphin-routed-v4` and `qualify_execution` through
   the product-python bootstrap, then `freeze`, `issue_qualifications`, `admit(...,'pilot')`.
   Required profile checks: `FACTS_CHECKS` (ordinary inventory, plugin loaded, checkpoint
   held once, pending reminder shown, user boundary unchanged, route note and standing
   profile in the system prompt, fact_search visible, write/state/log agree, detour refused).
4. Run a one-task canary (`--canary morgan/023`) into its own output. It must save and grade.
5. Run the fixed 20-task pilot through AtSys under the new condition (copy
   `.atsys/tasks/dolphin-routed4-fixed20-i3.json` with new paths). It must be
   "Completed and validated". This writes the `pilot.json` receipt that full admission needs.
   Expect ≈ 17/20 (morgan/085 and morgan/130 are fixture limitations; alex/139 is the open miss).
6. Create a new full config by copying `.atsys/tasks/dolphin-routed4-full600.json` with the
   new condition, receipts and a **new output path** (e.g. `routed4-full600-20261101-v5`) and
   a new summary path. Run `atsys doctor`, then `atsys task submit` **once**. Open
   `atsys task watch <id>` in a terminal for the owner.
7. When it ends: if accounting is blocked by a $0 subscription failure, apply the
   reconciliation tool (§2.8). Let AtSys's inspect-only retry produce the summary and run
   `validate_full_routed.py`.
8. Produce `scripts/report_dolphin_per_action.py --run-dir <output>` and report per action
   (reads and writes separate; failure classes), plus totals versus the published 390/600.

Alternative (only if launching before ≈ 06:00 AEDT 1 Nov): reuse the i3 condition and
receipts. You must first move the stale `atsys-full-launch-intent.json` into the stopped
attempt's folder as preserved evidence (record that in `verification.md`), use a new output
path, and confirm the 8.4 h run ends before the receipts expire.

## 5. What to report back

Branch/commit, condition identity, receipts timestamps, AtSys task ids (canary, pilot,
full), validator results, full score with per-cohort and per-action breakdown, API cost,
any reconciliation applied, and limitations (self-tested; one run; fixtures retained).
Do not claim a public or official score.
