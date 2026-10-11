# Data Model

## `FormationScenarioV1`

Fields: `scenario_id`, `fictional_identity_group`, `template_family`,
`semantic_chain_id`, `paraphrase_cluster_id`, ordered `evidence_events`,
`initial_state`, `expected_final_state`, `scope_fixture`, `difficulty`,
`safety_tags`, `generator_version`, `seed`, `license_provenance`.

Invariant: the expected state is reproducible from initial state and events by
the oracle; no field contains real user data or a secret.

## `TypedDecisionExampleV1`

Fields: `example_id`, `scenario_id`, `question_id`, `question_type`, bounded
`authorized_input`, ordered `choice_ids`, `expected_choice_ids`, `allow_abstain`,
`oracle_receipt`, `audit_rationale`, `split`, `content_digest`.

Invariant: every expected choice belongs to the supplied finite set; target IDs
resolve inside the authorized candidate set; `split` is group-disjoint. The
authorized input and overflow receipt come from the same versioned packer used
at runtime and pass a byte-identical parity fixture.

## `QuestionDefinitionV1`

Fields: `question_id`, `semantic_version`, `kind`, `prompt_template`, choice
semantics, cardinality, score interpretation, abstention behavior, calibration
method, tokenizer revision, effective token ceiling, reserved-token calculation,
overflow policy and compatibility range.

Invariant: a digest change requires a new version and invalidates an unmatched
calibration bundle.

## `CalibrationBundleV1`

Fields: model/data/question revisions, per-question thresholds or calibration
parameters, calibration sample counts, reliability metrics, selection procedure,
created time and digest.

Invariant: built only from the calibration split; sealed test labels are not
available to threshold selection.

## `DecisionReceiptV1`

Fields: request ID, authorized source/candidate digests, canonical generation,
model and revision, question-schema digest, device, selected choices and scores,
calibration identity, token counts, included source ranges, overflow/loss receipt,
confidence result, fallback/escalation reason, latency, provider usage,
authoritative disposition and audit digest.

Invariant: the receipt records a proposal and final disposition separately; it
cannot itself authorize a mutation.

## `TrainingRunManifestV1`

Fields: code/base-model/dataset revisions, environment lock, objective and
hyperparameters, seeds, split digests, device/hardware, checkpoints, metrics,
calibration, export inventory and parent run.

Invariant: credentials and host secrets are forbidden; referenced artifacts are
checksum-bound and reloadable.

## `EvaluationCaseResultV1`

Fields: protocol/case/cluster/arm identities, exact artifact identities, inputs
and option digest, candidate-pool digest, stage outcomes, primary/secondary
metrics, safety events, latency, usage, cost and error category.

Invariant: comparable arms share case, authorized-input, option and candidate-
pool digests; missing/error cases cannot be counted as success.

## State transitions

Dataset: `generated -> validated -> audited -> private_staged -> verified -> public`
Model: `initialized -> smoke_passed -> trained -> calibrated -> sealed_evaluated -> exported -> private_staged -> verified -> public`
Runtime profile: `absent -> installed -> ready -> previewed -> active -> rolled_back`
Release: `planned -> candidate_committed -> tagged -> workflow_verified -> package_published`; website PR and live deployment are separate parallel states.

The initial dataset `audited` transition covers only non-sealed splits. The
sealed split transitions from `frozen -> firewalled_audited -> evaluated`; its
reviewer cannot influence generators, oracles, training or thresholds. A failed
sealed audit invalidates the dataset/model version rather than returning it to an
editable earlier state.
