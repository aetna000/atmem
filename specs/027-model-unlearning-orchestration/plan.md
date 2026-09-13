# Implementation Plan: Model Influence Revocation and Unlearning Orchestration

**Feature**: `027-model-unlearning-orchestration`

**Date**: 2026-09-12

**Spec**: [spec.md](spec.md)

## Summary

Build a research-preview control plane that handles one forget request across four explicitly different assurances: external memory revocation, inference-time behavioral suppression, provider acknowledgment and evaluated open-weight model unlearning. Reuse Specs 015/023 for immediate revocation and impact, then add evidence-backed model/data lineage, immutable forget manifests, a separately privileged worker protocol, reproducible evaluation, independent approval and exact-digest deployment binding. AtMem orchestrates and verifies declared boundaries; it does not become a training framework or claim proven weight erasure.

## Technical context

**Language/version**: Python 3.10–3.13 for AtMem contracts/services/workers; existing HTML/CSS/JavaScript dashboard; optional training framework isolated behind worker plugins/services.

**Primary dependencies**: Base install uses existing AtMem services and standard library. Research profiles may use explicitly pinned PyTorch/Transformers/PEFT/evaluation dependencies in a separate environment or worker image; none become mandatory AtMem/AtBot dependencies.

**Storage**: Canonical SQLite for requests, manifests, model/data lineage, jobs, reports, approvals and deployment bindings; external artifact storage by protected digest-bound reference. Spec 010 governs production backend equivalents.

**Testing**: pytest contract/security/recovery tests, fake workers/adapters, tiny reproducible open-weight integration, fixed synthetic forget/retain/adversarial suites and installed serving-profile checks.

**Target platform**: Local/customer-hosted control plane first; registered isolated workers and serving adapters. Closed providers participate only through declared provider APIs and evidence.

**Performance goals**: Control-plane operations remain bounded and paginated; publish job/evaluation wall time, compute, cost and artifact size per profile rather than promising trainer-independent latency. Immediate revocation retains Spec 023 propagation targets.

**Constraints**: No implicit enrollment, training or model switch; exact lineage required for weight claims; independent approval; target-data minimization; no raw target in routine evidence; explicit egress; unsupported and unknown are first-class results.

**Scale/scope**: 2.10.0b1 targets one end-to-end single-consumer-GPU profile using Apache-2.0 `Qwen/Qwen2.5-0.5B-Instruct` at revision `c89bee90d9f811437d9735454613c35b4a3c4dc8` and fake coverage for failure modes. Replacement requires a reviewed spec/plan update rather than an execution-time substitution. General large-model, distributed-training and closed-provider weight claims remain outside the preview.

## Constitution check

| Principle | Design response |
| --- | --- |
| I. Authority Before Intelligence | AtMem authorizes target/manifests; AtBot proposes only; privileged workers train but cannot approve/deploy. |
| II. Provenance and Exact Evidence | Every request, dataset, model, method, report, approval and deployment is digest/generation bound with explicit coverage gaps. |
| III. Safe Defaults and Reversibility | Inspection and immediate revocation precede optional jobs; enrollment/dispatch/deployment are separate explicit operations; rollback is preserved. |
| IV. Scope, Privacy and Verifiable Deletion | Target access is least-privilege, derived material is registered, cleanup is verified where controlled and external uncertainty remains visible. |
| V. Contract-First Host Neutrality | Worker and serving capability contracts are framework/provider neutral; adapters implement declared profiles. |
| VI. Executable Claims | Assurance labels are mechanically limited by observed evidence; real-profile and adversarial gates constrain publication. |
| VII. Local-First and Replaceable Intelligence | Revocation/status remain useful without AtBot or training; optional SDKs stay in isolated workers. |

No constitutional exception is required. Re-check after detailed threat modeling, especially target-content staging, semantic scope expansion, worker authentication, artifact substitution and self-approval.

## Research baseline and claim policy

The preview must treat model unlearning as an empirical, profile-specific operation. Existing research shows that ordinary forget metrics can disagree with the stronger goal of behaving like a model never trained on the target, and adversarial or relearning attacks may recover apparently forgotten information. Therefore:

- use multiple disjoint evaluation dimensions rather than one aggregate;
- compare to the original base model and a retrained-without-target reference when feasible;
- preserve per-case outputs and missing denominators;
- preregister thresholds before candidate evaluation;
- label a passing artifact `weight_unlearning_evaluated`, never `weight_erasure_proven`;
- keep runtime containment active according to policy even after a candidate passes.

Protocol post-training is a separate, safer output: train models on synthetic examples to consult governed memory, respect lifecycle/revocation and abstain under conflicts. It must not export real personal facts by default.

## Architecture and ownership

### 1. Assurance and request service

Add a host-neutral domain package:

```text
atmem/unlearning/
├── models.py          # assurance, request, manifest, job, report, approval contracts
├── service.py         # request lifecycle and orchestration
├── manifest.py        # authorized exact target/retain/evaluation material planning
├── lineage.py         # model/data/artifact relationship validation
├── suppression.py     # behavioral control policies and coverage
├── workers.py         # registration, dispatch and reconciliation boundary
├── evaluation.py      # profile runner/aggregation and claim calculation
├── approval.py        # independent review and exact-artifact decision
├── deployment.py      # serving identity checks, activation and rollback binding
└── projection.py      # scoped status, receipts and investigation views
```

The request service records requested assurance separately from achieved assurance. Acceptance immediately invokes existing Spec 015/023 revocation where applicable; model operations are subsequent independent branches. A failed or unsupported model path cannot roll back completed controlled memory revocation.

### 2. Model and training-data lineage

Extend Spec 024 inventory contracts rather than create a competing fleet registry. The feature-owned lineage service records evidence-backed relationships required for an unlearning decision:

```text
source/dataset item → dataset version → training/fine-tuning job
                    → base/adapter/checkpoint artifact → serving conversion
                    → deployed endpoint/profile
```

Each node/reference carries tenant/scope, immutable digest where possible, producer evidence, relevant configuration and coverage state. Unknown relationships remain unknown. Similarity, shared words or an observed context exposure cannot establish training inclusion.

### 3. Forget manifest

`manifest.py` builds a preview from exact authorized lineage. It separates:

- exact forget examples authorized for processing;
- human-reviewed semantic expansions;
- retain examples and neighboring facts protected from collateral damage;
- evaluation-only prompts that must never enter training;
- target-content staging, retention and cleanup policy.

AtBot may propose paraphrases/semantic neighbors using a minimized authorized package through a new versioned capability. AtMem validates IDs/scope and requires review. The final manifest is immutable, digest-bound and content-addressed; changes create a new generation.

### 4. Privileged worker boundary

Workers register supported methods, artifact formats, maximum job size, isolation, authentication, cancellation/reconciliation, evidence and cleanup capabilities. Dispatch requires a dedicated model-training capability unavailable to ordinary agents and AtBot. The initial real profile runs in a separately pinned local/container environment against a tiny model/dataset; fake workers exercise faults deterministically.

AtMem supplies a signed/authorized manifest reference or bounded material according to deployment policy, never an unrestricted database credential. Workers emit progress events and artifact manifests. Returned checkpoints remain untrusted until digest/lineage validation and evaluation complete.

### 5. Evaluation and claim computation

Create versioned evaluation profiles under `atmem/unlearning/profiles/` and fixtures under `tests/fixtures/product/027/`. Keep training inputs disjoint from evaluation cases. Dimensions include:

- exact and paraphrased forget behavior;
- multilingual variants where declared;
- retain-set and neighboring-knowledge utility;
- general capability regression;
- extraction/jailbreak recovery;
- relearning resistance;
- privacy/memorization signals supported by the profile.

AtBot may generate bounded candidate attacks, but fixed deterministic cases remain mandatory and the evaluation service—not AtBot—calculates results. Thresholds and severe-case vetoes are registered before a candidate run. Missing suites remain in the denominator/coverage report and cannot increase assurance.

### 6. Independent approval and deployment

Approval requires a distinct authorized reviewer when configured and binds exact base/candidate artifact digests, manifest generation, worker/method, evaluation profile/data/configuration/results and expiry. Deployment adapters use the host's existing model-selection mechanism and declare whether they can verify the served artifact. Activation fails on digest/profile mismatch, stale approval or unsupported identity.

Rollback is a separately authorized idempotent operation to a recorded artifact. It reports that the restored model may retain the original forget risk and does not undo candidate outputs.

### 7. Behavioral suppression and monitoring

`suppression.py` consumes Spec 019/023 policy and dispatch generations to apply scoped, expiring controls only at declared boundaries. It may withhold, refuse, redirect to governed current memory or require review. It is defense in depth, not a weights claim.

Post-deployment monitoring runs explicitly configured synthetic probes and verifies served identity when supported. Production observations are content-minimized and are not silently repurposed into evaluation/training data. Leakage or identity mismatch creates a Spec 021 finding with permitted containment/rollback actions; it does not silently switch models.

### 8. Protocol-training export

Add `atmem/unlearning/protocol_data.py` to produce lifecycle/revocation behavior examples from checked-in synthetic fixtures. Real correction history is a separate privileged export requiring consent, purpose, scope, retention and deletion propagation. Export validation rejects forgotten/inaccessible content and registers every derived artifact.

## Contract and data changes

Planned contracts:

- `atmem-unlearning-request-v1`
- `atmem-unlearning-assurance-v1`
- `atmem-forget-manifest-v1`
- `atmem-model-data-lineage-v1`
- `atmem-unlearning-worker-capability-v1`
- `atmem-unlearning-job-v1`
- `atmem-unlearning-evaluation-profile-v1`
- `atmem-unlearning-evaluation-report-v1`
- `atmem-model-approval-v1`
- `atmem-model-deployment-binding-v1`
- `atmem-behavioral-suppression-policy-v1`
- `atmem-unlearning-receipt-v1`
- `atbot-unlearning-expansion-request-v1` / `result-v1`

Persistence uses allocated Spec 010 migrations for request/generation, content-minimized manifest metadata, lineage references, worker/job state, reports, approvals, deployment bindings and suppression policies. Large datasets/checkpoints remain in deployment-controlled artifact storage; AtMem stores protected references, digests and verification evidence.

Existing memory, provider, signed delegation, model selection and release formats remain compatible. Upgrade registers no inferred lineage, assurance, enrollment, suppression or job.

## Security and privacy design

- Separate request, target-review, worker-dispatch, evaluation-review and deployment capabilities.
- Prevent requester/worker self-approval under separation policy.
- Authenticate workers and serving adapters; bind messages to nonce/idempotency, generation and digest.
- Authorize lineage graph nodes, joins, counts and exports to prevent existence leakage.
- Treat target text, paraphrases, gradients, adapters and checkpoints as potentially sensitive derived data.
- Apply explicit staging encryption/access/retention and verified local cleanup; report external/unmanaged copies.
- Reject indirect prompt instructions in training examples and semantic-expansion inputs.
- Enforce network/endpoint policy before provider, AtBot, worker or evaluation egress.
- Keep raw prompts/results out of default Black Box evidence; store bounded outcomes and digests.

## Verification and research protocol

1. Contract and guarantee-state tests prevent overclaiming combinations.
2. Authorization and red-team fixtures cover target expansion, cross-tenant lineage, self-approval and artifact substitution.
3. Fake worker tests cover dispatch, duplicate request, timeout, cancellation, late success and restart reconciliation.
4. Immediate revocation tests reuse Spec 023 race/propagation gates with all model components absent.
5. Evaluation harness tests preserve per-case results, missing coverage and preregistered thresholds.
6. Tiny open-weight profile runs base → unlearning worker → candidate → evaluation → approval → isolated deployment.
7. Retain damage, superficial refusal, paraphrase/multilingual extraction, jailbreak and relearning cases remain separately visible.
8. Protocol-training export tests prove synthetic-only default and deletion propagation.
9. Installed serving-profile tests verify exact artifact identity or label it unsupported.
10. Upgrade, rollback, content cleanup, dependency isolation and base-install tests remain mandatory.

Research reports live under `docs/implementation-evidence/027/` with exact code, model, dataset, configuration, environment/hardware, duration/cost and limitations. No passing local toy profile establishes general large-model effectiveness.

## Project structure

```text
atmem/unlearning/                         # orchestration, evaluation and assurance
atmem/unlearning/profiles/                # preregistered versioned profiles
atmem/context/                            # Spec 019/023 suppression and revocation integration
atmem/service/application.py              # common authenticated operations
atmem/control/assets/                     # status, review and deployment UI projections
packages/atbot/src/atbot/unlearning.py     # bounded semantic expansion/attack proposals
tests/test_unlearning.py                  # contracts, authority, failure and recovery
tests/fixtures/product/027/                # synthetic forget/retain/adversarial fixtures
tools/unlearning_worker/                   # isolated reference worker/profile tooling
docs/implementation-evidence/027/          # append-only research results
```

**Structure decision**: Keep unlearning orchestration inside the host-neutral AtMem service while isolating heavyweight and privileged training dependencies in registered workers. Reuse lifecycle/context/execution/fleet authorities rather than duplicating them.

## Delivery sequence

### Pre-2.10 prerequisites

- 2.7/Spec 023: external revocation, exposure impact, propagation and honest cleanup states.
- 2.9/Spec 024: model/deployment inventory and fleet identity sufficient to bind a candidate to a served profile.
- Specs 012/013: durable authenticated administration and separation of duties.
- Specs 020/021: execution evidence, findings and permitted remediation actions.

### 2.10.0b1 research preview

1. Assurance/request/status contracts and immediate revocation integration.
2. Read-only model/data lineage inspection and synthetic manifest preview.
3. Fake worker and evaluation flows with security/failure gates.
4. The pinned `Qwen/Qwen2.5-0.5B-Instruct` single-consumer-GPU method/profile.
5. Independent approval and one isolated serving adapter with digest verification.
6. Synthetic post-deployment monitoring and protocol-training export.

Closed-source profiles remain limited to provider-request/acknowledgment and behavioral controls actually verified. General large-model effectiveness, formal erasure and managed training service are deferred.

## Rollback

Disabling the feature prevents new manifests/jobs/evaluations/activations but preserves authorized evidence and immediate memory revocation. A running external job is cancelled only where the worker supports verified cancellation; otherwise state is unknown until reconciled. Model rollback restores an explicitly approved prior artifact and reports its known forget limitations. Rollback never resurrects revoked external memory automatically.
