# Plan: benchmark first, changes second

Status: implementation in progress. Governed by spec.md, the constitution and contract v1.

## Stack and ownership

Python harness in `benchmarks/agent_continuity/`, separate destination process,
durable SQLite test service and append-only evaluator records. Choose and pin a
public checkpoint-capable runtime at gate G0 through demonstrated capabilities,
not brand preference. No new runtime dependency in AtMem's base install.
Selected: LangGraph 1.2.12 and SQLite checkpoint 3.1.1 in a separate benchmark
environment. Current process-kill tests exercise that implementation; public
retail integration and no-fault upstream equivalence remain incomplete.
AtMem adapter uses supported APIs; optional AtFlows adapter emits authenticated
OTLP through existing ingest. Bun/TypeScript AtFlows contract tests stay there.

Proposed harness files: `manifest.py`, `destination.py`, `faults.py`, `oracle.py`,
`runtime.py`, `adapters/atmem.py`, `adapters/atflows.py`, `runner.py`, `report.py`;
tests in `tests/benchmarking/test_agent_continuity.py`. Raw bundles under an
explicit run output directory, no private Home reuse or credentials in exports.

## Gates

1. **G0 protocol**: resolve upstream/runtime commits and licenses; audit existing
   product capabilities and identity mapping; define destination contracts and
   task eligibility. Record selection in `protocol-lock.json` before trials.
   Lock pilot/held-out clusters now, not after inspecting pilot outcomes.
2. **G1 harness**: independent ledger, deterministic fault barriers and negative
   controls pass. No-fault selected upstream suite validates adapter equivalence.
   Require exact per-task outcome agreement on deterministic recorded-response
   replay; preregister native-versus-wrapped stochastic pass-rate tolerance at
   G0. Implement and test metric reporting here, before the baseline report.
3. **G2 current baseline**: freeze artifacts and run all supported current-product
   arms. Unsupported telemetry or state is a reported gap. Save immutable output
   digests and baseline report before changing product or product adapters.
4. **G3 evaluation registration**: pilot determines variance and affordability;
   publish `preregistration.json` before held-out tasks. Insufficient coverage
   leaves the work engineering evidence, not production-level claims.
5. **G4 bounded improvements**: propose gap-specific changes under the owning
   product spec; retain disabled defaults and backward compatibility. Require
   separate implementation approval. Shared harness bug fixes rerun all arms.
6. **G5 paired rerun/report**: freeze new artifacts, execute preregistered held-out
   schedule and publish all cells, uncertainty, regressions and null outcomes.
   Rerun frozen current-product arms as well as preregistered changed arms.
   Never describe one local trial as general production safety.

G4 is optional: current products can enter G5 without modification. No dashboard
or release work is part of these planning artifacts. Subsequent implementation
must satisfy SC-004 and AtFlows compatibility gates before any shipping claim.

## Constitution check

Authority remains separate from ranking/telemetry; host owns execution. No live
user fault injection or undisclosed egress. Exact evidence capture, scoped access,
redacted publication, explicit profiles and production-evidence gates preserved.
No amendment or lifecycle migration is proposed.
