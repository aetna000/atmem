# Feature Specification: Model Influence Revocation and Unlearning Orchestration

**Feature directory**: `specs/027-model-unlearning-orchestration`
**Created**: 2026-09-12
**Status**: Research preview specified; implementation and verification pending
**Input**: Use AtMem above the model and alongside post-training infrastructure to coordinate forget requests, immediate runtime containment, open-weight unlearning jobs and honest evaluation without equating RAG deletion with removal from model weights.

## Overview

AtMem becomes the governed control and evidence plane for information-removal requests that may span external memory, delivered context, providers and registered model artifacts. It first performs the strongest immediate controlled action available—revoking eligible external memory and future governed delivery—then reports past exposure and remaining uncertainty. Where exact model/training lineage and an authorized open-weight training environment exist, AtMem can prepare a bounded forget manifest, dispatch it to a separately privileged unlearning worker, evaluate the resulting checkpoint and bind approval/deployment to the exact tested artifact.

The product distinguishes memory revocation, behavioral suppression, provider-reported deletion and evaluated weight unlearning. Passing a benchmark or observing refusal does not prove that information was erased from weights. Closed-source or lineage-unknown models remain eligible only for the controls their provider and deployment actually support.

AtBot may assist with bounded semantic target expansion and adversarial evaluation generation, but it cannot authorize a forget scope, access unrestricted training data, run training, decide that a model passed, approve deployment or change canonical memory. The unlearning worker is a separate registered execution boundary.

This research preview follows the 2.7 context-revocation and 2.9 fleet/model-inventory foundations and is proposed for 2.10.0b1. It does not block releases 2.3–2.9.

## Assurance vocabulary

Every request and result uses one or more explicit assurance states:

| State | Meaning |
| --- | --- |
| `memory_revoked` | Controlled external memory is no longer eligible for future governed use at the reported boundary. |
| `behaviorally_suppressed` | Named supported runtime paths apply a scoped response/control policy; bypass or unmanaged paths may remain. |
| `provider_deletion_acknowledged` | A provider reports processing a request; this is not independent proof of weight or backup erasure. |
| `weight_unlearning_evaluated` | An exact candidate checkpoint passed a named, versioned evaluation profile against a registered baseline. |
| `weight_erasure_proven` | Reserved and not claimable by this research preview. |

## User scenarios and acceptance

### US1 — Revoke and contain information immediately (P1)

As an authorized privacy or model operator, I can request forgetting and see which controlled boundaries stopped using the information before any optional training job completes.

**Independent test**: Submit a request targeting synthetic data that exists in canonical memory and prior context evidence, then verify future delivery blocking, impact reporting and explicit unmanaged/model uncertainty without any training worker.

1. Given an authorized forget request, when it is accepted, then existing Spec 015/023 controls revoke eligible external memory and future governed delivery independently of model-training availability.
2. Given prior observed exposures, when impact is inspected, then AtMem lists authorized known packages/executions and unknown coverage without claiming that exposure caused weight memorization or output.
3. Given behavioral suppression is configured for a supported runtime, when a related query reaches the controlled boundary, then the policy is applied and recorded; direct/unmanaged access remains explicitly outside assurance.
4. Given a closed-source model with only a provider deletion API, when a request is sent, then requested, acknowledged, provider-verified and unknown states remain distinct and AtMem never reports weight unlearning.

### US2 — Prepare and execute an open-weight unlearning job (P1)

As an authorized model operator, I can turn a sufficiently traceable forget request into a reproducible, bounded job for a registered open-weight model.

**Independent test**: Use a tiny synthetic model/checkpoint and training corpus with exact lineage to build a manifest, execute a fake and one declared real worker profile, and reconcile output artifacts by digest.

1. Given exact model, dataset and target-example lineage, when a manifest is prepared, then it identifies the authorized forget set, retain constraints, neighboring knowledge, evaluation-only variants, method/profile and content-handling policy without silently expanding scope.
2. Given missing or ambiguous training lineage, when weight unlearning is requested, then AtMem marks it unsupported or awaiting review while preserving immediate revocation/suppression controls.
3. Given a privileged registered worker, when a job is dispatched, then the worker receives only the approved manifest/material, reports progress and returns immutable artifact/evidence references; AtBot and ordinary agents cannot invoke it.
4. Given cancellation, timeout, retry or worker restart, when the operation reconciles, then no duplicate checkpoint is approved and unknown training state remains explicit.

### US3 — Evaluate, approve and deploy a candidate honestly (P1)

As a model reviewer, I can compare forgetting effectiveness, retained utility and adversarial recoverability before an exact candidate artifact becomes deployable.

**Independent test**: Evaluate baseline, candidate and retrained-without-target reference where feasible using fixed forget/retain/neighbor/general/adversarial suites, then attempt to deploy a different digest and a failing candidate.

1. Given a candidate model, when evaluation runs, then results separately report forget behavior, retain utility, neighboring knowledge, general capabilities, privacy/extraction attacks, multilingual/paraphrase robustness and relearning resistance supported by the profile.
2. Given unavailable metrics, attacks or retraining reference, when the report is produced, then denominators and missing coverage are explicit and are not counted as passes.
3. Given a candidate satisfies a pre-registered profile, when an independent authorized reviewer approves it, then approval binds the base/candidate digests, manifest, method, evaluation data/configuration and expiry.
4. Given deployment requests a different or modified artifact, stale approval or unsupported serving path, when activation is attempted, then it fails closed.
5. Given a candidate passes, when shown to a user, then the assurance is `weight_unlearning_evaluated` with the exact profile—not proof of erasure or equivalence to never-trained behavior.

### US4 — Train models to obey governed memory without embedding personal facts (P2)

As a model developer, I can produce privacy-safe post-training examples that teach the AtMem interaction protocol instead of copying users’ mutable memories into weights.

**Independent test**: Generate a synthetic protocol dataset for current, expired, superseded, conflicting, derived and forgotten states and verify that no canonical user content or inaccessible metadata appears.

1. Given synthetic lifecycle fixtures, when protocol-training examples are exported, then they teach consultation, abstention, temporal reasoning, correction precedence and revocation handling without exporting real user memories by default.
2. Given a request to use real correction history, when consent, purpose, scope or retention authority is absent, then export is denied.
3. Given a forgotten record, when any later protocol dataset is generated, then its content, paraphrases and derived representations are absent.

### US5 — Monitor post-deployment leakage and rollback (P2)

As an operator, I can monitor declared evaluation probes against the deployed digest, detect regression or model mismatch and take a governed rollback or containment action.

**Independent test**: Deploy an approved synthetic candidate, substitute a mismatched digest, simulate a leakage regression and verify alerting, suppression escalation and rollback without generating unrestricted user traffic.

1. Given an approved deployment, when monitoring runs, then it verifies the served model identity where the adapter supports it and keeps synthetic probes separate from production observations.
2. Given leakage regression or unverifiable model identity, when policy requires containment, then AtMem can disable the affected governed route or strengthen behavioral suppression and recommends an authorized rollback; it cannot silently replace the model.
3. Given new evidence or an expanded forget target, when reevaluation is required, then prior approval remains historical and cannot authorize the changed scope or artifact.

## Edge cases

- One fact may appear in many examples, languages, modalities or derived datasets; semantic expansion is a reviewable proposal and never proof of complete lineage.
- Shared or public knowledge entangled with a personal target requires retain/neighbor evaluation and may make requested weight-level scope infeasible.
- Hash equality identifies bytes, not semantic equivalence; semantic similarity cannot silently add examples to a forget manifest.
- A provider may acknowledge deletion without exposing checkpoint identity or method; report the acknowledgment and missing assurance separately.
- The target content may be required temporarily by the authorized worker to perform unlearning, creating a controlled processing-versus-erasure tension; staging, access, retention and cleanup must be explicit and verified.
- Evaluation prompts can themselves disclose target information to model/provider endpoints; egress, isolation and retention policy apply before evaluation.
- Apparent refusal may be a superficial safety behavior while underlying information remains recoverable; adversarial tests and claim limits remain visible.
- Excessive forgetting can damage related or general capabilities; no single forget metric can approve a candidate.
- Relearning, fine-tuning, model merging, quantization or serving conversion creates a new artifact requiring lineage and reevaluation.
- A rollback restores a prior artifact and its known risk; it does not reverse disclosures made by the candidate.

## Functional requirements

- **FR-001**: Define versioned guarantee/assurance semantics for external memory revocation, behavioral suppression, provider acknowledgments, evaluated weight unlearning and the unclaimable `weight_erasure_proven` state across every interface.
- **FR-002**: Accept an authenticated, authorized and purpose-bound unlearning request with exact subject/tenant/model/provider scope, target selector, requested assurance, reason, legal/policy basis, idempotency identity and retention constraints.
- **FR-003**: Execute or reconcile immediate Spec 015/023 memory revocation, controlled derivative invalidation and exposure-impact reporting independently of optional model operations; distinguish future enforcement, prior exposure and unmanaged copies.
- **FR-004**: Behavioral suppression MUST be a scoped, versioned, expiring policy enforced only at declared adapters/boundaries, resistant to stale caches and reported as behavioral control rather than weight modification.
- **FR-005**: Maintain a registered model/data lineage graph containing exact artifact digests, base/parent relationships, training/fine-tuning dataset versions, method/configuration identity, deployment references and coverage/unknowns. Lineage claims require evidence and authorization.
- **FR-006**: Build a content-minimized, immutable forget manifest only when target authorization and required lineage are sufficient. Separate exact forget examples, reviewed semantic expansions, retain/neighbor constraints and evaluation-only prompts.
- **FR-007**: Semantic target expansion MAY be proposed by AtBot from an already authorized bounded package, but AtMem MUST validate and require review before expanding training or evaluation scope. Similarity alone cannot authorize inclusion.
- **FR-008**: Dispatch training only to a separately registered privileged worker through a versioned capability contract. Ordinary agents, AtBot, dashboard arguments and untrusted providers cannot acquire training or deployment authority.
- **FR-009**: Bind every job to base model, manifest, method, code/environment, random-seed policy, hardware/dependency evidence where applicable, output location, content-handling policy and expected generations. Make dispatch/retry/cancel/reconcile idempotent and explicit about unknown remote state.
- **FR-010**: Register returned checkpoints and derived artifacts by digest and immutable lineage before evaluation. A worker-reported success is not an AtMem evaluation or deployment approval.
- **FR-011**: Define pre-registered evaluation profiles with disjoint forget, retain, neighboring, general-utility and adversarial suites; include paraphrase/multilingual, extraction/jailbreak and relearning checks when supported, and record unavailable coverage and denominators.
- **FR-012**: Compare candidate results with the base model and, where feasible, a retrained-without-target reference. Preserve per-case results and declared statistical/threshold policy; no aggregate alone may hide severe retain damage or target leakage.
- **FR-013**: Require independent authenticated review for candidate approval. Bind approval to exact artifact, manifest, evaluation profile/data/configuration, results, expiry and governing generations; prohibit requester/worker self-approval where policy requires separation.
- **FR-014**: Deployment activation MUST verify the approved artifact digest and supported serving identity, be explicit/idempotent/recoverable, preserve prior model/evidence and fail closed on mismatch or stale approval. It never silently changes an agent's model.
- **FR-015**: Support post-deployment synthetic monitoring, leakage-regression findings and governed containment/rollback recommendations without storing unrestricted production prompts or manufacturing traffic unless explicitly configured.
- **FR-016**: Export protocol-training data from synthetic fixtures by default. Real memory/correction history requires explicit consent, purpose, scope, minimization, retention and deletion propagation; forgotten or inaccessible content is forbidden.
- **FR-017**: Expose a shared status/receipt showing requested versus achieved assurance, known effect, uncertainty, exact models/providers/boundaries, times/check age, evidence and permitted next action. Counts, joins, exports and evaluation data remain scope-authorized.
- **FR-018**: Keep core revocation and reporting local/useful without AtBot, training frameworks or hosted providers. Optional workers and model/provider SDKs remain extras or separately deployed services with enterprise-safe pinned profiles.
- **FR-019**: Add synthetic research benchmarks and declared real open-weight profiles. Tests cover authorization, poisoning, scope expansion, lineage gaps, artifact mismatch, worker failure, retain damage, superficial refusal, adversarial recovery, relearning and rollback.
- **FR-020**: Contract/schema/persistence changes MUST be versioned, migratable and recoverable from supported release floors. Upgrade cannot create training lineage, enable suppression, dispatch a job or reinterpret a past provider acknowledgment.

## Key entities

- **UnlearningRequest**: Authorized requested target, assurance, scope, basis, retention policy and lifecycle.
- **ForgetManifest**: Immutable approved mapping from exact target lineage to forget material, reviewed expansions, retain constraints and evaluation-only cases.
- **ModelArtifact**: Digest-bound base/candidate/derived checkpoint with parentage, format, creation evidence and deployment references.
- **TrainingLineage**: Evidence-backed relationship among source data, dataset versions, training jobs and model artifacts, with explicit gaps.
- **UnlearningWorkerRegistration**: Privileged capability, authentication, isolation, supported methods/artifacts and evidence contract.
- **UnlearningJob**: Idempotent dispatched operation and progress/reconciliation state bound to a manifest and base model.
- **EvaluationProfile/Report**: Pre-registered suites, thresholds, coverage, per-case results and comparisons for one exact candidate.
- **ModelApproval/DeploymentBinding**: Independent decision and activation state tied to the evaluated digest and serving boundary.
- **SuppressionPolicy**: Scoped inference-time containment rule with enforcement coverage, generation and expiry.
- **UnlearningReceipt**: User-facing requested-versus-achieved assurance and evidence, limitations, timestamps and next action.

## Success criteria

- **SC-001**: Every tested request reports the exact achieved assurance state; zero external-memory-only, prompt-only or provider-acknowledged cases are labelled weight unlearning or proven erasure.
- **SC-002**: Authorization, poisoning, cross-tenant, ambiguous-lineage and semantic-expansion fixtures produce zero unauthorized manifest material, evaluation egress, worker dispatch, model approval or deployment.
- **SC-003**: Immediate controlled revocation blocks future supported delivery within the Spec 023 measured bound even when every model/training component is absent or failing; prior exposure and unmanaged paths remain explicit.
- **SC-004**: Retry, timeout, cancellation and restart fixtures reconcile to one job/artifact lineage per idempotency identity with no unreviewed checkpoint activation and explicit unknown remote state.
- **SC-005**: A deployment can activate only the exact independently approved candidate digest and serving profile; mismatch, quantization/conversion without lineage, stale approval and failed evaluation are rejected in all supported interfaces.
- **SC-006**: Research reports preserve all forget/retain/neighbor/general/adversarial per-case results and missing denominators for base, candidate and available retraining reference; no unavailable attack or profile is counted as passing.
- **SC-007**: Protocol-training export fixtures contain zero real canonical memory by default and zero forgotten, inaccessible or non-consented content under all tested configurations.
- **SC-008**: Published 2.10 preview evidence names exact model, dataset, code, worker, evaluation and hardware identities plus cost/duration and limitations. The initial intended profile uses Apache-2.0 `Qwen/Qwen2.5-0.5B-Instruct` at revision `c89bee90d9f811437d9735454613c35b4a3c4dc8` on a single consumer GPU; replacing that planning target requires a reviewed spec/plan change. At least one reproducible open-weight profile completes end to end, while broader model/provider claims remain unsupported.
- **SC-009**: Post-deployment mismatch/leakage fixtures produce a scoped finding and safe permitted action without silent model replacement, invented provider cleanup or unapproved production probing.

## Dependencies and ownership

Spec 015 owns canonical memory forgetting and invalidation; Spec 019 owns context policy/package authorization; Spec 020 owns observed execution/model boundary evidence; Spec 021 owns investigation findings and remediation semantics; Spec 023 owns context revocation, exposure impact and cleanup acknowledgments; Spec 024 owns fleet/model/deployment inventory distribution; Spec 025 owns provider connection/authentication journeys; Spec 001 owns benchmark reporting. This feature owns assurance vocabulary, forget manifests, model/data lineage required for unlearning, privileged job orchestration, evaluation/approval and deployment binding.

AtBot owns only replaceable semantic expansion and evaluation-case proposals over bounded authorized inputs. Registered workers own method execution but cannot approve their outputs. Deployment adapters retain their host's model-selection mechanics and must declare identity/enforcement capability.

## Compatibility, privacy and rollout

Begin with non-mutating inspection and synthetic manifests, then fake workers, then a tiny isolated open-weight profile. External revocation remains independently usable. Target content staging uses least privilege, encryption appropriate to the deployment, bounded retention and verified cleanup; hashes are identifiers, not anonymization. Existing models, agents and providers are never enrolled implicitly. Closed-source providers expose only their actually verified request/acknowledgment and serving-control capabilities.

## Out of scope

- Claiming mathematical proof of weight erasure or universal equivalence to a never-trained model.
- Providing a general training platform or bundling every research unlearning algorithm.
- Weight modification for closed-source models without a provider-supported verified capability.
- Automatically expanding a forget request to related people, facts, languages or datasets.
- Using customer memories for post-training without explicit consent and purpose.
- Treating refusal, low benchmark probability, RAG deletion or a provider acknowledgment as sufficient proof of unlearning.
- Delaying immediate external-memory revocation until an optional training job finishes.

## Constitution check

I: AtMem authorizes scope and effects; AtBot/worker cannot commit or deploy. II: manifests, lineage, artifacts and reports bind exact evidence. III: inspection-first rollout, independent review and rollback preserve safe operation. IV: scope/minimization/deletion govern target handling and derived artifacts. V: contracts are host/provider/trainer-neutral and versioned. VI: claims are limited to named boundary evidence and adversarial coverage. VII: immediate revocation/reporting work locally; optional model and training egress is explicit.

## Invariant attestation

Touches INV-001, INV-002, INV-003, INV-004, INV-005, INV-006, INV-007, INV-008, INV-009, INV-010 and INV-011 through planned assertions `spec027.assurance_authority`, `spec027.expansion_authorization`, `spec027.suppression_revalidation`, `spec027.explicit_activation`, `spec027.digest_binding`, `spec027.lineage_history`, `spec027.derived_cleanup`, `spec027.unlearning_claims`, `spec027.deployment_rollback`, `spec027.local_revocation` and `spec027.upgrade_compatibility`. These assertions extend existing invariant meanings and become proven only through executed boundary/profile evidence; the research preview reserves rather than proves weight erasure.
