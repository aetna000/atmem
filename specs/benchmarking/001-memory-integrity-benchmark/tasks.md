# Tasks: Memory Integrity Benchmark Qualification

**Input**: `spec.md`, `plan.md`, `research.md`, `data-model.md`,
`contracts/qualification-evidence.md`, and `quickstart.md`

**External repository**: `/Users/javadtaghia/gitlab/memory-integrity-benchmark`
after forking `iluxu/memory-integrity-benchmark` to `aetna000`.

## Phase 1: Freeze inputs and establish the public fork

- [x] T001 Record the exact upstream benchmark commit, tag/license, harness
  version and attack digests in `specs/benchmarking/001-memory-integrity-benchmark/research.md`.
- [x] T002 Fork and clone the benchmark to
  `/Users/javadtaghia/gitlab/memory-integrity-benchmark`, configure `origin` as
  `aetna000/memory-integrity-benchmark` and `upstream` as
  `iluxu/memory-integrity-benchmark`, and create an AtMem integration branch.
- [x] T003 [P] Resolve the published `atmem==2.3.5` wheel URL and SHA-256 without
  importing this checkout; record them in the qualification manifest fixture in
  `/Users/javadtaghia/gitlab/memory-integrity-benchmark/system-configurations/atmem.json`.
- [x] T004 [P] Add benchmark-fork dependency pins for `atmem==2.3.5` and record
  its source in `/Users/javadtaghia/gitlab/memory-integrity-benchmark/system-configurations/adapter-sources.json`.

**Checkpoint**: Inputs are immutable, licensed, public and clean-installable.

## Phase 2: Capability gate (blocks adapter implementation)

- [x] T005 [US2] Write installed-wheel falsification tests for AtMem source
  trust, quarantine, scope, lineage, review, outcome evidence, recall and secret
  inspection in `tests/test_benchmark_memory_integrity_contracts.py`; tests must
  use public APIs and isolated temporary Homes.
- [x] T006 [US2] Execute a small public-API capability spike against the clean
  2.3.5 wheel and record observed native fields/statuses without adapter-created
  labels in `specs/benchmarking/001-memory-integrity-benchmark/research.md`.
- [x] T007 [US2] Finalize all six capability decisions and their exact APIs,
  persisted markers, enforcement points, falsification tests and limitations in
  `/Users/javadtaghia/gitlab/memory-integrity-benchmark/adapters/atmem/CAPABILITIES.md`.
- [x] T008 [US2] Add tests in
  `/Users/javadtaghia/gitlab/memory-integrity-benchmark/tests/test_atmem_adapter.py`
  that reject unknown, overstated or adapter-local-only capability declarations.

**Checkpoint**: No adapter operation proceeds until procedure authority,
derivation taint and category-L scoring surfaces have an honest decision.

## Phase 3: Pre-implementation review gates

- [x] T009 Run Claude CLI read-only review of spec/plan/tasks, capability
  honesty, anti-gaming, evidence contract and release ladder; apply reasonable
  findings and repeat until no unresolved critical/high item remains.
- [x] T010 Run Spec Kit consistency analysis after planning and again after any
  material Claude-driven artifact change; resolve coverage/contradiction findings.

## Phase 4: Benchmark harness integration

- [x] T011 [US1] Generalize the system registry/order in
  `/Users/javadtaghia/gitlab/memory-integrity-benchmark/runner/run.py` so AtMem is
  registered without changing attack definitions or existing system behavior.
- [x] T012 [P] [US1] Generalize labels and system iteration in
  `/Users/javadtaghia/gitlab/memory-integrity-benchmark/runner/report.py`,
  `runner/merge.py`, `runner/revise.py`, and `runner/combined_report.py`.
- [x] T013 [P] [US1] Add bounded AtMem smoke/full targets and clean-environment
  help to `/Users/javadtaghia/gitlab/memory-integrity-benchmark/Makefile` and
  `README.md`.
- [x] T014 [US1] Add regression tests in
  `/Users/javadtaghia/gitlab/memory-integrity-benchmark/tests/test_contract.py`
  and `tests/test_combined_report.py` proving existing systems, order, counters,
  schemas and published inputs remain unchanged.

## Phase 5: Native AtMem adapter

- [x] T015 [US2] Add failing adapter contract tests for deterministic reset,
  per-trial scope/Home isolation, installed-distribution identity, settle, close
  and cleanup in `/Users/javadtaghia/gitlab/memory-integrity-benchmark/tests/test_atmem_adapter.py`.
- [x] T016 [US2] Implement lifecycle and identity plumbing in
  `/Users/javadtaghia/gitlab/memory-integrity-benchmark/adapters/atmem_adapter.py`
  using the published AtMem public APIs only.
- [x] T017 [US2] Add failing tests for trusted/untrusted ingestion, repetition,
  active/quarantined inspection and governed recall; then implement `ingest`,
  `inspect` and `recall` without post-filtering benchmark targets.
- [x] T018 [US2] Add failing tests for mixed-parent derivation and native taint
  visibility; implement `derive_summary` only if the final capability decision
  is representable, otherwise raise the correct benchmark exception.
- [x] T019 [US3] Add failing positive/negative procedure tests; implement
  `propose_procedure`, `approve_procedure` and `list_active_procedures` only
  through a native typed proposal/review/activation contract, including invalid,
  stale, replayed and cross-scope approval cases.
- [x] T020 [US2] Add failing outcome-laundering tests; implement
  `record_outcome` only if AtMem's native action/outcome evidence is accepted by
  the mapping and prove it cannot change trust, taint or lifecycle.
- [x] T021 [US2] Add exhaustive scoring-surface tests for synthetic secret
  scanning and implement `scan_secret` across public recall, active,
  quarantined, derived and other benchmark-scoring persistence surfaces; also
  inventory encrypted Agent Black Box channels and disclose any benchmark-named
  transcript/evidence exclusions without treating them as non-retention.
- [x] T022 [US2] Run the adapter tests against both the clean 2.3.5 wheel and a
  negative fixture that disables each declared native control; ensure the
  corresponding assertion changes or representability status is explicit.

## Phase 6: Smoke run and first immutable 2.3.5 evidence

- [x] T023 [US1] Run all benchmark and adapter tests, validate schemas and run
  exactly one isolated trial for each A, C, D, F, H, I and L against 2.3.5.
- [x] T024 [US1] Add publication validation for editable imports, dirty trees,
  mixed identities, duplicate/missing trials, changed attack/config digests,
  plaintext synthetic secrets, absolute paths, checksum drift, invalid statuses
  and any aggregation that counts `ERROR` as success or failure in
  `/Users/javadtaghia/gitlab/memory-integrity-benchmark/tests/test_publication.py`.
- [x] T025 [US1] Execute the complete deterministic 700-trial profile against
  `atmem==2.3.5`, preserving the first complete run under a unique directory in
  `/Users/javadtaghia/gitlab/memory-integrity-benchmark/results/published/`.
- [x] T026 [US1] Generate manifest, raw JSONL, aggregates, failures, table,
  environment lock, reproduction guide, limitations and checksums solely from
  the frozen run data.
- [x] T027 [US1] Rebuild the report from raw trials in a second clean environment
  and verify byte-identical generated files and all checksums.

**Checkpoint**: A complete 2.3.5 result exists even if it contains failures or
capability gaps; no result has been optimized away.

## Phase 7: Triage and conditional prerelease correction

- [x] T028 [US4] Classify every non-pass/error as product, adapter, harness,
  environment or capability gap in the immutable run's `failures.jsonl` and
  `LIMITATIONS.md`, with exact raw-trial references.
- [ ] T029 [US4] For adapter/harness defects only, add a failing benchmark-fork
  regression, correct the integration, assign a new run identity and rerun the
  affected category plus all 700 publication trials without changing AtMem.
- [x] T030 [US4] If and only if a genuine AtMem defect is confirmed, add the
  failing boundary regression to `tests/test_benchmark_memory_integrity_contracts.py`
  before changing product code and preserve the 2.3.5 evidence package.
- [ ] T031 [US4] Conditional on T030, implement the smallest constitutional
  product correction, set the next available beta version consistently across
  AtMem/AtBot/OpenClaw compatibility metadata, add release notes and run all
  required release gates without publishing stable.
- [ ] T032 [US4] Conditional on T031, publish/install the beta only under the
  repository release-completion rule, rerun all 700 trials against the actual
  artifact and compare it with 2.3.5 without rewriting either run.

## Phase 8: Product verification and publication

- [ ] T033 [US3] Run AtMem's installed-artifact, invariant, authority,
  extraction, retrieval, lifecycle, deletion, evidence, encryption, framework
  adapter, metadata and Python 3.10–3.13 gates appropriate to the actual diff;
  assert the external benchmark is not added to AtMem's base runtime dependencies.
- [ ] T034 [US5] Publish an honest qualification summary with exact categories,
  denominators, statuses, errors, configuration and limitations in
  `docs/benchmarks/memory-integrity.md`; link it from the existing benchmark
  documentation index and link to the public fork rather than duplicating raw
  evidence.
- [ ] T035 [US5] Validate the clean reproduction path from a fresh clone without
  local AtMem source, private services, developer environment files or existing
  user state.
- [ ] T036 [US5] Commit and push the benchmark fork branch and evidence package,
  then open a narrow upstream proposal/PR that distinguishes fork publication,
  submission and merge status.
- [ ] T037 [US5] Assert that every qualification reference remains `2.3.5` and
  no package/installer version changed when triage found no product defect; then
  commit and push this branch with the completed qualification record and
  regressions; do not merge, tag or claim upstream acceptance unless
  those external states are verified.

## Phase 9: Read-only implementation review and final consistency

- [ ] T038 Run Claude CLI read-only implementation review of both repository
  diffs, tests, smoke/full evidence and claims; apply reasonable findings and
  rerun affected tests/trials.
- [ ] T039 Recheck constitution, all Markdown consistency, version references,
  local-path/secret scans and task completion before reporting the outcome.

## Dependencies and execution order

- T001–T004 establish immutable inputs.
- T005–T008 are a hard capability gate before T015–T022.
- T009–T010 are mandatory read-only/consistency review gates before code.
- T011–T014 may proceed after the fork exists but must pass before smoke.
- T015–T022 build the adapter test-first and depend on the capability gate.
- T023–T027 produce the immutable first run.
- T028 decides whether T029 or conditional T030–T032 applies.
- T033–T037 publish only after evidence is validated.
- T038 and T039 close implementation.

## Independent story validation

- **US1**: A clean environment produces and regenerates exactly 700 raw trials.
- **US2**: Every capability and adapter operation is traceable to falsifiable
  native 2.3.5 behavior; unsupported concepts remain explicit.
- **US3**: Category I activates only a properly authorized procedure while
  invalid/stale/replayed/cross-scope attempts fail closed.
- **US4**: Every non-pass survives unchanged and has one reproducible triage class.
- **US5**: A third party can reproduce the fork result and distinguish it from
  upstream acceptance or a later product release.
