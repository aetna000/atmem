# Spec 050 implementation evidence — 2026-11-09

Implementation authorized by owner request to start all specified features.
Execution follows `.agents/skills/speckit-implement/SKILL.md` in task order.

## T001 — complete

- Native/AtMem/candidate comparison definitions, immutable baseline commit,
  synthetic corpus, verification tiers, metric denominators, all seven success
  gates, zero-call default and three-candidate cap recorded in
  `docs/benchmarks/verified-memory-feedback.md`.
- Six bounded synthetic task definitions and hashed corpus manifest under
  `tests/fixtures/feedback/`. No measured baseline or quality result asserted.
- Offline `atmem.feedback.baseline` validates those inputs and refuses changed
  memory, split/chronology leakage, unbounded resources, relaxed gates,
  self-approved authority and self-reported success.
- 31 focused preflight tests passed on macOS / Python 3.12.13 / pytest 9.2.0.

## T002 — initial blocker (historical; remediation below)

Source commit pinned to `d0288be5b3330d2442e3907185b8e9d0958297bb`;
version/OS limitations and exact function paths documented in
`docs/verified-memory-feedback.md`.

Four source-contract probes passed, reproducing normal veto, deny-wins, the
fail-open hook-dispatch exception and argument modification after policy checking.
The latter two are conformance failures against FR-014/015 and SC-004, not passes
of those requirements. Local callbacks simulate effects; this is not installed
host conformance. No installed enforcing version could be qualified from
those initial results. The earlier absent-interpreter diagnosis was incorrect:
the shell launcher uses a present managed Python runtime. Launcher availability
was not a blocker, and no launcher was executed or changed.

Invocation:

```sh
HERMES_SOURCE=/Users/javadtaghia/.hermes/hermes-agent .venv/bin/python -m pytest -q \
  tests/test_feedback_baseline.py tests/test_feedback_hermes_boundary_prerequisites.py
```

Result: 35 passed. No network/model calls, actual tool writes, user-memory
mutation, Hermes launch, production activation, release or paid evaluation.
The only installed dependencies are in this worktree's ignored `.venv`.

Regression invocation added `tests/test_action_guard.py` and
`tests/test_hermes_upstream_contract.py` under the same pinned source environment:
97 passed in 1.94 seconds. `git diff --check` passed. This verifies existing guard
behavior and reproduces source contracts; it does not upgrade the host capability.
The isolated test environment occupies 36 MiB; no training or benchmark outputs
were created.

The initial implementation halted at this prerequisite under the implementation
skill. The owner then authorized its repair; see the candidate evidence below.

## T002 — complete: reviewed boundary and local remediation candidate

Hermes branch `fix/final-tool-policy-boundary`, candidate commit
`1088e06e448bef2af736122a5d424082a57bf548`, lives in the separate
`/Users/javadtaghia/gitlab/hermes-tool-policy-boundary` worktree. The owner runtime
at the base commit is unchanged. Its package metadata is `0.0.0`, so the commit
and five source-file hashes, not that non-distinguishing version, identify the
candidate in `integrations/hermes/patches/final-tool-policy-boundary.json`.

The generic host fix:

- Fails closed on outer pre-tool dispatcher errors in agent and direct-tool paths.
- Adds `authorize_tool_call` after transformations at agent callback and
  registry/connector dispatch, including concrete connector batch entries.
- Checks detached final arguments, refuses mutation/modifying decisions, preserves
  existing vetoes and returns ordinary blocked errors so recovery can retry.
- Handles callback/dispatch errors and timeouts without leaking final-policy
  exception text into result/log output. Calls without a final policy keep their
  native path; legacy transform hooks still fire once.

Canonical Hermes test command is reproduced in the patch README. Result: **467
passed** across seven files, including **40 new boundary cases** with actual
module imports and directory-plugin discovery, on macOS / Python 3.14.7 / pytest
9.1.1. Allowed writes create a temporary effect file; denied/failed writes do not.
The connector transport is a test double; there are no real external writes or
model calls. The source-only historical probes above remain distinct evidence.

Regression proof temporarily restored the two unfixed dispatch files, retained
the new hook registration so the fixture could load, then ran the new cases:
four outer-dispatch-error cases failed, and the 32-case final-policy matrix
failed. Both files were restored byte-for-byte automatically. The recorded
467-pass run uses the fixed versions; source hashes match the candidate commit.

The mail patch applies cleanly to the unmodified base (`git apply --check`) and
reverse-checks cleanly on the candidate. Both checks are read-only. Upstream MIT
license and commit metadata accompany the patch. No live source, launchers,
global Python environment, real memory or benchmark was modified. The isolated
Hermes test environment is 248 MiB and was built by its PM, without model extras.

This completes the T002 version/boundary/OS inventory and prerequisite repair.
T003–T024 remain unchecked. Installed rule-service conformance, source revocation,
atomic approval use, Windows/Linux, full outcome/review/export/UI journeys and
efficacy remain required by their later tasks. No rule activation, deployment,
release, upstream acceptance or universal enforcement claim is implied.

The owner-requested review of Mem0, LangMem, Letta and LangChain/LangGraph is
recorded with primary sources and limitations in `memory-system-comparison.md`.
