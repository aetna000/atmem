# Data Model

This model applies only to the replacement authentic-conversation dataset and
the model trained from it. The earlier fictional scenario dataset and every
derived checkpoint are superseded and cannot satisfy Spec 041.

## Immutable source layer

### `source_dataset`

Fields: `source_id`, repository/dataset identity, immutable revision, license,
collection method, human-origin evidence, retrieval time and inventory digest.

Invariant: the source must contain authentic human conversation. Generated
dialogue, generated continuations, synthetic paraphrases, translated replicas
and hand-authored conversation rows are ineligible.

### `conversation` and `turn`

`conversation` fields: stable source conversation/user/session identifiers,
scope key, source identity, language/script, timestamps where available and
content digest. `turn` fields: stable turn ID, order, role, original text and
source-row locator.

Invariant: text is immutable and remains in its original language. Annotations
never overwrite source content. Same-scope chronology and cross-user corpus
identity are distinct relationships.

### `observation`

Fields: observation ID, conversation/scope/turn identifiers, bounded authorized
content, source digest, eligibility state, exclusion reason and risk tags.

Invariant: every observation resolves to immutable source turns. It is not a
training example until bound to an immutable pre-state, actual retrieval result,
typed question and expected transition. Language/source metadata guides
sampling but is excluded from model-visible decision state.

## Scale and partition layer

### `experiment_scale_manifest`

Fields: manifest/version, `experiment_scale_percent`, full allocation, requested
and achieved counts, grouping keys, allocator version, seed, source inventory,
partition digests, exclusions and manifest digest.

Full allocation: 50,000 state-building observations; 20,000 training, 5,000
validation, 5,000 calibration and 20,000 sealed-test transitions; and 30,000
holdback observations. The currently authorized scale is 10%, requesting
5,000/2,000/500/500/2,000/3,000 respectively.

Invariant: identity, scope, conversation, chronology chain and exact/semantic
duplicate components remain intact. Each scope, including its state-building
prefix, belongs to exactly one split family. Whole-group isolation takes
precedence over exact row count, and requested versus achieved counts are always
recorded.

## Corpus relationship layer

### `fingerprint`, `embedding`, `duplicate_edge`, `duplicate_cluster`

Fields bind normalized exact hashes and multilingual semantic representations
to candidate IDs, similarity method/revision/score, edge kind and canonical
connected-component identity.

Invariant: the graph is computed corpus-wide before final splitting. A
cross-scope duplicate edge removes redundant training material; it does not by
itself mean that a user's memory decision is `DUPLICATE`. A same-scope
chronological duplicate requires an earlier canonical target.

## Canonical state and retrieval layer

### `canonical_memory`, `memory_revision`, `memory_relation`

Fields retain scoped opaque memory IDs, authorized source observations,
lifecycle, class, canonical content derived by AtMem, validity, generation,
revision and duplicate/update/supersession/forget relations.

Invariant: canonical memory is built by chronological replay and adjudicated
transitions, not by inserting every raw turn. Laya never authors canonical text.

### `state_snapshot`, `vector_snapshot`, `retrieval_receipt`

`state_snapshot` binds the SQLite bytes/schema, scope generations, canonical
state digest and source manifest. `vector_snapshot` binds memory membership,
embedding model/revision/configuration and index digest. `retrieval_receipt`
binds observation/pre-state, requested and returned counts, ordered opaque memory
IDs/scores/digests, truncation/completeness and retriever revision.

Invariant: a decision example cites one immutable pre-state and the actual
authorized same-scope retrieval result produced from it. Independent evaluation
restores that pre-state; trajectory evaluation evolves state chronologically.

## Stateful transition and independent judge layer

### `transition_example`

Fields: transition ID, partition, trajectory ID, pre-state snapshot and
generation, authorized observation, retrieval receipt, one typed question,
expected typed response, required target/evidence IDs, expected authoritative
operation, expected post-state digest, acceptable-abstention flag and provenance.

Invariant: no isolated utterance/disposition pair is eligible for training or
evaluation. Audit rationale and later confirming evidence are excluded from the
model-visible request.

### `judge_run`

Fields: judge (`codex` or `claude`), CLI/model version, rubric/schema/prompt
digests, pass purpose, read-only query policy, start/end state and run digest.

### `judgment`

Fields: immutable judgment ID, transition/judge/run/pass IDs, typed question and
response, expected operation/target/post-state, evidence IDs, confidence,
rationale, prior judgment ID, change reason, query receipt digest, latency,
output digest and validation state.

Invariant: each judge independently adjudicates every eligible state transition before it
can see the other judge's work. Later self-review passes may reference only
that judge's prior decision. Records are append-only; the orchestrator validates
and commits them.

Required self-review views are:

1. exact and multilingual-semantic duplicate clusters;
2. same-scope chronology;
3. language, class, risk and confidence strata; and
4. contradiction and outlier search.

Review stops at zero eligible changes or the frozen pass limit. Repeated runs
are not votes; each change requires an evidence-bound reason.

### `comparison`, `adjudication`, `final_label`

In dual mode, comparison begins only when both judges freeze required passes.
Exact agreement may proceed after deterministic validation. Disagreement
receives an isolated adjudication record; unresolved rows are rejected. If
Claude allowance is exhausted, an append-only policy event enables disclosed
Codex-only finalization only after every Codex review view freezes. `final_label`
exposes the exact mode, immutable source, available judge histories and any
adjudication.

## Training and runtime records

### `EvaluationRequestV2`, typed responses, `FormationRulingV2`, `DecisionReceiptV2`

`EvaluationRequestV2` contains state plus exactly one strict `choice`, `noul` or
`score` question. `ChoiceResponseV2` and `ScoreResponseV2` carry complete
probability data and separately calibrated confidence. The strict Jev
`NoulResponseV2` carries only the finite probability that its positive predicate
is true; it has no separate confidence field. None carries free-form reasoning
or generated memory. `FormationRulingV2` combines validated typed
responses. `DecisionReceiptV2` distinguishes classifier proposal from final
authoritative outcome. Model output never authorizes a mutation.

### `TrainingRunManifestV2`

Fields: authentic dataset revision and database snapshot digest, final-row
query/digest, base model, code/environment, objective, seeds, split/cluster
digests, hardware, checkpoints, metrics, calibration and export inventory.

Invariant: it rejects old synthetic and isolated-label manifest formats and
binds the exact scale, partition, snapshot, retrieval, transition, judge and
post-state manifests. Only the training partition optimizes the model;
validation, calibration and sealed test retain separate roles.

## State transitions

Dataset: `sourced -> eligibility_verified -> globally_clustered ->
scale_partitioned -> state_built -> snapshot_frozen -> retrieval_frozen ->
transition_adjudicated -> self_review_frozen -> compared -> accepted -> audited
-> private_staged -> verified -> public`.

Model: `blocked_until_dataset_verified -> initialized -> smoke_passed -> trained
-> calibrated -> held_out_evaluated -> exported -> private_staged -> verified
-> public`.

No prior synthetic dataset, model, receipt or public revision may enter either
transition chain.
