# Product continuity first; benchmark as an external test rig

Decision: 2026-09-25, explicitly requested by the owner. This replaces the earlier
benchmark-first delivery order. Implementation is authorized; release is not.
This is a correction within the existing feature, not a new spec number.

## Binding boundary

The benchmark has no role in implementing the feature. It may supply workloads,
start/kill/restart processes, introduce faults or policy changes through normal
interfaces, observe external effects, meter experiment spend, and score results.
It MUST NOT select a resume point, maintain a recovery journal for a product arm,
decide retries, reconcile ambiguous actions, invent receipts, repair task state,
or fill missing product telemetry/cost. Its hidden truth must never reach agents.
Faults use external signals and destination/proxy response barriers; no benchmark
fault hooks are added to shipped packages. Internal crash unit tests are not
evidence that the external benchmark reached the same barrier.

The same user program must recover with the benchmark absent. Product packages
must not import benchmark/test modules. An installed-artifact test must run in a
fresh working directory without either source checkout or benchmark on its path.
Destination test doubles may implement declared tool semantics, not agent recovery.
The evaluator's cost ledger remains independent and must not supply AtFlows totals.

## What the audit actually found

| Current code | Behaviour | Disposition |
| --- | --- | --- |
| `benchmarks/agent_continuity/runtime.py` | `dispatch.db`, saved receipt reuse, skip completed, query/retry/block decisions, checkpoint restoration | Historical recovery design fixture; not proof of shipped AtMem continuity. Replace in product evaluation with installed integration calls. |
| `benchmarks/agent_continuity/adapters/atmem.py` | Decides when receipts permit completion; appends a benchmark-specific audit record before proposing task status | Audit contract sufficiency; implement receipt acceptance and authority in product services, never bless this adapter as the feature. |
| `benchmarks/agent_continuity/adapters/atflows.py`, `observation.py` | Fixture events and independent observations | Keep for test input/scoring only; do not fabricate missing production instrumentation. |
| AtFlows `tests/continuity/http-probe.ts` | Starts and probes existing ingest | Keep as a test; identity, accounting and user views must live in shipped packages/apps. |
| `native_pilot.py`, `spend.py`, raw results | Native workload and experiment accounting | Retain evidence and budget ledger. Native pilot tested neither product recovery nor retry cost reporting. |

The 24 completions / 6 safe stops in each arm are historical design-fixture
results. They do not establish product recovery, equivalence or superiority.
Preserve raw files, hashes, protocol locks and reports; add a correction rather
than altering historical measurements. Previous checked fixture tasks stay
historically complete, not product acceptance complete.

## Product requirements

- **PC-001 AtMem state:** Extend existing Spec 007 task authority and Spec 020
  evidence through supported public services. Persist operation identity,
  argument binding, intent before dispatch, attempt/run links and receipts.
  Use existing encrypted evidence/access boundaries, not a parallel plaintext
  journal. Existing task enums remain unchanged unless separately migrated;
  unknown external outcome is not proof of failure.
- **PC-002 supported integration:** Ship reusable host-neutral tool/recovery
  support and one documented host integration. Host owns execution/checkpoints;
  AtMem owns authoritative progress and eligibility. Do not replace the host
  scheduler or claim support for every host. Recover saved progress, skip only
  evidence-supported completed work, query uncertain effects when supported,
  reuse valid idempotency keys, and stop when neither reconciliation nor safe
  retry is possible. Key expiry, conflicting payloads, stale receipts and
  concurrent attempts fail closed. Revalidate current permissions before any
  reconciliation call, redispatch, context delivery or state transition.
- **PC-003 user operation:** Document exact enablement and a runnable example
  outside benchmarks. CLI/API and dashboard must expose completed, remaining,
  uncertain and blocked work, with receipts, reasons and safe next actions.
  No invented command or "automatic resume" claim before installed tests pass.
  Preserve disabled defaults and make unsupported host/tool capabilities explicit.
- **PC-004 AtFlows:** Ship identity mapping, duplicate/conflict handling, restart
  linkage, usage/price provenance and retry/recovery views via normal ingest,
  storage and dashboard paths. Missing cost is unknown, never zero. Totals count
  each charge once even when retry and recovery labels overlap. AtFlows outages
  never authorize actions or prevent otherwise safe host execution.
- **PC-005 separation gate:** Run the documented example from installed packages
  with benchmark/source paths unavailable, inject a crash externally, and prove
  the product resumes or explicitly blocks. Imports alone are insufficient:
  inspect process inputs and data flow for oracle answers or harness state repair.
- **PC-006 honest evaluation:** Keep baseline host/runtime pinned and independent,
  with its normal documented durability enabled. Do not silently give baseline
  AtMem code or remove its existing safety features. All arms receive the same
  workload, destination capabilities, permissions and fault schedule. Missing
  capability is a result, never repaired in an adapter. Report feature availability
  separately from performance and safety gains.

## Revised delivery sequence

1. **P0 boundary audit and contracts:** classify each behaviour above; map product
   public contracts, ownership, schema/security/migration impacts and one supported
   integration. Read-only Claude review; resolve findings before implementation.
2. **P1 AtMem feature:** implement authoritative operations/receipts and restart
   recovery support in product code, with scope, crash, concurrency and migration
   tests. Review code read-only with Claude and correct issues.
3. **P2 user integration:** ship the reusable integration plus documented example,
   configuration, status and safe resume/confirmation flow. Demonstrate from an
   installed artifact without benchmark helpers; review with Claude.
4. **P3 AtFlows feature:** implement durable links and honest cost accounting,
   expose a joined recovery story in the existing UI, test standalone use and
   loss/duplicates/upgrades. Coordinate Spec 010; review with Claude.
5. **P4 inert rig:** replace product-arm fixture logic with ordinary public calls.
   Run boundary/data-flow checks and deliberate negative controls. Product
   failures must fail the test, not trigger a helper repair. Review with Claude.
6. **P5 qualification:** no-fault workflows, then crashes/uncertainty/revocation
   across baseline, +AtMem, +AtFlows, both; repeated qualification before held-out
   evaluation. Retain every result, cost and failure. Existing USD20 cumulative
   cap and spend ledger remain binding; do not reset them. Product offline work
   precedes any more paid comparison runs.

P1/P2 may use deterministic product integration tests; these are correctness
checks, not production performance evidence. Scope UI work to recovery/status
and cost visibility, not a general redesign. Versions are assigned only after
artifact/compatibility gates; no tag, merge, publish or deploy is authorized here.

## Acceptance example

An ordinary documented agent uploads a document and is killed after upload but
before acknowledgement. On restart, shipped integration/product code checks
the destination and either continues to notification without a second upload or
shows an uncertain outcome needing confirmation. AtFlows shows original and
resumed attempts with known costs and explicit missing values. The benchmark
only causes the interruption and checks the outcome. Repeat with the benchmark
removed: the behaviour must still work.

## Mandatory P0 contract exit gates (read-only review corrections)

- **Identity:** define one versioned product contract under AtMem's public
  contracts documentation, consumed by AtFlows and pinned by digest in both
  manifests. Map Spec 007/020 IDs and specify each issuer. Hosts may issue
  run/attempt IDs; AtMem validates their scoped operation binding. AtFlows
  authenticates producer scope and never infers joins from timestamps/text.
  Experiment trial/arm IDs are not user authorization.
- **Disclosure:** default telemetry permits opaque IDs, safe event/reason codes,
  usage and price provenance, not receipts, arguments, memory or low-entropy
  content hashes. AtMem receipt reads/exports require evidence privileges and
  audit; AtFlows links to authorized evidence instead of copying plaintext.
  Test leakage and scope on ingest, storage, CLI, UI and exports.
- **Authority/outage:** host checkpoints cannot override AtMem eligibility.
  Failed durable intent write or unavailable required authority prevents
  dispatch in governed mode; no silent fallback or mid-operation opt-out.
  Divergence reconciles via public product operations or blocks. Test both sides
  of intent persistence and receipt commit.
- **Host/compatibility:** first ship a LangGraph integration and ordinary example
  outside benchmarks, using native checkpoints and an optional pinned dependency
  profile. Do not add LangGraph to base install. OpenClaw/AtBot support requires
  separate real hooks, aligned pins and installed tests; it is not implied.
  Define old-store migration, mixed-version clients, rollback/downgrade refusal
  and uncertain-operation representation before schema code.
- **Human resolution:** define current actor/scope permission, retain actor/time/
  reason/evidence and make resolution idempotent. Human attestation is not
  independently verified success and cannot mint a destination receipt.
  Unresolved unsafe retries remain blocked.
- **Cost:** distinguish event, attempt and provider charge IDs. Specify dedup
  provenance; absent trustworthy charge identity cannot cause heuristic merging.
  Show known sum plus unknown count, not a false exact total. Test overlapping
  retry/recovery labels and late duplicates after outages.
- **Isolation:** assert clean cwd, Python import paths/NODE_PATH, allowlisted
  arguments/environment and permitted endpoints; no source mount or benchmark
  endpoint accessible to product processes. Monitor file/network access where
  supported and record enforcement limits. A planted forbidden import and oracle
  leak must fail the gate; import checks alone are insufficient.

These are requirements to resolve in P001/P101 product-contract documents, not
claims that the detailed contracts or runtime features already exist.

P001 and P101 are task IDs within P0, not later phases. All mandatory contract
gates close with a recorded cross-repo review before P1/schema code. The AtMem
contract owner coordinates version/digest changes with the AtFlows consumer;
neither repo silently updates the shared interpretation. Contracts must also
define tool capability descriptors (query semantics, key TTL/scope, retry safety;
undeclared means no assumed safe retry), lease/fencing rules rejecting stale
dispatchers, and pending/uncertain operations after evidence retention/deletion.
Unavailable/locked/rotating evidence keys count as unavailable required authority;
they cannot permit plaintext fallback or dispatch without a durable intent.
Freeze qualification counts, safety/success rules and remaining USD20 allocation
before qualification; freeze held-out analysis separately before held-out runs.
