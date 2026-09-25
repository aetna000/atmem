# Plan: product continuity first, independent benchmark second

## Current delivery order — correction 2026-09-25

Follow [product-first-correction.md](product-first-correction.md), PC-001–PC-006
and P0–P5. Product implementation is now explicitly authorized. The benchmark
must not implement or compensate for recovery. Installed-product acceptance with
the benchmark absent precedes further paid comparisons. Baseline capture means
preserve existing artifacts and record gaps, not block feature work on an
unsupported four-arm run. AtFlows Spec 010 follows the same order.

## Historical plan below — superseded delivery order

The earlier M/G sequence is retained for evidence provenance only. Its
benchmark-first, optional-product-change, separate-approval and no-UI clauses
are superseded by P0–P5. Workload isolation, budget and evidence rules still apply.

Status: implementation in progress. Governed by spec.md, the constitution and contract v1.

## Stack and ownership

Python harness in `benchmarks/agent_continuity/`, separate destination process,
durable SQLite test service and append-only evaluator records. Choose and pin a
public checkpoint-capable runtime at gate G0 through demonstrated capabilities,
not brand preference. No new runtime dependency in AtMem's base install.
Selected: LangGraph 1.2.12 and SQLite checkpoint 3.1.1 in a separate benchmark
environment. Current process-kill tests exercise that implementation; public
retail integration and no-fault upstream equivalence remain incomplete.
AtMem adapter uses supported APIs. The current AtFlows arm uses isolated loopback
OTLP through existing ingest and reports the missing authenticated-producer
contract. It must not claim scoped authentication or add it in an adapter.
Authenticated integration is a later product-change gate, not a prerequisite
that prevents recording current limitations. Bun/TypeScript tests stay there.

## Prioritized implementation milestones (2026-09-25)

Complete bounded offline substeps while live G0 choices are finalized. The user
approved gpt-4.1-2025-04-14 for agent and simulator and a USD 20 total inference
budget (all roles, retries and recovery combined). Exact prompts and operational
limits remain to freeze. This does not advance G2/G5 or complete
their parent tasks.

1. **M1 retail tool boundary:** `retail.py` verifies immutable upstream source,
   imports only the pinned checkout, wraps native tools in an isolated process,
   and compares outputs and DB state with native execution. Evaluator-only pilot
   reference-action replay checks plumbing; it is not an agent trajectory or
   upstream no-fault evaluation and cannot pass T005 alone. Held-out tasks remain
   unavailable to development replay. Record policy/tool/source digests.
2. **M2 current observation:** AtFlows `tests/continuity/http-probe.ts` starts the
   unmodified server on ephemeral loopback with an isolated DB and no network
   price refresh. AtMem drives HTTP fixtures, compares independently known
   deliveries/replays with retained traces, and records gaps without product fixes.
3. **M3 full runtime (offline wiring before separately approved paid runs):** native agent/user orchestration, persistent simulator,
   four-arm scheduling, current-policy and standalone evidence boundaries,
   independent usage/resource ledger and repeat qualification. No provider calls
   until model, prompts, egress, limits and spend cap are explicitly locked.
4. **M4 study:** pilot then preregistered held-out runs, unchanged gates G2–G5.

After each milestone, submit code/test evidence to Claude with tools disabled
(read-only review), correct actionable findings and rerun affected tests. Store
review status and remaining gaps; approval is not production performance evidence.

Offline children receive an allowlisted environment without provider credentials
or dotenv loading. Tripwires detect/reject guarded-path network attempts, and any
detected attempt invalidates the test; this is not an OS sandbox. Only existing product configuration is used; no
exported-handler or authentication patch may alter the current baseline. M2
uses the unmodified server because its OTLP handler is not exported. AtFlows
T002a precedes AtMem T007a. AtMem `milestone-reviews.md` is the canonical review
record; AtFlows links to it. Held-out reference actions/expectations never enter
development fixtures or review prompts; existing split IDs remain in the lock.

Proposed harness files: `manifest.py`, `destination.py`, `faults.py`, `oracle.py`,
`runtime.py`, `adapters/atmem.py`, `adapters/atflows.py`, `runner.py`, `report.py`;
tests in `tests/benchmarking/test_agent_continuity.py`. Raw bundles under an
explicit run output directory, no private Home reuse or credentials in exports.

## Gates

### M3a budget and publication evidence prerequisite

Before provider dispatch, durably reserve a conservative per-attempt upper bound
in a shared SQLite ledger. Integer micro-USD arithmetic and serialized transactions
must prevent concurrent or restarted runners from resetting the allowance. Unknown
charges retain their whole reservation; only known measured usage can release
headroom. Duplicate attempt IDs must not authorize a second dispatch. Freeze the
authorization identity and pricing/protocol digest with the ledger; reopening with
a changed cap or protocol fails. A detected underestimated reservation stops further
dispatch rather than hiding the overrun. This is a harness spending control, not
provider billing enforcement; provider retries must be disabled in the caller.

Keep this ledger independent of AtFlows. Record per-attempt trial/arm/role identity,
retry/recovery classification, timestamps, usage, estimated cost, unknown reasons,
and request/response artifact references. It stores accounting metadata only, not
private prompts or credentials. Public-corpus request/response exports are separate
from governed AtMem evidence and must be explicitly screened before publication.
Every scheduled trial needs a disposition, including budget stops and failures.
Checksummed JSON exports, reproducible manifests and an explicit limitations section
must support subsequent reports/articles; no incomplete pilot becomes production
evidence. Original baseline bundles and protocol locks remain unchanged.

### M3b first native no-fault pilot

Start with already design-exposed pilot task 0 before any four-arm claim. Run pinned
upstream LLMAgent, UserSimulator and Orchestrator; replace only provider transport
with single-attempt logged direct HTTP. Pin temperature 0, 2048 output tokens,
58 steps/60 calls, 600-second loop limit and 90-second request timeout. Persist
upstream prompts, all requests/responses, each completed step, partial/final
trajectories, model usage and checksums. Grade DB plus the task's NL assertions
through the same budget, rejecting missing assertion coverage. A request already
in flight can exceed the loop timeout by at most its request deadline; this is not
a real-time deadline guarantee. All three roles share the one USD20 ledger.
Official pricing checked 2026-09-25: GPT-4.1 standard USD2/M input, USD0.50/M cached
input, USD8/M output. Reserve USD2.20 per call (the full model context plus capped
output and margin), not a heuristic input token estimate. Pricing/tier/model drift
stops the pilot. Report invoice verification as unavailable. This native-only
development pilot is not full no-fault equivalence, a held-out score or evidence of
AtMem/AtFlows performance. Current-product comparison remains a subsequent gate.

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
