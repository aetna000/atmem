# First external parent/reference control — resource continuation v2

This prospectively authorizes one new recorded parent/reference pair on the
SAME first preselected task and immutable image as v1. It is available only if
both protected v1 attempt receipts say `started=false` with
`host_free_space_below_8GiB` and no worker result. No code test or model outcome
was observed in v1. Preserve v1 unchanged, with its original zero-execution
attrition; use a new exclusive state directory and evidence run ID for v2.

All task, evaluator, parser and grading identities, no-network/no-host-mount
boundaries, hidden-material isolation, budgets and qualification requirements
in `external-reference-control-v1.md` remain unchanged. The worker contract
label remains v1; the control evidence run is v2. Freeze the actual driver and
worker source hashes plus this policy text before dispatch. Solver calls: zero.
Never replace this task based on either control's outcome or silently rerun v2.

V2 additionally retains worker output if container cleanup times out or fails.
Cleanup failure is explicit and disqualifies the control. Output sizes and
truncation are recorded; a process that exits between polling ticks cannot
evade the output budget. This is an observation-integrity correction, not a
change to task success criteria, upstream tests or source logic.
The worker also preserves partial stdout/stderr on script timeout and retains
raw output if upstream grading raises. Either condition prevents qualification;
partial test markers cannot override a timeout.

Keep the 8 GiB minimum host-free guard. Reclaim only exact retired benchmark
scratch after recipient-encrypted archive round-trip, fresh-process recovery,
unchanged source inventories and no active writer checks. Keep archive keys
internal; do not remove owner data, original credential stores, or current
solver/runtime dependencies. Recovery is not permission to change grading.
