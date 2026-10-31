# Implementation plan

## Context and constitution

Python 3.10+, pathlib/JSON/SHA-256, upstream MCP SDK and pinned DolphinBench.
Use `benchmarks/dolphinbench` orchestration; do not change product retrieval or
upstream fixtures. The constitution requires separate evidence of model input,
tool activity and independent outcomes, explicit egress, immutable provenance,
and honest synthetic-vs-benchmark claims. No authority/schema migration occurs.

## Architecture

- `execution_profile.py`: MCP-only supported Hermes config; outgoing tool audit.
- `readiness.py`: frozen configuration, immutable receipt files, artifact digests,
  freshness, pilot evidence and admission at pilot/full/adapter boundaries.
- `safe_runner.py`: prevent upstream `_apps` resetting existing app evidence;
  journal intent and raw state/log snapshots, refusing uncertain repetition.
- `qualify_execution.py`: real upstream bridge/SDK synthetic mutation and crash
  qualification; produce raw durable evidence and bound qualification receipts.
- `pilot_readiness.py`: verify selection, report original/new scores and regressions
  and create pilot evidence only when all 20 rows and accounting are available.
- Existing adapter, gateway and launch entry points invoke the common gate; no
  receipt-less legacy path may dispatch scored cases.

## Frozen identities

One JSON file pins actual input files with role/path/SHA-256, three memory
checkpoint roles, wheel, upstream manifest, source manifest, fixed selection,
reader/judge settings and budget. Profile/runtime verification occurs before
provider forwarding. A receipt binds the whole config, exact artifact bytes and
timestamp. Raw diagnostics remain distinct from passing pilot receipts. Local
operator control is trusted; claims do not imply third-party attestation.

## Phases and test strategy

1. Spec/plan/tasks analysis and durable instructions.
2. Profile and boundary gate with bad-tool and changed-input tests.
3. Actual synthetic mock app state/log round trips and crash after mutation.
4. Pilot report/runner and complete-vs-partial controls; do not invent unavailable
   frozen memory or private configuration. Run live pilot when storage is present.
5. Integrate gates into full and legacy dispatch; subprocess tests show no provider
   call/output creation without readiness.
6. Claude Opus 5.5 medium review; fix findings; commit/push exact results and blockers.

## Historical operational constraint (superseded for the current repair)

The original `/Volumes/AtMemDolphin` workspace is currently unmounted. Code,
synthetic qualification and pilot tooling can be completed. Live memory-backed
pilot/frozen run config require the authentic checkpoint/key material; missing
material is an explicit blocker, not a passing receipt. No full run is launched.

Owner amendment: new 20 selection and source-bound AtSys exact-command launcher; no changes to reader60-turn cap, memory, retrieval or judge. Old condition/receipts are retained and invalidated for the new pilot.


## Bounded recovery amendment — current implementation scope

`pilot_recovery.py` independently verifies retained historical bytes, reconstructs
129 without dispatch, creates immutable epoch/condition transitions, imports
completed executions/grades, carries SQLite accounting via a disposable staged
copy and backup, and enforces persistent intent/lock boundaries. `readiness.py`
keeps normal admission and additionally checks inherited evidence at forwarding.
`pilot_readiness.py` skips saved executions/grades and validates recovery receipts
in reports. `recovery_supervisor.py` verifies bounded coding/test/qualification
handoffs without executing workload commands. Root performs private/MEM writes
outside the workspace coding sandbox. The historical read-only/no-repair retry
policy is superseded within this amendment; scientific configuration is fixed.
No product, grader, fixtures, upstream or model-setting changes occur.
Tests use real upstream export/validation on synthetic and retained evidence;
root performs installed ARM product qualification after review. See
[recovery-implementation.md](recovery-implementation.md) for current limits and CLI.
