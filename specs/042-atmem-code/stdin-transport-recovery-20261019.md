# Infrastructure-only stdin recovery

The full-query screen stops after seven terminal cells and an eighth complete
model capture. Native Django's stdout, usage and final patch are already retained.
The next SSH worker blocks until its 420-second transport deadline. Diagnostics
show no running evaluator container and the matching Python job loader waiting
on Linux `read(0)`; two older benchmark loaders are stranded the same way.
The previous `json.load(sys.stdin)` requires EOF across Windows SSH/WSL pipes.

Preserve the stopped campaign first. The separate encrypted MEM snapshot
`swebench-full-query-context-screen-20261019-transport-stop` independently
recovers all six evidence runs and eight original model streams. Do not overwrite
that snapshot, manufacture usage, restart a captured model or choose a new task.

The allowed controller delta is exact: parse one newline-framed JSON job with
`json.loads(sys.stdin.readline())`, append its newline at the sender, and give
descendants explicit EOF via `/dev/null`. The trusted program/payload remain
identical. Source comparison must reject any other controller change; worker,
tool, context and Cognee helper sources stay byte-identical to the execution lock.
The wheel, solver/model/effort, task order, budgets, authority and official
grader do not change. A real child test keeps the sender's pipe open and must
still finish, including inherited stdin EOF; a Windows/WSL probe must pass too.

`tools/recover_swebench_grade.py` validates complete original captures, terminal
rows and frozen source before doing anything. It may terminate only owned old
benchmark EOF loaders verified blocked on fd0. No data file, owner process or
container is removed. Apply the unchanged official grader to the original
captured patch, retain its result whether successful or not, and derive the
terminal dictionary from the frozen controller expression. Mark this grading
as recovery after a transport stop, not a new model attempt or an unqualified
successful original transport. Never retry a bad grade to pass.

Then use the existing explicit `--continue-unstarted` path for the two remaining
scikit-learn cells. Retain both execution locks and the stop/recovery history.
No started cell is rerun. Final reporting must disclose this infrastructure
recovery and separately archive/verify the completed campaign. A seven-minute
transport stall is not counted as a model's agent execution time or hidden as
zero; its raw stop remains available alongside product/solver measurements.
