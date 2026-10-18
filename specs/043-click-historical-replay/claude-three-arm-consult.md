# Claude three-arm: explicit graph-consult diagnostic

2026-10-18; second distinct protocol, not a retry of a failing arm. Same parent,
task, frozen grader, exact installed AtMem wheel and upstream Cognee pin as
claude-three-arm.md. All three new sessions; no reuse of previous native score.
No product changes, task/reference hints or grader feedback supplied to models.

The first comparison completed all three arms, but neither graph was used despite
being present in Claude's actual tool inventory. Its three results remain
separate. It cannot establish a graph-mechanism comparison. Also, the sandbox
launcher generated .codex temporary files in candidate trees and replaced TMPDIR.
The first raw scope-violation flags remain unchanged, not silently reclassified.

This protocol changes only host integration: graph arms must call a graph tool
successfully before workspace commands are enabled, with identical instructions
in both. This measures explicit consultation, not automatic adoption. No memory
has only workspace_command, as before. Internal launcher artifacts now live
under the already-declared .solver-tmp exclusion, and the confined shell exports
workspace-local TMPDIR explicitly. Do not exempt arbitrary candidate files.

Claude Code 2.1.281, claude-opus-5-5, medium effort, subscription OAuth, fresh
configuration directories, no native tools or custom hooks/skills/memory.
Builtin agents-md plugin was listed in the prior init but no target CLAUDE.md
exists. MAX_THINKING_TOKENS=0 is requested, but the first target runs nevertheless
reported 620/569/595 thinking tokens. Therefore do NOT claim thinking is disabled;
report actual usage for this run. No additional model probe or adaptive tuning.

Same 240-second, 30-tool, 500000 audited input+output caps; same offline sandbox,
MCP inventories, preparation controls and protected event capture. Prepare and
freeze all three before models; grade only after all three terminate. Every
attempt counts, even failed graph uptake, timeouts and scope violations.
Report full suite counts, graph calls/errors, actual model, token components,
wall/index/setup times, independent functional versus budget success. Aggregate
input counts cache read and creation once, from terminal Claude usage only.

One reused task, one attempt per arm, fixed order native/Cognee/AtMem: no causal,
statistical or multi-repository superiority claim. Preserve both comparisons
and the zero-dispatch failed preflight in the final evidence archive.
