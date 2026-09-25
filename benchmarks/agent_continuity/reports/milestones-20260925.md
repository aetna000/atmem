# Continuity milestones M1/M2 — 2026-09-25

**Implemented and locally tested: pinned native retail tool parity and isolated
current AtFlows HTTP observations. Not implemented: complete autonomous retail
continuity execution or four-arm public evaluation. No production gain claimed.**

## Release priority and ownership

Continuity qualification now precedes new Memory Health work in AtMem's product
and release roadmaps and new storage/MCP/intelligence tracks in AtFlows' roadmap.
No package version, published artifact, installed daemon or runtime default changed.
Branches remain `feat/agent-continuity-benchmark` and `feat/continuity-observability`.
This milestone's source/documentation changes are local pending commit/review.
The original 61-cell smoke bundle and current-product artifact locks are preserved.

## What ran

| Check | Result | Meaning |
| --- | --- | --- |
| Python foundation, retail, observation and existing task-state suites | 117 passed in 137.91 seconds | Local targeted regression; no remote CI claim |
| AtFlows dedicated suites | 6 top-level tests passed, including wrapper for 6 existing characterization checks | Existing behaviours plus unmodified-server HTTP fixture and tripwire checks |
| AtFlows server TypeScript check | Passed | Existing server project typecheck |
| Whitespace and Python compilation | Passed | No installed-artifact/full-release claim |
| Claude M1 and M2 read-only source reviews | Approved after corrections | Review scope/limitations in canonical review record |
| Native vs separate-process retail pilot task 0 | 5/5 tool responses identical; final DB identical; zero tool errors; state changed | Evaluator reference-action parity, not agent decision quality |
| AtFlows HTTP fixture | 2/3 planned distinct spans retained; replay rejected once; no unexpected spans or attribute mismatches | One span deliberately never sent; **not** a claim of 67% real-product capture reliability |

The retail test uses Sierra's native tools at immutable commit
`b7ea9074c1cba482b30687fecdb5c8425fd6f619`. It does not reimplement their business
logic. Only wall-clock `ToolMessage.timestamp` is excluded from response parity.
The model, simulator and policy-following behaviour are not evaluated by replaying
reference actions. Task 0 was already designated design-exposed in the locked pilot.
No held-out task was executed or exposed as a development expectation.

The HTTP fixture uses AtFlows 0.1.2's unchanged `/v1/traces` route on fresh ephemeral
loopback listeners. No credential or Origin header is sent; this says nothing
about the separately authenticated dashboard. Missing usage/cost on the two stored
fixture rows become zero in current AtFlows. The evaluator retains that observation
but labels usage and cost accuracy unknown; no model call occurred. A duplicate span
is rejected, not given an idempotent acknowledgement. Those are baseline gaps,
not hidden fixes or new product features.

## Evidence and reproduction

[Publishable fixture bundle, currently local](../results/offline-milestones-20260925/SHA256SUMS.json):

- `retail-tool-parity.json`: native/wrapped tool responses, source and environment
  digests, independently anchored source lock, errors and explicit claim limits.
- `atflows-http-schedule.json`: delivered/replayed/dropped fixture inputs.
- `atflows-http-report.json`: raw server observations, harness-owned coverage,
  current tracked-source pin, Bun version and dependency limitations.
- `LICENSE-tau2.txt`: upstream MIT notice for the small public pilot output excerpt.

Commands and optional benchmark dependencies are in the [README](../README.md).
Python ran in the existing temporary benchmark venv (Python 3.12.2), which has
system-site-package visibility; this is **not** a hermetic clean-install test.
The final replay enforces upstream's declared mandatory dependency ranges and
records actual versions, including LiteLLM 1.82.6 and psutil 7.2.2. Earlier local
development replay used incompatible LiteLLM metadata and is not the final bundle.
Installed AtMem/AtFlows artifacts remain unchanged. Bun was 1.4.2; installed
node_modules bytes are not independently hashed. Full transitive/environment
qualification remains required before public agent evaluation.

The compatibility-only `tomllib`/`tomli` import fallback was added after the first
M1 approval and included in closeout review. AtMem's existing `pyproject.toml`
already declares `tomli>=2.0` for Python <3.11; no package dependency changed.
All 117 tests were rerun on Python 3.12.2 after the change. Python 3.10 collection
behaviour is **unverified in this milestone**. The optional upstream retail run
requires Python 3.12–3.13; this is not a new AtMem base-runtime requirement.

Original temporary output, including server fixture databases and development
runs, is temporarily retained at `/private/tmp/atmem-continuity-milestones.1xFMCM`.
That OS-managed temporary directory is not durable evidence; the checksum-covered
repository bundle above is the evidence selected for version control. Only allowlisted
public report files were copied into Git; auth files/databases and incidental
server logs are not exported. The probes reject network attempts on guarded paths
and strip provider credentials/dotenv. They are tripwires, not OS sandboxes.

## Spec coverage and remaining work

Completed bounded substeps: AtMem T001a/T005a/T007a/T013a and AtFlows T002a.
All original FR/SC requirements remain mapped to parent tasks. Existing G0/G1
partial work does not silently advance G2 or G5. No constitutional requirement,
encrypted-evidence guarantee or authority boundary was relaxed.

Next implementation milestones:

1. Full native retail agent/user-simulator orchestration, durable simulator state
   and upstream no-fault equivalence—not just tool replay.
2. Integrate current AtMem context/evidence APIs and actual workflow AtFlows
   telemetry; execute four configurations with equal runtime/policy information.
3. Complete independent usage/resources, stale/revoked context and standalone
   evidence checks; final-source repeated harness qualification.
4. Approved-budget pilot, then frozen preregistration and held-out evaluation.

Model proposal `gpt-4.1-2025-04-14` for agent and user simulator was approved in
conversation. At this M1/M2 checkpoint no benchmark provider call had been made.
Subsequently the user approved a USD20 total inference cap; see
`../pilot-authorization.json` and the M3 sections of the canonical milestone review.
A spending cap alone does not close the remaining implementation
gates. No new production benchmark number, release, merge, deployment or push is claimed.
