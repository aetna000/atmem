# Cross-repository preflight — recorded progress, no model scores

The familiar Click five remain retired from further scored tuning. This work
executes the external plan rather than changing the source pack again. The
50%/exact-20% goal and equal-or-better quality requirement remain unachieved.

## Prospective metadata selection

Pinned official task revision: `3d07b464b7b311a0cbfb5ed5b2d8a3b96f84a33d`.
Pinned task tree: `39df60edb3d9e709c7f6c19516c1d4b1fa3a8d50`.
Seed: `atmem-repository-disjoint-preflight-20261017-v1`.
Order each repository's complete candidate pool by SHA-256 of seed/NUL/repo/
NUL/instance ID; take exactly two. The selection is retained BEFORE fetching
selected task metadata. No failed row was replaced or model outcome consulted.
Selection SHA-256:
`cbeca26c63db27d122461b436e9a96792f06a3bebae6c1e70a0e4e802dd9e2f5`.

| Authentic catalog task | Metadata/recipe identity | Image registry metadata | Runtime control |
|---|---|---|---|
| marshmallow-code__marshmallow-1229 | verified | immutable amd64 digest resolved | shell/interpreter and v2 parent/reference passed |
| marshmallow-code__marshmallow-1810 | verified | immutable amd64 digest resolved | not attempted |
| psf__requests-1327 | verified | immutable amd64 digest resolved | not attempted |
| psf__requests-4356 | verified | immutable amd64 digest resolved | not attempted |
| pylint-dev__astroid-934 | verified | immutable amd64 digest resolved | not attempted |
| pylint-dev__astroid-1616 | verified | immutable amd64 digest resolved | not attempted |

This is a metadata feasibility sample, not yet an eligible scoring pool.
Only `task.yaml` and `Dockerfile` were fetched; Git blob identity and SHA-256
are checked. No external gold patch, hidden test patch, hint or problem statement
was opened. Actual manifests retain upstream split/dataset membership; catalog
counts do not imply one dataset split or contamination-free tasks.

Public metadata artifacts live in
`/Volumes/MEM/AtMem-Code-Replay-20261017/cross-repository-preflight-v1`.

## One constrained amd64 execution control

All six recipes require linux/amd64; the current Docker worker is aarch64,
2 CPUs and about 4 GiB RAM. Internal macOS storage had about 13 GiB free.
Registry layers are roughly 1 GB compressed per selected image; pulling all
six without resource qualification would be unsafe.

Only the first preselected image was pulled, at immutable digest
`sha256:3ea6d8d3b8ad25509c6058af273c8f7e1703c5584cae8516d16c02639d5253b6`.
The pull completed in 46.32 seconds under the 180-second / 8-GiB host-free guard.
One task-owned container ran without mounts/network, with read-only root,
capabilities dropped, no-new-privileges, 1 CPU/512 MiB/64 PID limits and a
64 MiB noexec/nosuid/nodev tmpfs. Fixed `uname` and isolated standard-library
queries observed `x86_64` and Python 3.9.21 on Linux. No repository scripts,
tests, model or owner credentials were supplied. The temporary container was
removed; the pinned image stays cached for later qualification.

Docker reports image `Size=987240808` bytes. This field alone does not establish
the actual unpacked host disk footprint; do not label it that way. Observed free
space after subsequent local tests is about 8.6 GiB, close to the guard, so no
additional images are pulled. Runtime artifacts are in
`/Volumes/MEM/AtMem-Code-Replay-20261017/cross-repository-runtime-control-v1`.
This proves only shell/interpreter compatibility for this image under constrained
emulation, NOT repository dependency, parent/reference or solver qualification.

## Implemented neutral boundaries and exposure receipts

- `external_catalog.py`: identity-only stable sampling, pinned Git tree/blob
  verification, restricted metadata fetch and explicit failed/unqualified rows.
- `source_policy.py`: source-only merge over trusted regular-file snapshots,
  with explicit per-repo roots instead of `src/click/`. Handles additions and
  deletions without trusting mutable Git HEAD/status. Candidate test edits never
  replace frozen evaluator tests, including tests nested within a package.
  Out-of-scope configuration edits are rejected. Secure filesystem capture and
  official task-worker integration still need wiring; this is not a full runner.
- Code MCP: separate hash-bound initialize/tools-list PREPARED and WRITTEN
  audit events. Stream write is recorded only after successful flush. These
  are not client acknowledgments or proof of model-visible tool exposure.
  No raw request IDs, repository contents or caller arguments enter guidance.
  Ordinary memory MCP behavior remains unchanged.

208 local replay/MCP/packing/audit checks pass. The source-boundary tests caught
and corrected an unsafe-root exception-path bug before any integration run.
No inference was used for these checks. No remote CI or publication is claimed.

## Still required before the comparison

1. Task license/environment and upstream parent-fail/reference-pass qualification.
2. Secure source capture and official grader integration using the new boundary.
3. Matched solver access to the qualified target runtime without Docker/socket,
   owner filesystem or evaluator leakage; the host AtMem interpreter is separate
   from the task's older Python environment.
4. Actual host exposure/uptake and complete-usage qualification, especially at
   resource stops. Partial counters remain unknown for full-total comparisons.
5. Frozen validation candidates, repository-disjoint confirmation and execution.

No external coding solve or new guidance-model probe has run. No token-saving,
quality, latency or research-publication result is inferred from preflight.

## Parent/reference control v1: resource stop before execution

The next qualification stage fetched only the first selected task's pinned
evaluator script, reference patch, hidden test patch and expected-test metadata,
plus pinned upstream parser/grading sources and their license. These are retained
in internal protected evidence, not the public metadata directory or solver
context. Hints and the problem statement remain unfetched. This supersedes the
metadata-stage-only fetch description above; no evaluator content is exposed here.

The adapter and isolated worker are implemented, with six focused fixture tests.
Both planned dispatches stopped at `host_free_space_below_8GiB` before either
worker executed. Parent and reference therefore have no test outcomes. The task
is **unqualified**, not a failed coding attempt; solver calls remain zero.
Evidence run: `external-reference-control-v1-20261017`. Host free space was
subsequently checked at about 7.2 GiB. The 8 GiB guard has not been lowered.

Retain this attempt. Any later execution requires an explicitly recorded new
control version using the same preselected task, not overwriting v1 or selecting
a replacement based on outcomes. Resource recovery and secure source/solver
integration remain prerequisites to any cross-repository performance claim.

After adding the qualification adapter, the complete local replay/MCP/packing
suite passes: **214 tests**. Task inventory and tracked-file whitespace checks
also pass. The CI definition now includes qualification fixtures; no remote CI
execution is claimed. These checks do not establish upstream runtime success.

## Stopped-workspace capture boundary

`source_capture.py` now supplies the previously missing descriptor-relative
POSIX filesystem reader. It requires an explicit stopped-writers assertion,
rejects symlinks, hard links and special files, enforces file/entry/depth/total
budgets and checks identities before/after reads. Only top-level Git metadata
is excluded; configuration changes remain visible to source-policy enforcement.
The caller must supply a trusted root and quiesce all writers: this routine does
not establish process termination or provide a live atomic filesystem snapshot.

Eleven capture fixture cases plus fourteen source-policy tests pass, including
mid-read mutation, a new entry during capture, and candidate-test exclusion from
frozen grading. This boundary is not yet wired to a qualified external solver.
No new scored task, qualification-container retry or product pack change occurs.
Disk guard recheck: about 7.0 GiB free; the prior stop remains retained.

Combined replay/MCP/packing regression run: **225 passed**. The subsequent
root-path identity check also passes all eleven focused capture cases. Task
inventory and tracked whitespace checks pass. CI includes these fixtures but
has not been run remotely. Performance acceptance remains unproven.

## Resource recovery and explicit v2 control

300 exact retired benchmark directories have been archived to encrypted MEM
bundles, verified in fresh processes, checked against current inventories and
checked for open handles before removal. They remain recoverable; archive keys,
the active vault and current dependencies were not removed. Host free space is
now about 8.10 GiB. See `2026-10-17-benchmark-resource-recovery.md` for byte counts
and retention evidence. Historical scores and usage remain unchanged.

The separately recorded same-task v2 control completed under
`external-reference-control-v2.md`; this preserves v1's two zero-execution space
stops. No coding model or replacement task is involved. Updated runner checks
preserve output through cleanup/parser failures and script timeouts; 236 local
checks pass.

| First Marshmallow control | Target checks | Regression checks | Controller |
|---|---:|---:|---|
| Parent | 0/8 pass; 8 observed failures | 61/61 pass | exit 0; no cleanup failure |
| Verified reference patch | 8/8 pass | 61/61 pass | exit 0; no cleanup failure |

All 69 statuses are parsed in each attempt; no regression skips. Upstream
resolution is `RESOLVED_NO` versus `RESOLVED_FULL`. The optional test-exit marker
is absent in both logs; the pinned upstream parser finds test results and grades
their actual statuses. No test/patch/parser success criterion was rewritten.
Evidence run: `external-reference-control-v2-20261017`, qualified within scope
`first_task_parent_reference_control_only`, solver calls zero. Other tasks,
secure solver/runtime integration, exposure/full-usage and efficacy remain open.

Both control versions, scratch-reclamation audit and full harness-source snapshot
are archived under `MEM/AtMem-Code-Replay-20261017/protected-external-reference-v2`.
Four encrypted bundles round-trip and recover 17 events in a fresh process
without the original vault; recovered source bytes match their retained hashes.
Keys stay internal. This is retention verification, not independent replication.

Subsequent source-to-grader controls and public-source export pass for the first
task; see [external-source-boundary.md](2026-10-17-external-source-boundary.md).
This advances source eligibility/assembly, not model performance. Other task,
native runtime, host exposure and complete-accounting gates remain open.
