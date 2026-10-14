# Feature Specification: AtMem Laya Formation Model

**Feature directory**: `specs/041-atmem-laya-formation-model`
**Created**: 2026-10-10
**Status**: Approved and in implementation. The earlier isolated-row labeling
design and the always-on sequential V2 Noul/Choice/Score formation plan are
superseded. Matched 2026-10-14 evidence rejected both original and fine-tuned
Laya as full-path classifiers; the current scope is a selective, single-call
state-transition specialist evaluated against the same frozen database baseline.
Implementation is authorized initially at `experiment_scale_percent=10`;
raising the scale requires a later owner decision. Quality, cost,
compatibility, publication and release gates still fail closed.
**Target release**: a post-`2.3.9b1` beta whose version is selected only after
FR-047 passes. The published immutable `v2.3.9b1` tag MUST NOT be moved,
overwritten or represented as containing V3.

## Outcome

AtMem will publish three independently usable Hugging Face artifacts: a
checksum-bound scoped SQLite/vector baseline database, a multilingual dataset
of memory-state transition decisions derived from authentic human-origin
conversations, and a fine-tuned multilingual Laya decision model. A dataset
example is never an isolated utterance. It binds an
authorized new observation to the relevant memories retrieved from a frozen,
scoped SQLite and vector state; one strict Jev-style `choice`, `noul`, or
`score` question; the expected ruling; and the expected post-state. Labels are
contextual weak supervision and adjudication, not human ground truth.

Laya classifies bounded questions and returns calibrated structured judgments;
it never reads or mutates storage, generates canonical memory text, or acquires
authority. AtMem selects and shapes each question, validates the response,
rechecks governance and alone mutates canonical state. Exactly one semantic
classifier is used per formation transaction: the unchanged `2.3.8`
deterministic classifier, Laya, or Laya followed by configured escalation.
The historical V2 sequential plan remains research evidence but is not eligible
for activation. The selective V3 behavior is not shipped until T074–T083 and
its matched integration gates complete.

The beta succeeds when the installed product remains easy and backward
compatible on Windows, macOS and Linux; all three artifacts pass publication gates;
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

1. Versioned, multilingual, source-licensed state-transition datasets and
   reproducible scoped SQLite/vector snapshots for typed formation,
   target-selection, retrieval-usefulness and escalation decisions.
2. A fine-tuned `convaiinnovations/laya-multilingual` model,
   tokenizer/configuration, calibration information,
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
- Using LoCoMo anywhere in this feature, including training, pilot labeling,
  calibration, model selection, or evaluation.
- Treating machine labels as human annotations, translating source evidence
  into English for training, or allowing language identity to determine a
  memory decision.
- Silently replacing the default profile, downloading weights on upgrade, or
  requiring Jev/Qwen/Laya for core operation.
- A general conversational model, autonomous retraining, website self-merge,
  leaderboard submission or an unqualified production-quality claim.

## Functional requirements

### Authority and runtime

- **FR-001** AtMem MUST bound input to already-authorized source regions and
  active canonical candidates before any model invocation.
- **FR-002** Laya MAY answer only one versioned Jev-style typed question per
  invocation: `choice`, `noul`, or `score`. `choice` MUST expose 2–255 finite
  option identifiers and return exactly one option, a complete normalized
  probability distribution and calibrated confidence. `noul` MUST state one
  unambiguous positive predicate and return `noul`, the probability that it is
  true; the strict Jev response contains no separate Noul confidence field.
  `score` MUST expose 2–10 ordered rubric levels and return zero-based
  `probabilities`, their `legend`, the continuous expected `score` and calibrated
  confidence. Choice confidence is separately calibrated and MUST NOT be
  required to equal the winning class probability. Unknown keys/options,
  nonfinite values, invalid sums, a Choice argmax mismatch, a Score legend
  mismatch or a Score expected-value mismatch are invalid. The
  profile MUST bind the exact model/tokenizer ceiling, preserve the complete
  question and options/rubric, account for special tokens, and never silently
  truncate. Evidence that does not fit MUST produce an explicit loss receipt
  and review/escalation; it MUST NOT be silently summarized by the classifier.
- **FR-003** AtMem MUST calculate and verify exact quotes, offsets, digests,
  ownership, scope, generations, admission policy, canonical mutations and
  delivery. Model text or scores MUST NOT be treated as source evidence.
- **FR-004** Every model decision MUST record the typed question and exact
  options/rubric, model/revision, schema and formation-plan versions, complete
  probability data, calibrated confidence when the strict response supplies it,
  selected choice/score,
  authorized input and retrieval digests, canonical generation,
  fallback/escalation reason, timing, classifier identity, and final AtMem
  authority outcome without logging secrets or unauthorized content. The
  receipt MUST distinguish the classifier proposal from the committed,
  refused, stale or reviewed state transition.
- **FR-005** The Laya integration MUST be optional. Fresh installs and upgrades
  from `2.3.8` MUST preserve byte- and behavior-compatible deterministic
  classification until explicit activation. Every formation-capable entry
  point MUST select exactly one semantic classifier per transaction:
  `deterministic` uses only the `2.3.8` decision rules; `laya` delegates semantic
  judgment only to Laya; and `laya-escalation` delegates first to Laya and then,
  only under declared conditions, to escalation. Governance validation is not a
  second semantic classification. AtMem MUST NOT silently replace a valid Laya
  ruling with its deterministic classification. Invalid, stale, unauthorized,
  incomplete or under-threshold responses fail closed to an explicit review or
  the configured, receipted failure policy. The exact single-classifier and
  valid-ruling semantics are normative in
  `contracts/authentic-memory-understanding-v2.md`; implementations MUST NOT
  weaken them by interpreting this summary independently.
- **FR-006** A guided command and noninteractive equivalent MUST install or
  select the pinned artifact, run compatibility checks, preview the change and
  require explicit activation. A newly installed or changed model/revision MUST
  first run in a measurable non-influencing shadow profile over the configured
  qualification cases; only an explicit second cutover may let its rulings
  influence formation. Status/doctor MUST show shadow/active state, exact
  revision, device, calibration state and fallback readiness.
- **FR-006a** Every `remember`, automatic-ingestion, conversation-capture,
  OpenClaw, AtBot and import/reconciliation path that can create or alter
  ordinary memory MUST converge on one formation service when `laya` or
  `laya-escalation` is active. Administrative migration and verified restore are
  governed system operations and MUST be identified separately. Integration
  tests MUST prove there is no direct-write bypass and no duplicate semantic
  classification.
- **FR-006b (superseded V2 research behavior)** The rejected V2 formation plan
  selected and conditioned typed questions. Laya did not select its own question or emit
  free-form reasoning. The minimum plan contains Noul gates for context
  sufficiency and durability; a Choice operation over `STORE_NEW`,
  `UPDATE_EXISTING`, `SUPERSEDE_EXISTING`, `DUPLICATE`, `DO_NOT_STORE` and
  `FORGET_EXISTING`; a conditional Choice over retrieved opaque target IDs; and
  an advisory Score for future utility when a durable mutation is proposed.
  `REVIEW` is an AtMem outcome for abstention, insufficient/overflowed context,
  invalid output or policy—not a memory mutation generated by Laya.
  This sequential learned plan MUST NOT be used by the active V3 path; FR-040
  replaces it with one joint Choice invocation.
- **FR-006c** AtMem MUST combine validated typed responses from V2 research or
  the single validated V3 joint Choice into one internal
  formation ruling, re-read the referenced canonical generation and targets,
  enforce scope/evidence/lifecycle/policy, and atomically commit or explicitly
  refuse/review the transition. A valid authorized Laya classification MUST
  follow the normative valid-ruling semantics referenced by FR-005. Laya MUST
  NOT generate replacement memory text; AtMem
  derives the canonical representation only from authorized observation
  evidence and preserves revision/supersession provenance.

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

### Stateful authentic-conversation transition dataset

- **FR-010** The eligible source pool MUST contain 130,000 source-licensed
  authentic human–AI conversation observations with human-authored user turns.
  It MUST be partitioned by whole source identity, conversation, scope,
  chronological chain and exact/semantic duplicate component into the full-scale
  allocation below. No row may cross partitions. LoCoMo and all other generated
  dialogue, generated continuations, synthetic paraphrases, translated replicas
  and hand-authored replacement rows are excluded from training and evaluation.

  | Partition | Full-scale allocation | Purpose |
  | --- | ---: | --- |
  | State-building history | 50,000 | Build adjudicated canonical SQLite/vector state |
  | Training transitions | 20,000 | Optimize Laya typed judgments |
  | Validation transitions | 5,000 | Select checkpoints and training settings |
  | Calibration transitions | 5,000 | Fit probabilities, thresholds and abstention |
  | Sealed test transitions | 20,000 | Paired base-versus-tuned confirmation |
  | Holdback/stress pool | 30,000 | Later multilingual and distribution-shift evaluation |

  The build MUST accept `experiment_scale_percent` in `(0,100]`. Counts are
  deterministically derived from the full-scale allocation, while whole-group
  isolation takes precedence over exact count; each manifest records requested
  and achieved counts plus exclusions. The presently authorized value is `10`,
  yielding targets of 5,000/2,000/500/500/2,000/3,000 respectively. Sampling,
  partitioning, contracts and gates MUST be identical at every scale. A 10%
  artifact MUST be labeled `10%-scale` and MUST NOT claim full-scale evidence.
  Every partition MUST achieve at least 90% of its scaled target and all
  required action/language/safety coverage floors, or the build fails rather
  than publishing under that scale label. Any higher threshold declared in the
  frozen run manifest takes precedence. The manifest validator MUST also prove
  that each scope belongs to exactly one split family, including the
  state-building prefix associated with that family; a scope used to build a
  training pre-state cannot also back validation, calibration, sealed-test or
  holdback transitions, and conversely.
  Superseded isolated weak labels MAY be used only as deterministic sampling
  signals to enrich authentic state and rare-action coverage. They MUST be
  excluded from model-visible input and MUST NOT become canonical state,
  transition targets, training labels or evaluation labels; every selected row
  requires fresh state-aware adjudication. The manifest MUST disclose the
  selector, signal distributions and this non-target use.
- **FR-011** Every decision example MUST bind stable source, conversation,
  scope, trajectory, observation and question identifiers to: the immutable
  pre-state snapshot/generation; the original-language authorized observation;
  the actual same-scope memories retrieved by AtMem with scores and digests; the
  exact typed question and finite options/rubric; the expected typed response;
  any required target/evidence identifiers; the expected canonical transition
  and post-state digest; whether abstention is acceptable; and provenance,
  adjudication, safety, language, split and license fields. Rationales and later
  confirming observations are audit evidence, never model-visible inference
  targets. Dataset creation and runtime inference MUST call the same versioned,
  tokenizer-exact packer and typed response validators.
- **FR-012** Codex CLI and, while its locally authenticated allowance remains
  available, independently invoked Claude CLI MUST label original-language
  evidence under the same frozen rubric. If Claude allowance is exhausted, the
  run MAY continue in explicitly recorded `codex_only_credit_exhausted` mode;
  the card and manifest MUST NOT call those rows dual-model verified. Rows with
  disagreement, missing evidence, invalid schema, unsupported inference,
  language mismatch or unresolved ambiguity MUST be rejected or sent to a
  separately recorded adjudication pass. Labels MUST never be described as
  human ground truth. Ambiguous cases MUST be labeled for review/escalation.
  The manifest and data card MUST disclose the accepted row count and fraction
  by judge mode for every split; no aggregate may be called dual-model verified
  unless every row contributing to it was independently judged by both named
  models.
- **FR-012a** Corpus labeling MUST invoke locally authenticated Codex CLI and
  Claude CLI with schema-constrained non-interactive output. Direct OpenAI or
  Anthropic SDK/API labeling is prohibited, and API-key environment variables
  MUST be removed from both CLI subprocesses.
- **FR-012b** Each available CLI judge MUST independently adjudicate the
  state-aware transition rather than an isolated candidate. The judge receives
  the authorized observation, frozen pre-state, actual retrieval result,
  relevant chronology and permitted typed questions, then audits its own
  decisions through separately recorded corpus-wide views: exact/semantic
  duplicate clusters; same-scope chronology and state evolution;
  language/class/risk/confidence strata; and contradiction/outlier searches.
  Audit passes MUST retain the previous and revised decision, purpose, query
  receipt and evidence-bound change reason. A judge MUST NOT see the other
  judge's decisions until both have frozen their required self-review passes.
  Repeated passes MUST converge under a declared stopping rule and MUST NOT be
  reduced to majority voting over repeated prompts. Only then may comparison
  and separately recorded adjudication occur.
- **FR-013** Train, validation, calibration, sealed-test and holdback split
  families MUST be disjoint by source conversation, user/session identity where
  available, scope, chronology chain, semantic cluster and near-duplicate
  component. State-building observations inherit their scope's split family and
  serve only as the chronological prefix used to construct that family's
  pre-state; they are not optimization examples. A test scope's earlier
  observations may therefore build its test pre-state, but neither its pre-state
  content nor its later transitions may enter optimization, checkpoint selection
  or calibration.
  LongMemEval, DolphinBench and the external multilingual consistency evaluation
  remain test-only and MUST be decontaminated before training.
- **FR-013a** The work database MUST preserve immutable conversation text and
  provenance separately from annotations and canonical state. It MUST build
  scoped canonical memories by chronological replay, retain lifecycle and
  supersession links, and freeze checksum-bound SQLite plus vector-index
  snapshots with schema, embedding model/revision, configuration, source and
  canonical-state manifests. Unrelated users MUST remain separate security
  scopes even when one physical database is used. Judges receive a restricted
  read-only query surface over the whole eligible corpus, including sort,
  filter, row/scope/chronology/cluster lookup, lexical search, semantic-neighbor
  search and aggregate inspection. Judges MUST NOT edit source rows, duplicate
  graphs, the other judge's records or final labels; validated append-only
  receipts are committed by the orchestrator.
- **FR-014** Before any scale increase or training run, a stratified stateful
  pilot MUST measure transition adjudication agreement, rejection rate, action
  and target balance, retrieval coverage, CLI latency and utilization by
  language, plus cost only when the CLI emits it. The accepted
  corpus MUST have zero schema, credential,
  source-license or known-PII findings under automated full-corpus gates. Each
  high-risk tag
  (`sensitive`, `credential`, `private_scope`, `cross_scope`, `contradiction`)
  MUST contribute at least 60 independently verified pilot examples, allowing
  overlap. Sealed evaluation labels MUST be frozen by a blinded adjudication
  authority that did not produce the training labels and cannot inspect base or
  tuned model predictions; pre-existing public annotations are used only where
  they express the same state-transition contract. The manifest MUST name the
  authority, independence controls and any machine-judgment dependence, and MUST
  NOT call machine adjudication human ground truth. Unless every reported
  sealed item has independently verified human annotation under this exact
  contract, all sealed metrics MUST be titled and described as agreement with
  blinded machine weak supervision, not correctness or human-ground-truth
  accuracy. A human audit of only a sample may validate process quality but
  cannot convert unaudited rows into human ground truth. Any critical provenance, privacy,
  leakage or label-contract finding invalidates that dataset version and trained
  run; failures block public visibility.
- **FR-015** Dataset documentation MUST disclose source composition, organic
  production versus controlled human study provenance, snapshot construction,
  retrieval configuration, transition-adjudication method, teacher dependence,
  `experiment_scale_percent`, requested/achieved partition counts, limitations,
  per-language/per-action/per-question balance, group-disjoint split method,
  audit result and intended/non-intended uses. The public viewer MUST expose
  useful columns for observation, bounded retrieved state, typed question,
  expected response and expected transition without exposing private or
  disallowed source content. Machine-adjudicated results MUST NOT be presented
  as human ground truth or independent production evidence.

### Language invariance

- **FR-015a** Training MUST start from the exact immutable revision of
  `convaiinnovations/laya-multilingual`. The English Laya checkpoint is a
  comparison arm only and MUST NOT be the released model's base.
- **FR-015b** Source evidence MUST remain in its original language. Language and
  country metadata are provenance and sampling inputs only and MUST NOT appear
  in the model-visible decision state. Translation is an agent presentation
  concern outside the formation-policy model.
- **FR-015c** Fixed language-neutral choice identifiers and one shared decision
  head MUST be used across languages. Training sampling MUST cap dominance by
  any language and cover multiple scripts; duplicated translations MUST NOT be
  counted as independent training rows.
- **FR-015c.1** The accepted corpus MUST contain 50% English; 20%
  Chinese; 5% each French, Spanish, Arabic and German; 1% each Portuguese,
  Japanese, Russian, Indonesian and Korean; and 5% collectively from all
  remaining supported languages, including Hindi and Urdu. A source shortage
  MUST fail the build rather than be filled with generated or translated
  conversation.
- **FR-015d** Evaluation MUST report per-language macro-F1, critical false-store
  rate, abstention/review rate and calibration, plus worst-language performance
  and the maximum gap from English. Aggregate accuracy cannot pass when a
  required language fails its safety or minimum-quality gate. A language-level
  quality gate is eligible only with at least 100 accepted sealed examples and
  at least 50 accepted calibration examples for that language at the evaluated
  scale. Under-powered languages remain in aggregate and descriptive results,
  with exact counts and intervals, but MUST NOT be represented as individually
  powered pass/fail findings. Safety findings and any observed unsafe mutation
  remain blocking regardless of sample size.
- **FR-015e** Cross-language semantic consistency MUST be evaluated on a frozen,
  test-only parallel human-created corpus. Machine translations MUST NOT be used
  as training evidence or claimed as real-world conversations.

### Training and calibration

- **FR-016** Training MUST start from the exact multilingual Laya revision and
  optimize only state-aware `choice`, `noul` and `score` examples built from the
  training-transition partition. It MUST retain encoder, typed heads, question
  definitions, tokenizer, formation-plan version, snapshot/dataset revisions,
  configuration, objective, reward components, seed, dependencies and hardware
  in a reproducible manifest. The model learns judgments, targets and calibrated
  scores; it MUST NOT learn or emit canonical memory text or perform mutations.
- **FR-017** The experiment MUST compare the supported Laya objective (including
  RLCD/proper scoring where available) with a simpler cross-entropy control;
  rewards MUST score typed-action correctness, required-target correctness,
  exact post-state validity, later retrieval utility, calibration and appropriate
  abstention, with explicit penalties for false storage, duplicate creation,
  wrong/cross-scope targets and unsupported forgetting. Objective choice is
  based only on training, validation and calibration evidence. The frozen
  unmodified Laya baseline and final tuned model MAY both run on the identical
  sealed test for a paired comparison, but sealed results MUST NOT influence
  objective, checkpoint, threshold, prompt, question or training-data selection.
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
- **FR-022** Paid training compute has separate hard ceilings of USD 8 on
  Vast.ai and USD 11 of existing Hugging Face credit, with no automatic top-up;
  either ceiling requires explicit owner approval to amend. RunPod is
  prohibited. Vast.ai is preferred after local infeasibility; Hugging Face
  compute may be used only as a fallback and MUST remain inside its separate
  USD 11 credit ceiling.
  These are cumulative Spec 041 ceilings, not fresh per-phase allowances.
  Before T079, the operator MUST reconcile provider ledger totals with all
  prior Spec 041 receipts and calculate the remaining balance. No instance may
  launch unless worst-case cumulative spend remains within the applicable cap.
  Interruptible capacity
  is allowed only after checkpoint resume and off-instance synchronization are
  proven; the instance is destroyed promptly after verified artifact recovery.
- **FR-023** API tokens, SSH passwords and provider credentials MUST come from
  environment variables, interactive entry or an approved secret store. They
  MUST NOT appear in specs, source, commands, logs, datasets, artifacts or model
  cards. Only source-licensed public authentic-conversation data that passed the
  privacy/egress gate may be copied to rented compute.
- **FR-024** Heavy derived/training artifacts on the Mac MUST use
  `/Volumes/MEM/AtMem-Laya-Formation/` with checksum-bound manifests; the Git
  repository retains only bounded metadata, code and small fixtures.

### Publication

- **FR-025** Database snapshot, transition dataset and model MUST use three
  separate Hugging Face repositories. The database artifact MUST include the
  loadable SQLite state, vector index, schema, embedding revision/configuration,
  source/canonical manifests, licenses, integrity verifier and example queries;
  it MUST exclude judge-private annotations, secrets and content lacking
  redistribution permission. The public database is a sanitized research-corpus
  fixture containing only redistribution-cleared public source material and
  derived benchmark state; it is not a production AtMem evidence store and MUST
  NOT claim the constitution's full-fidelity encrypted-evidence profile. Product
  evidence stores, backups and exports remain subject to the encryption and
  application-mediated-access requirements. Each artifact is independently useful outside
  AtMem and has independent version, license, privacy, integrity, clean-load and
  anonymous-redownload gates.
  Upload first as private staging, using a least-privilege write token from the
  environment; validate inventory, secret scan, license, digests, cards and clean
  load before making any artifact public.
- **FR-026** The public model card MUST bind exact base-model and dataset
  revisions, schema, metrics by decision class, calibration, platform evidence,
  limitations, AtMem version compatibility and generative escalation boundary.
- **FR-027** Publication state MUST be tracked independently for database,
  dataset, model, package, website PR merge and live website deployment. No
  state implies any other state. Before replacement publication, already-public
  fictional/isolated V1 artifact cards MUST be updated with an unambiguous
  deprecated/superseded notice and links to the replacement lineage; they MUST
  not be deleted or rewritten as authentic evidence.

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
  primary metric. A fully correct transition requires the correct operation,
  correct target when required, governance acceptance when mutation is expected,
  and the expected post-state. Reports MUST also include action macro-F1,
  per-action recall/precision, conditional target accuracy, false-store and
  duplicate-creation rates, unsafe mutation, appropriate abstention,
  probability calibration, review/escalation, latency, cost and failures.
- **FR-031** Retrieval scoring MUST use a frozen candidate pool and report MRR@5
  as primary, Recall@1/5/10, evidence coverage, abstention, latency and cost.
  Model arms MUST NOT change candidate-pool membership.
- **FR-032** Combined evaluation MUST score whether a stored state supports a
  future query and attribute failure separately to source, formation, mutation,
  nomination, ranking, packing and delivery. It MUST include both independent
  transition evaluation from a restored pre-state and chronological trajectory
  replay where an earlier committed decision changes later retrieval.
- **FR-033** Results MUST be paired by scenario/cluster and report bootstrap 95%
  confidence intervals plus per-class results. “Beats Jev” is allowed only for
  the named workflow when the interval for the primary difference is entirely
  above zero and all safety, identity and matching gates pass. Aggregate gains
  cannot hide a safety or required-class loss.
- **FR-034** Negative or inconclusive comparisons MUST be published honestly.
  They do not block independent dataset/model publication if artifact safety and
  quality gates pass, but they block the corresponding superiority claim.
  A result from this machine-labeled training dataset MUST be named explicitly
  as a weak-supervision training-set result and MUST NOT support a production or general
  customer-facing superiority claim. Any production-level “beats Jev” claim
  additionally requires a separately frozen, held-out human-origin conversation
  protocol at intended scale under the constitution and Spec 040. LongMemEval
  MAY be reported separately as a long-history benchmark but cannot substitute
  for authentic-conversation confirmation. LoCoMo is excluded. The same
  matchedness, safety and confidence gates apply.
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

### Selective single-call decision revision

- **FR-039** The 2026-10-14 three-way operational outcome in
  `RandD/2026-10-14-laya-memory-decision-outcome.md` is a blocking design input.
  Original Laya and the first fine-tuned V2 checkpoint MUST remain
  research-only. Their artifacts, raw receipts and negative results MUST be
  preserved; neither checkpoint may be silently relabelled, activated or used
  as evidence that a learned profile improves AtMem.
- **FR-040** The replacement learned path MUST use one model invocation and one
  strict finite Choice. AtMem constructs 2–255 opaque options that jointly
  encode an operation and, when required, one already-authorized target, for
  example `STORE_NEW`, `DO_NOT_STORE`, `UPDATE_EXISTING:target_0`,
  `SUPERSEDE_EXISTING:target_0` or `DUPLICATE:target_0`. The model returns only
  one selected option, its complete normalized probability distribution and
  calibrated confidence. AtMem maps the opaque option through its retained
  server-side table, revalidates authority and performs or refuses the
  transition. The model MUST NOT receive or generate mutation authority,
  canonical memory text, free-form reasoning or unrestricted identifiers.
  The option constructor MUST cap authorized targets deterministically at 32,
  preserve any exact-match target required by policy, and prove that the final
  joint option count is at most 255. If required targets cannot be represented
  within the option and token ceilings, the router records option overflow and
  returns review without invoking the model.
- **FR-041** A selective router MUST preserve the deterministic path for cases
  resolved by existing exact, structural or policy rules and invoke the learned
  specialist only for a versioned, receipted ambiguity predicate. The predicate
  may use retrieval scores, exact fingerprints, candidate count, lifecycle,
  source type and policy metadata, but MUST NOT make and then override the same
  semantic classification delegated to Laya. Every transaction records
  `deterministic_resolved`, `model_delegated`, `model_abstained`,
  `authority_rejected` or `runtime_failed`. Shadow mode MUST compute but never
  apply learned rulings; active mode requires a separate explicit cutover.
- **FR-042** The new training view MUST operate at transition level rather than
  question level. Each example contains the authentic authorized observation,
  actual same-scope retrieved pre-state, exact finite joint options, expected
  option, expected post-state and provenance. It MUST use the same V3 packer and
  option constructor as runtime. Training, validation, calibration and sealed
  evaluation remain split-disjoint under FR-013. Synthetic, translated,
  hand-authored or sealed-test observations remain prohibited.
- **FR-043** Before optimization, the training manifest MUST report transition
  counts for every deployable operation and target-bearing relation. A class
  absent from training cannot be exposed as an automatic learned action. A
  class with fewer than 100 distinct authentic training trajectories remains
  descriptive/research-only and cannot be activated. Balancing MUST select or
  weight authentic examples without creating conversation text, copying one
  observation across split families or representing repeated oversamples as
  independent evidence.
- **FR-044** Model selection MUST prioritize sequential exact-transition
  accuracy and macro-F1, with explicit asymmetric penalties for missed durable
  memory, false storage, wrong-target mutation, unsupported forgetting and
  runtime failure. Aggregate question accuracy and a majority-class advantage
  are ineligible selection criteria. A candidate MUST beat both deterministic
  AtMem and the always-majority control on the declared primary metric without
  regression in required-class recall or safety.
- **FR-045** Training MUST include authentic on-policy trajectory states: the
  observation text remains unchanged, but later pre-states are produced by
  replaying earlier candidate decisions. This is not synthetic conversation
  generation. The manifest distinguishes teacher-forced and on-policy states,
  records their source trajectory and prevents sealed outcomes from affecting
  training or selection.
- **FR-046** Runtime packing MUST bound candidates before model invocation with
  the same deterministic top-k/byte/token policy used during training. Mandatory
  observation, option and provenance fields MUST always fit; an over-budget
  item becomes explicit review and a recorded failure, never truncated input.
  Strict validators MUST accept numerically normalized distributions within a
  documented tolerance and reject nonfinite, negative, missing or materially
  inconsistent values. Training and runtime MUST pass byte-identical fixtures
  for candidate ordering, target aliases, option construction, serialization,
  tokenizer IDs, token counts and overflow receipts. Option-list and evidence-
  token overflow use the same fail-closed review/receipt policy.
- **FR-047** The replacement is eligible for active beta only when a matched
  replay from the same immutable SQLite/vector baseline reports zero malformed
  responses and zero context overflows, improves exact decisions over
  deterministic AtMem with a paired 95% confidence interval above zero, has no
  required-class or safety regression, and meets p50 `<=30 ms` and p95 `<=75
  ms` on at least one declared local profile. Failure leaves the model in
  shadow/research mode and blocks user-benefit and release claims without
  weakening deterministic AtMem.

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
8. With `experiment_scale_percent=10`, the builder deterministically targets
   5,000 state-building observations, 2,000 training, 500 validation, 500
   calibration, 2,000 sealed-test and 3,000 holdback rows, preserves whole-group
   isolation, and records any count shortfall. Re-running at `100` uses the same
   contracts and gates without code changes or reuse of 10%-scale test outcomes
   for model selection.
9. In `laya` mode an explicit preferred-name correction retrieves the active
   name memory, Laya answers the versioned Noul/Choice/Score questions, AtMem
   validates a `SUPERSEDE_EXISTING` ruling and commits a linked revision. The
   deterministic semantic classifier is never invoked for that transaction.
10. The same observation in `deterministic` mode follows the published `2.3.8`
    behavior, invokes no model, and produces no Laya artifacts or receipts.
11. A retrieved state contains two semantically plausible targets. The
    selective router delegates once with joint action-target options, Laya
    returns one normalized Choice response, and AtMem either commits the mapped
    authorized transition or records abstention/rejection; no preliminary
    durability model call occurs.
12. An observation is resolved by an exact deterministic rule. The specialist
    is not loaded or invoked and the receipt records `deterministic_resolved`.
13. The new candidate fails any FR-047 gate. Setup continues to expose only
    deterministic active behavior and may expose the candidate solely in
    non-influencing shadow/research mode.

## Success criteria

- **SC-001** The database snapshot and dataset meet FR-010–FR-015 and FR-025 and
  are independently publicly downloadable at immutable revisions with passing
  audit receipts, frozen SQLite/vector manifests, clean-load/anonymous-
  redownload evidence and truthful scale labels.
- **SC-002** The model meets FR-016–FR-019 and FR-025–FR-026 and is publicly
  loadable at an immutable revision from a clean Windows, macOS and Linux test
  environment for every claimed profile.
- **SC-003** Zero unauthorized writes, cross-scope disclosures, invented-source
  acceptances, direct-write formation bypasses, double semantic classifications,
  credential findings or policy bypasses occur in safety suites.
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
- **SC-009** On the frozen sealed transition set, raw results can reproduce the
  paired base-Laya versus tuned-Laya table, including fully correct transition
  count, macro-F1, target accuracy, exact post-state accuracy, false-store,
  duplicate creation, unsafe mutation, abstention, Brier/ECE calibration and
  bootstrap confidence intervals; no sealed result affects model selection.
  Unless the whole sealed set has exact-contract human annotation, the table
  labels these quantities as agreement with blinded machine weak supervision
  and never as human-ground-truth correctness.
- **SC-010** The selective V3 raw results reproduce one matched table for
  deterministic AtMem, original Laya, rejected V2 fine-tuned Laya and the new
  selective candidate from the same immutable baseline and hardware profile,
  including correct transitions, macro-F1, per-operation recall, safety,
  runtime failures, model invocation rate and p50/p95 end-to-end latency.
  Unless every sealed case has independent exact-contract human annotation,
  the table MUST describe agreement with blinded machine weak supervision and
  MUST NOT label the values as human-ground-truth correctness.
- **SC-011** Every active learned transaction performs exactly one model call;
  deterministic-resolved transactions perform zero. Tests detect duplicate
  semantic classification, direct-write bypasses and any invocation of the
  superseded sequential durability gate.

## Assumptions and dependencies

- Laya's Apache-2.0 artifact and supported training/export interfaces remain
  available at pinned revisions; implementation must revalidate both.
- Jev access is optional external evaluation, requires explicit egress and may
  be omitted only with the comparison and associated claim marked blocked.
- Hugging Face repository identifiers are selected during implementation and
  frozen before public links are documented.
- The owner has authorized separate ceilings of USD 8 on Vast.ai and USD 11 of
  Hugging Face credit for this run; there is no automatic top-up and RunPod is
  excluded.
- AtMem `2.3.8` and `v2.3.9b1` are published immutable historical baselines.
  V3 requires a new version and cannot alter either tag or its package claims.
- Approval authorizes implementation at `experiment_scale_percent=10` and the
  already-declared compute ceilings. Raising scale, increasing either ceiling or
  bypassing any safety/publication/release gate requires a later owner decision.
