# Tasks: AtMem Laya Formation Model

**Inputs**: `spec.md`, `plan.md`, `research.md`, `data-model.md`,
`contracts/formation-decision-v1.md`, `quickstart.md`
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
  host and Mac, and a conditional Vast total-cost worksheet with USD 20 hard cap,
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
  a qualifying instance under the USD 20 cap (FR-021–FR-023).
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
- [x] T042A Before any production-level or general customer-facing Jev
  superiority claim, run the separately frozen held-out public-corpus protocol
  at intended scale with LoCoMo and the applicable Spec 040 LongMemEval/store-to-
  retrieval workflow, apply the same matching/safety/confidence gates, and record
  a blocked claim when this evidence is absent or fails (FR-033–FR-034, SC-007).

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
- [ ] T047 Prepare a separate owner-reviewed source-pin refresh PR in the private
  website repository; do not merge it or claim deployment, and record website PR
  merged/live states separately (FR-027, FR-038).
- [ ] T048 Commit and push the clean reviewed release changes. If AtBot changed,
  create/push its annotated tag first and verify its workflow/PyPI artifact;
  otherwise record unchanged exact pin (FR-038).
- [ ] T049 Create and push immutable annotated `v2.3.9b1` on the exact reviewed
  commit, wait for `publish`, and verify prerelease URL, AtMem PyPI version and
  matching OpenClaw npm bridge; never move a published tag (FR-038).
- [ ] T050 Publish the final release record with branch, commit, tags, workflow,
  release URL, package versions, both Hugging Face revisions and separate website
  PR/live states; distinguish candidate pushed from release published (SC-008).

**Completion**: both Hugging Face artifacts are public and verified, optional
product behavior passes compatibility/safety gates, evaluation claims are
evidence-bound, and the coordinated beta publication is independently verified.
