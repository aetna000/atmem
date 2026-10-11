# Feature Specification: AtMem Laya Formation Model

**Feature directory**: `specs/041-atmem-laya-formation-model`
**Created**: 2026-10-10
**Status**: Draft for approval; no training, publication, rental, or release authorized
**Target release**: AtMem `2.3.9b1`

## Outcome

AtMem will publish two independently usable Hugging Face artifacts: a synthetic
memory-formation decision dataset and a fine-tuned Laya decision model. The
optional model will improve bounded memory formation, storage and retrieval
decisions while AtMem remains the sole authority for source truth,
authorization, provenance, policy, canonical mutation and delivery. A
generative model is used only through the existing AtBot provider boundary when
a declared escalation condition occurs.

The beta succeeds when the installed product remains easy and backward
compatible on Windows, macOS and Linux; both artifacts pass publication gates;
and a frozen evaluation reports formation/store, retrieval and combined workflow
results against deterministic AtMem, the current Qwen profile, unmodified Laya
and a revision-pinned Jev service. A claim that the candidate beats Jev is
permitted only for a named workflow whose paired confidence interval clears
zero without a safety regression.

## User value

- A default AtMem installation continues to work locally without Laya, a model
  download, an accelerator, a provider account or network egress.
- A user can opt into one guided setup command, inspect readiness and fall back
  without migrating or losing canonical memory.
- Common formation choices become faster, cheaper and more predictable than a
  generative-only path; difficult cases still receive bounded escalation or
  explicit review rather than confident invention.
- Every accepted memory remains traceable to authorized source evidence, and a
  model can neither manufacture evidence nor bypass ownership, policy or scope.
- Windows, macOS and Linux users receive an honest compatibility matrix and
  actionable diagnostics for CPU, CUDA and Apple MPS paths.

## Scope and relationship to Spec 040

[Spec 040](../040-atmem-context-engine/spec.md) controls formation, retrieval,
governance and canonical context-engine contracts. This feature adds an optional
intelligence profile, public training artifacts and evaluation; it does not
replace Spec 040 authority, change its safe defaults, or import benchmark logic
into production. Existing Qwen and deterministic profiles remain compatible.

In scope:

1. A versioned synthetic dataset for typed formation, target-selection,
   retrieval-usefulness and escalation decisions.
2. A fine-tuned Laya model, tokenizer/configuration, calibration information,
   model card, checksums and exact lineage.
3. Optional AtMem integration, guided setup, status/doctor, deterministic
   fallback and bounded AtBot escalation.
4. Frozen formation/store, retrieval and combined workflow evaluation.
5. Conditional training on the user's Windows machine or Mac before any
   cost-capped Vast.ai rental.
6. Hugging Face staging and publication plus the coordinated `2.3.9b1` release
   plan.

Out of scope:

- Giving a model mutation, authorization, policy or source-truth authority.
- Training on private user histories, credentials, production stores, LoCoMo,
  LongMemEval, DolphinBench, sealed evaluation cases or their answers.
- Silently replacing the default profile, downloading weights on upgrade, or
  requiring Jev/Qwen/Laya for core operation.
- A general conversational model, autonomous retraining, website self-merge,
  leaderboard submission or an unqualified production-quality claim.

## Functional requirements

### Authority and runtime

- **FR-001** AtMem MUST bound input to already-authorized source regions and
  active canonical candidates before any model invocation.
- **FR-002** Laya MAY answer only versioned typed questions: operation
  (`ADD`, `UPDATE`, `SUPERSEDE`, `NOOP`, `REJECT`), memory class, durability,
  evidence support, ambiguity, contradiction, review need, bounded target
  selection and candidate retrieval usefulness/insufficient evidence. The
  profile MUST bind the effective input ceiling verified from the exact model
  and tokenizer revision in the T002 source manifest, preserve the complete
  question and finite-choice set, account for special tokens, and never silently
  truncate. Evidence that does not fit MUST be reduced only by a deterministic
  source-range policy with an explicit loss receipt or routed to
  escalation/review.
- **FR-003** AtMem MUST calculate and verify exact quotes, offsets, digests,
  ownership, scope, generations, admission policy, canonical mutations and
  delivery. Model text or scores MUST NOT be treated as source evidence.
- **FR-004** Every model decision MUST record model/revision, schema version,
  calibrated scores, selected choices, input/prompt digest, fallback/escalation
  reason, timing and the final authoritative outcome without logging secrets or
  unauthorized content.
- **FR-005** The Laya integration MUST be optional. Fresh installs and upgrades
  from `2.3.8` MUST preserve deterministic behavior and existing profiles until
  explicit activation; absence or failure MUST fall back safely.
- **FR-006** A guided command and noninteractive equivalent MUST install or
  select the pinned artifact, run compatibility checks, preview the change and
  require explicit activation. Status/doctor MUST show active profile, exact
  revision, device, calibration state and fallback readiness.

### Escalation

- **FR-007** Generative escalation MUST use the existing AtBot provider contract
  and occur only for configured ambiguity, coupled mutations, an unsupported
  normalized value, option overflow/truncation, or calibrated low confidence.
- **FR-008** Escalation MUST receive only the minimum authorized evidence and a
  bounded schema; it cannot expand scope. Timeout, provider failure, malformed
  output or denied egress MUST produce deterministic fallback or explicit
  review, never an implicit acceptance.
- **FR-009** Thresholds, maximum calls/tokens, timeout, retry, egress and cost
  limits MUST be explicit and testable. A user can disable escalation while
  retaining Laya.

### Synthetic dataset

- **FR-010** The first public dataset MUST contain at least 12,000 scenario
  states and 60,000 typed decisions spanning add/update/supersede/no-op/reject,
  temporal change, contradiction, duplicates, sensitive content, procedures,
  private/shared scope, insufficient evidence, target selection and retrieval
  usefulness.
- **FR-011** Every row MUST include stable scenario/question identifiers,
  authorized inputs, finite choices, deterministic expected answer(s), rationale
  metadata not required at inference, generator/template versions, seed,
  difficulty, safety tags, split and license/provenance fields. Dataset creation
  and runtime inference MUST call the same versioned tokenizer-exact packing and
  serialization module; parity tests MUST produce byte-identical model input and
  overflow receipts for the same scenario/question/evidence tuple.
- **FR-012** Labels MUST be derived from an executable scenario state and
  independently validated invariants, not accepted from an unverified generator
  narrative. Ambiguous cases MUST be labeled for review/escalation.
- **FR-013** Train, validation, calibration and sealed-test splits MUST be
  disjoint by fictional identity, template/scenario family, semantic chain and
  paraphrase cluster. Dataset generation MUST run leakage and near-duplicate
  checks before training.
- **FR-014** A pre-training stratified audit of at least 400 rows drawn only from
  train, validation and calibration MUST attain at least 99% target correctness
  and zero critical privacy, credential or license findings. Each high-risk tag
  (`sensitive`, `credential`, `private_scope`, `cross_scope`, `contradiction`)
  MUST contribute at least 60 audited examples, allowing overlap; this gives at
  least 95% probability of observing one or more defects when a tag's defect
  rate is 5%. After the model, thresholds and analysis are frozen, a different
  firewalled reviewer MUST audit a separately sampled sealed-test packet and
  MUST NOT participate in later generator, oracle, training or threshold changes.
  Any critical finding or required correction invalidates that sealed dataset
  and trained run: a new version and fresh split/training cycle are required.
  Failures block public visibility.
- **FR-015** Dataset documentation MUST disclose synthetic construction,
  limitations, class balance, split method, audit result and intended/non-
  intended uses. Synthetic results MUST NOT be presented as production evidence.

### Training and calibration

- **FR-016** Training MUST start from an exact Laya revision and retain encoder,
  head, question definitions, tokenizer, configuration, objective, seed,
  dependency, hardware and source-dataset revisions in a reproducible manifest.
- **FR-017** The experiment MUST compare the supported Laya objective (including
  RLCD/proper scoring where available) with a simpler cross-entropy control;
  objective choice is based only on training, validation and calibration
  evidence, not assumption. The sealed test is opened once after the objective,
  checkpoint, thresholds and claim analysis are frozen and MUST NOT be used to
  revise or reselect them.
- **FR-018** Training MUST detect nonfinite loss, class/choice collapse,
  truncation, overconfidence and calibration underpower. Calibration uses its
  isolated split; thresholds are chosen before opening the sealed test.
- **FR-019** The exported artifact MUST load in a clean environment from
  Safetensors without training code or pickle and reproduce the retained
  evaluation within the following frozen tolerances: on the same backend and
  dtype, at least 99.9% selected-choice agreement and maximum absolute normalized
  score delta of `1e-4`; across claimed backends, at least 99.5% selected-choice
  agreement and no more than 0.2 percentage-point absolute change in any primary
  aggregate. A backend outside these tolerances is not a claimed profile.

### Compute selection and secrets

- **FR-020** Before Vast.ai, the training operator MUST run recorded capability
  and smoke checks on both available local candidates: the Windows SSH machine
  (prefer CUDA when usable) and the Mac (MPS or CPU). The chosen local candidate
  is the one that can complete within the resource/time envelope: no unsupported
  operation, OOM or nonfinite result; at least 20% measured memory headroom;
  free artifact storage at least three times projected peak run storage; working
  checkpoint/resume; and projected completion of both objective controls within
  48 elapsed hours. If both qualify, choose the lower reliable projected elapsed
  time and record why.
- **FR-021** Vast.ai MAY be used only after both local candidates have a recorded
  infeasibility or failed representative smoke result. Selection MUST minimize
  estimated total cost—including compute, storage, transfer and retry risk—not
  merely hourly price, and require a verified/reliable CUDA offer with at least
  16 GiB VRAM.
- **FR-022** Vast.ai spend has a default hard ceiling of USD 20, no automatic
  top-up, and requires explicit owner approval to amend. Interruptible capacity
  is allowed only after checkpoint resume and off-instance synchronization are
  proven; the instance is destroyed promptly after verified artifact recovery.
- **FR-023** API tokens, SSH passwords and provider credentials MUST come from
  environment variables, interactive entry or an approved secret store. They
  MUST NOT appear in specs, source, commands, logs, datasets, artifacts or model
  cards. Only synthetic/public data may be copied to rented compute.
- **FR-024** Heavy generated/training artifacts on the Mac MUST use
  `/Volumes/MEM/AtMem-Laya-Formation/` with checksum-bound manifests; the Git
  repository retains only bounded metadata, code and small fixtures.

### Publication

- **FR-025** Dataset and model MUST use separate Hugging Face repositories.
  Upload first as private staging, using a least-privilege write token from the
  environment; validate inventory, secret scan, license, digests, cards and clean
  load before making either public.
- **FR-026** The public model card MUST bind exact base-model and dataset
  revisions, schema, metrics by decision class, calibration, platform evidence,
  limitations, AtMem version compatibility and generative escalation boundary.
- **FR-027** Publication state MUST be tracked independently for dataset, model,
  package, website PR merge and live website deployment. No state implies any
  other state.

### Evaluation and claims

- **FR-028** A frozen protocol MUST compare deterministic AtMem, the current
  pinned Qwen profile, unmodified Laya, fine-tuned Laya, a resolved/pinned Jev
  model and the Laya-plus-escalation profile where applicable. Inputs, authorized
  evidence, choices, budgets and hardware classes MUST be matched or differences
  disclosed.
- **FR-029** Jev evaluation MUST resolve the service model identity rather than
  retain a moving alias and freeze API/schema, typed questions, option ordering,
  prompt digest, egress authorization, latency, usage and cost evidence.
- **FR-030** Formation/store scoring MUST make exact canonical-state success the
  primary metric and report operation, class, target and support correctness,
  safety violations, review/escalation rate, latency, cost and failures.
- **FR-031** Retrieval scoring MUST use a frozen candidate pool and report MRR@5
  as primary, Recall@1/5/10, evidence coverage, abstention, latency and cost.
  Model arms MUST NOT change candidate-pool membership.
- **FR-032** Combined evaluation MUST score whether a stored state supports a
  future query and attribute failure separately to source, formation, mutation,
  nomination, ranking, packing and delivery.
- **FR-033** Results MUST be paired by scenario/cluster and report bootstrap 95%
  confidence intervals plus per-class results. “Beats Jev” is allowed only for
  the named workflow when the interval for the primary difference is entirely
  above zero and all safety, identity and matching gates pass. Aggregate gains
  cannot hide a safety or required-class loss.
- **FR-034** Negative or inconclusive comparisons MUST be published honestly.
  They do not block independent dataset/model publication if artifact safety and
  quality gates pass, but they block the corresponding superiority claim.
  A result from this synthetic dataset MUST be named explicitly as a synthetic
  AtMem Formation benchmark result and MUST NOT support a production or general
  customer-facing superiority claim. Any production-level “beats Jev” claim
  additionally requires a separately frozen, held-out public-corpus protocol at
  intended scale under the constitution and Spec 040, including LoCoMo for the
  memory-retrieval track and the applicable LongMemEval/store-to-retrieval
  workflow, with the same matchedness, safety and confidence gates.
  BEAM is not applicable to this typed formation/ranking claim because no large-
  workload scheduling behavior is being claimed; any later scheduling or
  large-workload claim re-enters the constitution's BEAM requirement.

### Compatibility and release

- **FR-035** Installed-artifact tests MUST cover Python 3.10–3.13 and declared
  Windows CPU/CUDA, macOS CPU/MPS and Linux CPU/CUDA profiles. Unsupported device
  combinations MUST fail with actionable diagnostics, not partial activation.
- **FR-036** Existing databases, CLI/MCP contracts, OpenClaw bridge behavior,
  AtBot and AtFlows integrations MUST remain backward compatible. New stored
  metadata MUST be additive, versioned and safely ignored by old profiles.
  The published AtMem `2.3.8` package—not an untagged or release-candidate
  checkout—is the authoritative upgrade baseline. Final upgrade evidence and
  `2.3.9b1` release are blocked until `2.3.8` is published and registry-verified;
  any earlier development result MUST be rerun against that exact artifact.
- **FR-037** Release preparation MUST add `docs/releases/v2.3.9b1.md`, align all
  participating package/installer pins, update the website manifest and guides,
  and execute repository, companion, OpenClaw, build, metadata, installed-
  artifact and website-doc gates.
- **FR-038** Publication MUST follow `docs/release-coordination.md`: commit and
  push reviewed changes before immutable annotated tags; publish AtBot first if
  it changed; wait for and verify package workflows, GitHub release, PyPI and npm
  artifacts; prepare a separate owner-reviewed private website PR and never
  self-merge it or call docs live before production verification.

## Acceptance scenarios

1. A `2.3.8` user upgrades without selecting Laya; no model is downloaded and
   formation/retrieval behavior remains on the existing profile.
2. A user runs guided setup on each declared platform, sees exact model/device
   readiness and preview, activates explicitly, then can roll back without data
   migration or canonical-memory loss.
3. Laya proposes an update to an authorized target; AtMem independently verifies
   the cited source range and policy before commit and records a complete receipt.
4. Laya returns low calibrated confidence; a configured AtBot escalation receives
   only authorized evidence. Provider failure yields review/fallback and no write.
5. Both local machines fail the representative training smoke; a cost report
   selects a qualifying Vast offer under the cap, resumes from an off-instance
   checkpoint, recovers verified artifacts and destroys the instance.
6. Private staging scans find a credential-like token; public visibility is
   blocked until regeneration and a clean rescan.
7. The fine-tuned model improves one aggregate metric but its paired interval
   overlaps zero or a safety class regresses; reports show the result and make no
   “beats Jev” claim.

## Success criteria

- **SC-001** The dataset meets FR-010–FR-015 and is publicly downloadable at an
  immutable revision with a passing audit receipt.
- **SC-002** The model meets FR-016–FR-019 and FR-025–FR-026 and is publicly
  loadable at an immutable revision from a clean Windows, macOS and Linux test
  environment for every claimed profile.
- **SC-003** Zero unauthorized writes, cross-scope disclosures, invented-source
  acceptances, credential findings or policy bypasses occur in safety suites.
- **SC-004** Optional setup, activation, rollback and provider-offline fallback
  pass clean-install and `2.3.8` upgrade tests with no forced download or schema
  migration.
- **SC-005** The evaluation package satisfies FR-028–FR-034 and can regenerate
  all published tables from checksum-bound raw results.
- **SC-006** On identical cases, hardware, dtype and batch policy, median
  Laya-only decision latency is at least 25% lower than the pinned Qwen
  generative profile and the paired cluster-bootstrap 95% confidence interval
  has an upper latency-ratio bound below `1.0`; latency and cost distributions
  are reported rather than asserted.
- **SC-007** Any Jev superiority statement satisfies FR-033; otherwise the beta
  publishes an explicit non-superiority or inconclusive result.
- **SC-008** Dataset, model, package and website states are each truthfully
  reported and the coordinated release checklist is complete before declaring
  `2.3.9b1` published.

## Assumptions and dependencies

- Laya's Apache-2.0 artifact and supported training/export interfaces remain
  available at pinned revisions; implementation must revalidate both.
- Jev access is optional external evaluation, requires explicit egress and may
  be omitted only with the comparison and associated claim marked blocked.
- Hugging Face repository identifiers are selected during implementation and
  frozen before public links are documented.
- The USD 20 Vast ceiling is a planning default, not spending authorization.
- AtMem `2.3.8` is currently a candidate, not an assumed published dependency;
  its verified publication is a hard prerequisite for final T034 evidence and
  any `2.3.9b1` release declaration.
- Approval of this specification authorizes implementation planning only.
