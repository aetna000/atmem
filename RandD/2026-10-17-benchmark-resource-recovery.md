# Benchmark resource recovery, not another product candidate

The first external parent/reference control did not execute: both dispatches
stopped below the unchanged 8 GiB host-free guard. No model solve or upstream
test outcome was observed. Familiar Click tasks remain retired from tuning.

## Recovery scope

Archive only explicit retired benchmark directories, never the owner workspace,
credential store, active evidence vault, archive keys or current runtime. Three
exclusive plans select 260 old Click grader directories and 40 benchmark-state/
diagnostic directories. The initial group occupies 1,012,992 KiB; two additional
groups occupy 30,948 and 91,836 KiB. These are measured allocated directory sizes,
not a promise of reclaimed filesystem space.

`benchmarks/code_replay/scratch_retention.py` uses the existing signed,
recipient-encrypted framing. Compressed original trees and inventories are
encrypted; only keys and protected manifests remain internally. Archives are
under `MEM/AtMem-Code-Replay-20261017/protected-retired-scratch-v{1,2,3}`.
The utility never deletes sources. Before reclamation, require separate-process
archive-only recovery, matching current source inventories and an open-handle
check. Preserve all historical score/usage outcomes unchanged.

All three batches recovered successfully in separate processes: 275, one and
24 archives, respectively. The main batch verifies 103,611 entries; the other
batches verify 21 and 121. Before reclamation all 300 current inventories matched
the archived inventories and a repeated global open-handle scan found no match.
Only the 300 exact validated directories were removed. They remain recoverable
from the encrypted archives; keys, active vault and current dependencies remain
internal and untouched.

Measured host free bytes rose from 7,490,252,800 to 8,702,533,632 (about 8.10 GiB).
Protected audit run: `retired-scratch-reclamation-v1-20261017`. This is recovered
scratch capacity, not deletion of benchmark evidence or a changed score. V2 of
the same-task parent/reference control completed: parent has 8/8 observed target
failures and 61/61 regression passes; reference has 8/8 target passes and 61/61
regression passes, no skips. Controller exits are zero with no cleanup failure.
This qualifies only this task's parent/reference environment, not any solver,
AtMem efficacy, other task, or complete model-usage path. Solver calls remain zero.

## Control runner correction before any new dispatch

Preserve raw worker output when exact-container cleanup fails or times out.
Because Docker `--rm` can already remove a completed worker, verify absence
using an exact-name query rather than treating every nonzero removal as failure.
Record output size/truncation and enforce the output cap even for fast exits.
Retain partial stdout/stderr on script timeout; parsing errors must not discard
the captured streams. Timeout/cleanup/parsing failure cannot qualify a task.

V2 is a prospective, same-task control, not a rerun selected after seeing a test
result. It requires the two retained v1 zero-execution resource stops, has a new
exclusive evidence/state identity, and retains unchanged task/image/test/grading
identities and budgets. See `external-reference-control-v2.md`.

Validation: 236 local replay/MCP/packing checks pass, including fresh-process
scratch recovery without the original source and tamper rejection. Task inventory
and tracked whitespace checks pass. These are harness checks, not evidence of
external task qualification, model benefit or remote CI success.

Retention checkpoint: four control/reclamation/source bundles in
`protected-external-reference-v2` recover 17 events in a fresh process without
the original vault. All retained source bytes match their hashes. Archive keys
stay internal. The complete control outcome remains separate from model efficacy.
