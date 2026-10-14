# Tasks: AtMem Laya Formation Model

**Inputs**: `spec.md`, `plan.md`, `research.md`, `data-model.md`,
`contracts/authentic-memory-understanding-v2.md`, `quickstart.md`; the V1
contract is retained only as historical compatibility evidence.
**Rule**: tests precede each behavioral slice. No credential use, external API
call, paid compute, public visibility change, tag or release occurs merely
because this task list exists.

## Phase 1 — Freeze protocol, boundaries and sources

- [x] T001 Reconcile Spec 041 against Spec 040 public formation/retrieval
  contracts and record an authority/compatibility crosswalk in
  `specs/041-atmem-laya-formation-model/alignment.md` (FR-001–FR-009, FR-036).
- [x] T002 Pin Laya source/model revisions, license, file digests, supported
  training/export commands and dependencies in
  `research/laya_formation/sources.json`; load the exact pinned tokenizer and
  configuration, derive and test the effective maximum input length including
  reserved/special tokens, record the evidence and block schema/packer freeze
  until it passes; retain the upstream source/card snapshots permitted by
  license (FR-002, FR-016, FR-019).
- [x] T003 Pin the Jev API/schema and implement a no-call preflight that resolves
  a concrete service model identity; reject a moving alias or unrecorded schema
  in `research/laya_formation/jev_protocol.py` and tests (FR-028–FR-029).
- [x] T004 Define synthetic-data, training, calibration, installed-runtime and
  evaluation threat models, including prompt/data injection, cross-scope IDs,
  secret leakage, contamination and moving-service risk, in
  `specs/041-atmem-laya-formation-model/security.md` (FR-001–FR-004, FR-023).
- [x] T005 Freeze dataset/model Hugging Face repository naming, licenses, card
  templates, private-staging workflow and immutable-revision inventory schema
  without reading a token or creating repositories (FR-025–FR-027).
- [x] T006 Freeze one matched evaluation protocol with arms, cases, option and
  candidate-pool digests, budgets, hardware classes, metrics, bootstrap method,
  failure policy, minimum latency effect and separate synthetic versus public-
  corpus production claim gates in
  `benchmarks/laya_formation/protocol-v1.yaml` (FR-028–FR-034).
- [x] T007 Add a secret-safe compute qualification protocol for the Windows SSH
  host and Mac, and a conditional Vast total-cost worksheet with USD 8 hard cap,
  the FR-020 48-hour/memory/storage viability envelope, strict SSH host-key
  verification, no password-bearing command arguments, resume/sync and teardown gates in
  `research/laya_formation/compute_protocol.md` (FR-020–FR-024).

**Checkpoint**: immutable inputs, authority and claims are defined before data
generation or external execution.

## Phase 2 — Synthetic dataset

- [x] T008 [P] Add JSON Schema/Pydantic contracts and malformed/golden tests for
  `FormationScenarioV1`, `TypedDecisionExampleV1` and split manifests under
  `research/laya_formation/dataset/` and `tests/research/`; implement one shared
  versioned tokenizer-exact packer usable by dataset and product adapters and
  require byte-identical parity/overflow fixtures (FR-002, FR-010–FR-013).
- [x] T009 [P] Implement deterministic fictional identities, source events and
  scenario templates covering every required operation/class/safety case, with
  fixed seeds and versioned provenance (FR-010–FR-012).
- [x] T010 Implement the independent state oracle and validators for finite
  choices, target authorization, exact post-state, contradiction, insufficient
  evidence and review/escalation labels (FR-011–FR-012).
- [x] T011 Implement group-disjoint split assignment across identity, template,
  semantic chain and paraphrase cluster plus exact/near-duplicate and leakage
  tests; prove the sealed labels are inaccessible to training (FR-013, FR-018).
- [x] T012 Generate at least 12,000 states/60,000 decisions on the external
  artifact root, emit checksum-bound JSONL/Parquet/manifests and validate class,
  difficulty and safety coverage (FR-010–FR-013, FR-024).
- [x] T013 Build a blinded stratified 400-row audit packet and reviewer workflow;
  draw only from train/validation/calibration, include at least 60 examples for
  every FR-014 high-risk tag, block on less than 99% target correctness or any
  critical privacy, credential or license finding, and retain signed results
  (FR-014).
- [x] T014 Create the dataset card, data statement, limitations, split statistics,
  provenance and reproducibility commands; lint against production-evidence or
  real-user-data claims (FR-015, FR-025).
- [x] T015 Create the dataset repository privately, upload by environment token,
  redownload by commit, verify inventory/digests/schema/secret scan/card/license,
  and retain a visibility-change readiness receipt without making it public yet
  (FR-023, FR-025, SC-001).

**Checkpoint**: a clean, audited private dataset revision exists; no model has
trained on unvalidated or sealed-test content.

## Phase 3 — Compute qualification, training and model staging

- [x] T016 Add a fixed representative smoke workload that exercises load,
  forward/backward, checkpoint, resume, calibration and Safetensors reload and
  records throughput, peak/free memory, projected peak storage, projected
  completion and every FR-020 viability decision (FR-016–FR-022).
- [x] T017 Run the smoke on the Windows SSH machine using interactive/secret-store
  authentication, strict host-key verification and CUDA when available; retain
  redacted capability/results and copy no credentials into commands, process
  arguments or artifacts (FR-020, FR-023).
- [x] T018 Run the identical smoke on the Mac MPS/CPU route and retain matched
  capability/results on the external artifact root (FR-020, FR-024).
- [x] T019 Select a viable local route from T017/T018. Only if both are recorded
  infeasible, query live Vast offers, compute expected total cost/reliability,
  prove checkpoint resume/off-instance sync, obtain spending approval, and rent
  a qualifying instance under the USD 8 cap (FR-021–FR-023).
- [x] T020 [P] Add training-manifest, metric and calibration-bundle schemas plus
  determinism, nonfinite, truncation, collapse, class-prior and secret-scan tests
  and encode the FR-019 same-backend/cross-backend tolerances before training
  (FR-016–FR-019).
- [x] T021 Run fixed-seed cross-entropy and upstream-supported RLCD/proper-scoring
  controls on train/validation only; retain every configuration and failure,
  selecting by predefined quality/calibration criteria (FR-017–FR-018).
- [x] T022 Fit calibration/abstention thresholds on the isolated calibration
  split and freeze model/question/calibration digests plus the sealed-test
  analysis code without opening sealed examples or labels (FR-018).
- [x] T022A After model, thresholds and analysis are frozen, give a separately
  sampled sealed-test audit packet to a different firewalled reviewer. Record
  independence and signed results; any critical finding or required content/
  oracle correction invalidates this dataset/model version and requires fresh
  generation, splits and training rather than an in-place fix (FR-014, FR-018).
- [x] T022B After T022A passes, open the sealed test once with the frozen model,
  thresholds and analysis and produce class-level metrics and failure analysis;
  do not use results for reselection or tuning (FR-017–FR-018).
- [x] T023 Export the selected model/config/questions/tokenizer/calibration in
  Safetensors-compatible form; reload in clean CPU and available accelerator
  environments and reproduce predictions within tolerance (FR-019, FR-035).
- [x] T024 If Vast was used, verify all artifacts off-instance, record final
  compute/storage/transfer cost and destroy the instance; otherwise record that
  no rental was used (FR-021–FR-024).
- [x] T025 Write the model card with exact lineage, metrics, calibration,
  limitations, intended use, compatibility and AtMem authority/escalation
  boundaries (FR-026).
- [x] T026 Create the model repository privately, upload by environment token,
  redownload by commit, verify inventory/digests/secret scan/card/license and
  clean load, and retain a visibility-change readiness receipt (FR-023,
  FR-025–FR-026, SC-002).

**Checkpoint**: a clean, reproducible private model revision exists and all
compute has been recovered/closed without assuming a benchmark win.

## Phase 4 — Optional governed product integration

- [x] T027 [P] Add failing golden/malformed/version compatibility tests for
  `FormationDecisionRequest/Response`, question definitions, calibration and
  decision receipts, including tokenizer-exact packing, preserved question/
  choices, explicit overflow receipts and disabled silent truncation, in
  `tests/test_laya_formation_contracts.py` (FR-002–FR-004).
- [x] T028 [P] Add failing authority tests for forged/stale/cross-scope targets,
  invented evidence, policy denial, deletion races and unauthorized provider
  input in `tests/test_laya_formation_governance.py` (FR-001–FR-004, SC-003).
- [x] T029 Implement additive host-neutral contracts and the governance adapter
  that bounds requests then reloads and revalidates canonical state through Spec
  040 services before disposition (FR-001–FR-004, FR-036).
- [x] T030 Add an optional dependency group and lazy Laya artifact resolver with
  revision/digest/schema/calibration binding; prove base installs import and run
  offline without it (FR-005, FR-019, FR-035).
- [x] T031 Implement device selection, bounded inference, score validation,
  the shared T008 tokenizer-exact whole-range packer, calibrated abstention and
  deterministic fallback with content-safe diagnostics; re-run packer parity in
  the installed wheel (FR-002, FR-004–FR-006, FR-011).
- [x] T032 Implement the declared escalation policy through the existing AtBot
  provider with minimum authorized input, schema/budget enforcement and
  provider-offline fallback/review (FR-007–FR-009).
- [x] T033 Add guided and noninteractive setup, preview, activation, status/doctor
  and rollback using existing CLI conventions; add corresponding MCP/dashboard
  read-only status where the current product exposes profiles (FR-005–FR-006).
- [x] T033A Before accepting upgrade compatibility as final evidence, verify
  AtMem `2.3.8` is published and registry-verified, pin its wheel and digest, and
  install it as the T034 baseline. A candidate checkout may support development
  but cannot satisfy this gate (FR-036).
- [x] T034 Add clean-wheel fresh-install and `2.3.8` upgrade tests proving no
  forced download/default change, additive metadata, exact rollback and unchanged
  existing CLI/MCP/OpenClaw/AtBot/AtFlows contracts (FR-035–FR-036, SC-004).
- [x] T035 Run installed-artifact coverage for Python 3.10–3.13 and declared
  Windows CPU/CUDA, macOS CPU/MPS and Linux CPU/CUDA profiles; publish only the
  combinations actually executed (FR-035).

**Checkpoint**: Laya is an explicit reversible profile and cannot widen AtMem
authority; deterministic AtMem remains fully usable.

## Phase 5 — Matched evaluation and claim decision

- [x] T036 Implement adapters for deterministic AtMem, pinned current Qwen,
  unmodified Laya, fine-tuned Laya, resolved Jev and Laya-plus-escalation without
  importing evaluation code into product modules (FR-028–FR-029).
- [x] T037 Run no-egress/prepaid preflights and verify exact artifacts, matched
  cases/options/candidate pools/budgets, egress approval and maximum cost before
  any Jev or generative-provider call (FR-023, FR-028–FR-029).
- [x] T038 Execute formation/store evaluation and retain exact post-state,
  component correctness, safety, review/escalation, latency, usage, cost and all
  error rows for every arm (FR-030).
- [x] T039 Execute retrieval evaluation with frozen candidate membership and
  report MRR@5, Recall@1/5/10, evidence coverage, abstention, latency and cost
  (FR-031).
- [x] T040 Execute store-then-retrieve cases and emit source-to-delivery stage
  attribution with no unknown/error outcome credited as success (FR-032).
- [x] T041 Generate paired cluster-bootstrap intervals, per-class and aggregate
  tables, matchedness/identity/safety gates and machine-checkable claim decisions;
  include the SC-006 latency ratio/effect gate and prohibit hidden-class losses
  or best-of selection (FR-033–FR-034, SC-006).
- [x] T042 Publish a checksum-bound reproducibility report that states whether
  each workflow beats, ties, loses to or is inconclusive against Jev and explains
  end-user latency/cost/quality tradeoffs without expanding the evidence; label
  every dataset-only result as synthetic (SC-005–SC-007).
- [ ] T042A Before any production-level or general customer-facing Jev
  superiority claim, run the separately frozen held-out human-origin
  conversation protocol at intended scale and apply the same matching/safety/
  confidence gates. Report the applicable Spec 040 LongMemEval/store-to-
  retrieval workflow only as a separate addendum; it never satisfies or
  substitutes for the human-origin confirmation gate. Record a blocked claim
  when the human-origin evidence is absent or fails (FR-033–FR-034, SC-007).

**Checkpoint**: claims are outputs of a validated protocol, not release goals.

## Phase 6 — Artifact publication and 2.3.9b1 release

- [x] T043 After owner approval, make the verified dataset repository public,
  redownload the public commit anonymously, verify all checks and record URL,
  commit and publication evidence independently (FR-025, FR-027, SC-001).
- [x] T044 After owner approval, make the verified model repository public,
  redownload the public commit in clean environments, verify load/predictions and
  record URL, commit and publication evidence independently (FR-025–FR-027, SC-002).
- [x] T045 Add `docs/releases/v2.3.9b1.md` with exact install/upgrade/opt-in/
  rollback commands, compatibility matrix, artifact revisions, user-visible
  benefit, migration behavior, evaluation and honest limitations (FR-037).
- [x] T046 Align AtMem, AtBot and OpenClaw bridge package/installer constants,
  update `docs/website/manifest.json`, affected guides/examples and run
  `python scripts/check_website_docs.py` plus all package, companion, bridge,
  build, metadata and installed-artifact gates (FR-037–FR-038).
- [x] T047 Prepare a separate owner-reviewed source-pin refresh PR in the private
  website repository; do not merge it or claim deployment, and record website PR
  merged/live states separately (FR-027, FR-038).
- [ ] T048 Commit and push the clean reviewed release changes. If AtBot changed,
  create/push its annotated tag first and verify its workflow/PyPI artifact;
  otherwise record unchanged exact pin (FR-038).
- [ ] T049 Create and push immutable annotated `v2.3.9b1` on the exact reviewed
  commit, wait for `publish`, and verify prerelease URL, AtMem PyPI version and
  matching OpenClaw npm bridge; never move a published tag (FR-038).
- [ ] T050 Publish the final release record with branch, commit, tags, workflow,
  release URL, package versions, all three Hugging Face revisions and separate website
  PR/live states; distinguish candidate pushed from release published (SC-008).

**Completion**: all three Hugging Face artifacts are public and verified, optional
product behavior passes compatibility/safety gates, evaluation claims are
evidence-bound, and the coordinated beta publication is independently verified.

## Phase 7: Convergence

- [x] T051 HISTORICAL V1 Wire the explicitly activated Laya profile into the live
  Context Engine formation path through a lazy runtime router; preserve the
  byte-compatible deterministic path when the profile is absent, inactive,
  unhealthy or fails per FR-005, FR-006 and Acceptance Scenarios 1–2. This V1
  post-hoc route does not satisfy T067–T069 or the current single-classifier gate.
- [x] T052 HISTORICAL V1 Bind the five versioned Laya questions to authorized source
  ranges and active candidates, revalidate every proposal through Spec 040,
  apply only permitted canonical dispositions and retain model/fallback/final
  decision receipts per FR-001–FR-004 and Acceptance Scenarios 3–4. This records
  only the superseded proposal-only V1 behavior.
- [x] T053 HISTORICAL V1 Add an explicit deterministic/Laya/Laya-with-escalation selection to
  the guided AtMem setup journey while preserving the existing noninteractive
  formation commands and separate activation confirmation per FR-005–FR-009.
  V2 shadow qualification and active cutover remain in T069.
- [x] T054 HISTORICAL V1 Add live-path integration tests proving inactive-profile parity,
  activated model invocation, authority revalidation, decision-receipt
  persistence, and deterministic fallback on missing dependencies, abstention,
  timeout or invalid output per SC-003–SC-004 and Constitution III/VI. These tests
  cover V1 only and do not satisfy the V2 integration gates.

## Phase 8: Stateful authentic-corpus convergence

- [x] T055 CRITICAL Quarantine the obsolete synthetic corpus, its derived model,
  and the completion/publication evidence recorded for them; bind every current
  dataset/model claim to a new authentic-corpus lineage and explicitly prevent
  T043–T044 from satisfying the replacement artifact gates per FR-010,
  SC-001–SC-002 and Constitution VI.
- [x] T056 Freeze one versioned decision contract that maps the public
  dispositions `STORE`, `UPDATE`, `DUPLICATE`, `DO_NOT_STORE`, `FORGET`, and
  `REVIEW` to the runtime operations and requires evidence/target identifiers
  for relational decisions; add contract tests using the existing operational
  100-case corpus per FR-002–FR-004 and SC-003. This completed V1 evidence is
  retained but does not satisfy the replacement T061/T067 V2 gates.
- [x] T057 Implement a migration-tested SQLite work database on the MEM volume
  with immutable source and candidate tables, same-scope chronology, normalized
  fingerprints, embedding and duplicate-cluster tables, separate append-only
  Codex and optional Claude judgments, adjudication records, final-label views, integrity
  constraints, provenance, and transaction-safe restart state per FR-010–FR-012a
  and Constitution II/VI.
- [x] T058 Import more than 100,000 authentic licensed conversation candidates
  into the work database and enforce source revision, license, provenance,
  privacy exclusion, language identification, content hashing, and immutable
  source-row inventory before labeling per FR-010–FR-013 and SC-001.
- [x] T059 Construct corpus-wide exact and multilingual semantic duplicate
  graphs before judging, keep connected clusters intact across splits and work
  queues, and distinguish cross-scope corpus deduplication from same-scope
  chronological `DUPLICATE` decisions with explicit canonical targets per
  FR-002–FR-004, FR-012 and Constitution II/III.
- [x] T060 Provide both judge CLIs the same restricted read-only database query
  interface for row, scope, chronology, cluster, sort, filter, lexical search,
  semantic search, and aggregate inspection; prohibit either judge from editing
  source data, clusters, the other judge's output, or final labels per FR-012a
  and Constitution II/III.
- [x] T061 Replace isolated-candidate labels with versioned state-transition
  schemas containing pre-state snapshot/generation, authorized observation,
  actual retrieved memories, one strict Choice/Noul/Score question, expected
  typed response, required target/evidence, expected mutation and post-state;
  reject free-form output and generated memory text in
  `research/laya_memory_evidence/` and `tests/research/` (FR-002–FR-004,
  FR-011, FR-016).
- [x] T062 Implement a deterministic scale manifest and group-aware allocator
  for the full 50k/20k/5k/5k/20k/30k allocation, with
  `experiment_scale_percent=10` producing requested 5k/2k/500/500/2k/3k
  counts, recorded achieved counts and no identity/scope/conversation/
  chronology/duplicate-component leakage; add reproducibility and 10-to-100
  scale-equivalence tests (FR-010, FR-013).
- [x] T067 Replace the Choice-only runtime with strict discriminated
  `laya-evaluation-request-v2` Choice/Noul/Score contracts and validators,
  including exact strict-Jev field shapes, independent Choice confidence,
  Noul-without-confidence, Score legend/expected-value checks,
  tokenizer-exact packing, malformed/golden/compatibility tests and explicit V1
  behavior in `atmem/laya_formation/`, `research/laya_memory_evidence/` and
  `tests/` (FR-002–FR-004, FR-011).
- [x] T068 Implement the versioned formation-plan state machine, typed response
  receptors, unified AtMem formation ruling and proposal-versus-authority
  receipts; ensure Laya never generates canonical memory text and AtMem derives
  mutations only from authorized evidence (FR-003–FR-006c).
- [x] T069 Route every ordinary formation-capable entry point through exactly
  one semantic classifier; add mandatory non-influencing shadow qualification
  before explicit active cutover; prove `deterministic` parity with `2.3.8`,
  Laya-only delegation in `laya`, Laya-first behavior in `laya-escalation`, no
  direct-write bypass and no double classification; keep migrations/restores
  separately governed (FR-005–FR-009, FR-035–FR-036, SC-003–SC-004).
- [x] T063 Implement chronological baseline replay work items and adapt Codex CLI
  plus optional Claude CLI workers to adjudicate every state-building transition
  against its evolving same-scope state. Apply only accepted expected
  transitions through AtMem governance; never use unreviewed deterministic or
  Laya output as gold canonical state (FR-001, FR-010–FR-014, SC-003).
- [x] T064 After baseline adjudication, freeze checksum-bound scoped SQLite and
  vector snapshots with exact schema, embedder, configuration, source,
  transition and canonical manifests; prove unrelated scopes cannot nominate
  one another and support copy-on-write restore. The freeze command MUST require
  and verify T063's complete adjudication-receipt digest and fail closed when it
  is absent, incomplete or mismatched, in
  `research/laya_memory_evidence/` (FR-001, FR-010–FR-013a, SC-003).
- [ ] T065 Generate training/validation/calibration/sealed-test work items using
  actual AtMem retrieval against the appropriate immutable pre-state; adjudicate
  complete transitions rather than isolated text; run the preregistered
  10%-scale pilot and self-review passes with append-only receipts, convergence,
  agreement, retrieval-coverage, class/language/risk and post-state validity
  reports. Freeze sealed labels through a blinded adjudication authority that
  did not generate training labels and cannot inspect base/tuned predictions;
  retain prior isolated judgments only as superseded diagnostic
  evidence (FR-010–FR-015, FR-030–FR-032, SC-001).
  Assert in the manifest validator that every scope and its state-building
  prefix belong to exactly one split family. Report per-split judge-mode
  fractions, per-language sample-power eligibility and machine-weak-supervision
  status; do not call unaudited sealed rows human ground truth.
- [x] T065A Update the already-public fictional/isolated V1 dataset and model
  cards with immutable deprecated/superseded notices and replacement-lineage
  links; retain the artifacts and their historical claims without relabeling
  them as authentic evidence (FR-027).
- [x] T066 Export and publish two independent 10%-scale artifacts: (a) a
  loadable SQLite/vector database repository with schema, embedder/config,
  source/canonical manifests, integrity verifier and example queries; and (b) a
  viewer-ready transition dataset repository with Parquet/JSONL and split/
  snapshot references. Each must independently pass redistribution-license,
  privacy, provenance, leakage, secret, clean-load and anonymous-redownload
  gates and disclose achieved counts without a 100%-scale claim
  (FR-010–FR-015, FR-025–FR-027, SC-001).

## Phase 9: Stateful Laya training and matched evaluation

- [x] T070 Run and freeze unmodified multilingual Laya on the sealed 10%-scale
  2,000-transition set, recording complete typed outputs, calibration,
  governance outcomes, exact post-state, latency and failures without using the
  results for training or selection (FR-017–FR-019, FR-028–FR-034, SC-009).
- [ ] T071 Train objective controls on only the 2,000 training transitions,
  select on the 500 validation transitions, calibrate on the separate 500, bind
  every snapshot/dataset/schema/plan/model hash, export Safetensors and clean-
  reload across claimed platforms within the paid-compute gates (FR-016–FR-026,
  SC-002).
- [ ] T072 Evaluate the frozen tuned model on the identical sealed 2,000 cases
  and sequential trajectories; publish paired base-versus-tuned fully-correct
  counts, macro-F1, target/state accuracy, false-store/duplicate/unsafe rates,
  abstention, Brier/ECE, latency, bootstrap intervals and all failures without a
  predetermined win requirement. Unless all 2,000 cases have exact-contract
  human annotations, title the results as agreement with blinded machine weak
  supervision rather than correctness (FR-017–FR-019, FR-028–FR-034,
  SC-005–SC-009).
- [ ] T072A Revalidate `docs/releases/v2.3.9b1.md`, website manifest/guides and
  the private website source-pin PR against the final immutable database,
  dataset and model revisions; rerun website-doc gates before any release commit
  or tag and record website PR/live states separately (FR-027, FR-037–FR-038).
- [ ] T073 Stage and publish the independently usable model/card only after all
  gates pass and anonymously redownload/reload it. Only after T066, T072 and
  T072A pass, complete the coordinated `2.3.9b1` release procedure without
  self-merging the private website PR (FR-025–FR-027, FR-035–FR-038,
  SC-001–SC-008).

**Checkpoint**: the authentic corpus is partitioned by a reproducible scale
manifest; training and evaluation use frozen scoped SQLite/vector state and
actual AtMem retrieval; Laya emits only strict typed judgments; AtMem alone
governs and mutates; and published claims disclose the exact achieved scale.

## Phase 10: Selective single-call V3 correction

- [ ] T074 Freeze the rejected V2 evidence and V3 amendment: link the matched
  deterministic/original/fine-tuned receipts, exact baseline/model/corpus
  digests and R&D decision; update Spec 041, plan, data model, protocol and
  implementation status without rewriting the negative result; explicitly
  retire FR-006b's sequential learned plan and record that immutable
  `v2.3.9b1` cannot contain V3 (FR-039, SC-010).
- [ ] T075 Add failing contract/property tests and implement the strict V3 joint
  Choice request/response, request-bound opaque action-target option table,
  normalized-probability tolerance, exact one-call receipt and governance
  revalidation in `atmem/laya_formation/` and `tests/`. Require byte-identical
  training/runtime fixtures for candidate order, target aliases, options,
  serialized bytes, tokenizer IDs/counts and both option/evidence overflow
  receipts (FR-040, FR-046, SC-011).
- [ ] T076 Add failing routing tests and implement a versioned selective router
  that sends structurally resolved cases through unchanged deterministic AtMem,
  delegates unresolved semantic cases without first assigning a competing
  semantic answer, supports non-influencing shadow mode and records every
  routing/failure disposition (FR-041, SC-003–SC-004, SC-011).
- [ ] T077 Derive a transition-level V3 training view from the existing
  authentic work database and frozen split/snapshot manifests using the exact
  runtime option constructor and packer. Add leakage, option parity, post-state,
  teacher-forced/on-policy lineage and no-synthetic-content validators in
  `research/laya_memory_evidence/` and `tests/research/` (FR-042, FR-045–FR-046).
- [ ] T078 Produce a pretraining coverage report for every operation, target
  relation, language and trajectory. Freeze the automatically deployable action
  set; fail training for absent or underpowered required classes rather than
  fabricating rows. Freeze majority and deterministic controls plus the V3
  validation/calibration/sealed manifests before optimization (FR-043–FR-044).
- [ ] T079 Run representative Mac and Windows capability checks, then use the
  already-authorized cost-capped Vast/Hugging Face fallback only if both local
  routes remain infeasible. Train cost-sensitive cross-entropy first and only
  then an RLCD control if the first control and coverage gates justify it.
  First reconcile the cumulative Vast and Hugging Face provider ledgers against
  all prior Spec 041 receipts and record the remaining authorized balance.
  Retain checkpoints, logs, exact cumulative cost and teardown evidence
  (FR-020–FR-024, FR-042–FR-045).
- [ ] T080 Select a checkpoint using only transition-level validation and
  sequential trajectory metrics; calibrate per action on the isolated
  calibration split; reject majority shortcuts, missing-class recall,
  truncation, malformed distributions, nonfinite values and unsafe mutations.
  Export and clean-reload only a passing research candidate (FR-043–FR-046).
- [ ] T081 Wire the frozen candidate into selective shadow mode only, verify
  exactly one call for delegated cases and zero for deterministic-resolved
  cases, and run all authority, compatibility, offline, rollback and installed-
  artifact suites. Do not expose active cutover unless T082 passes (FR-040–FR-047,
  SC-003–SC-004, SC-011).
- [ ] T082 Restore the exact immutable database/vector baseline and execute the
  matched deterministic, original-Laya, rejected-V2 and selective-V3 arms on
  identical ordered cases and hardware. Publish raw rows, correct transitions,
  macro-F1, per-operation recall, missed-durable/false-store/wrong-target/
  unsafe rates, failures, invocation rate, p50/p95 latency and paired bootstrap
  intervals. Unless every sealed case has independent exact-contract human
  annotation, label all quality values as agreement with blinded machine weak
  supervision rather than correctness. Apply FR-047 without waiver
  (FR-044–FR-047, SC-005, SC-010).
- [ ] T083 If and only if T082 passes, prepare the independently versioned model
  artifact/card in a V3 repository/revision, add a rejected/superseded research
  notice to the V2 model card, select a new post-`2.3.9b1` beta version, prepare
  opt-in documentation, then follow the repository
  release-completion rule. If it fails, retain the model as private or clearly
  research-only, keep deterministic active, record the blocking outcomes and do
  not create a new release for the learned profile (FR-025–FR-027, FR-034,
  FR-039, FR-047).

**Checkpoint**: the selective model is either proven beneficial against the
same baseline and remains governed/reversible, or is explicitly rejected with
all negative evidence preserved. Training completion alone is never success.
