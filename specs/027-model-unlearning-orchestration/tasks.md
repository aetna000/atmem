# Tasks: Model Influence Revocation and Unlearning Orchestration

**Evidence policy**: Append verification to a new entry under `docs/implementation-evidence/027/` following `docs/implementation-evidence/README.md`. `docs/current-status.md` is a linked summary, not a raw test log; dated reviews remain frozen. Task-ID suffixes are significant (see `specs/task-conventions.md`).

**Status**: Research preview planned, unchecked.

**Input**: [spec.md](spec.md), [plan.md](plan.md), [product requirements](../product-requirements.md).

**Prerequisites**: Specs 012/013 authenticated administration; 015/023 revocation, impact and propagation; 020/021 execution findings/actions; 024 model/deployment inventory. The 2.10 preview does not block releases 2.3–2.9.

## Phase 1: Assurance contracts, threat model and fixtures

- [ ] [T001] Freeze assurance, request, receipt and stable reason-code contracts in `atmem/unlearning/models.py`; mechanically prohibit `weight_erasure_proven` and prevent memory revocation, prompt refusal or provider acknowledgment from satisfying evaluated-weight assurance (FR-001–FR-004, FR-017–FR-020; SC-001).
- [ ] [T002] Document the target-data, semantic-expansion, worker, artifact-substitution, evaluation-egress, self-approval, deployment and rollback threat model in `specs/027-model-unlearning-orchestration/security.md`, mapping each threat to an enforcing boundary and test (FR-002, FR-005–FR-020; SC-001–SC-008; depends on T001).
- [ ] [T003] Freeze model/data lineage, forget manifest, worker/job, evaluation, approval, deployment and suppression contracts in `atmem/unlearning/models.py`, negotiated public schemas and fake adapter interfaces; preserve exact digests, generations, missing coverage and separation of authority (FR-005–FR-015, FR-020; depends on T002).
- [ ] [T004] Define disjoint synthetic target/retain/neighbor/general/adversarial/relearning fixtures and expected non-claims under `tests/fixtures/product/027/`, plus tiny-profile manifests that can be redistributed under declared licenses (FR-011–FR-012, FR-016, FR-019; SC-001–SC-008; depends on T003).

## Phase 2: Request lifecycle and immediate containment

- [ ] [T005] Allocate SQLite migrations through Spec 010 for requests, assurance observations, content-minimized manifests/lineage, worker jobs, reports, approvals, deployment bindings and suppression policies; add real persisted upgrade and rollback/forward-recovery fixtures proving upgrade invents no lineage or activation (FR-002, FR-005–FR-006, FR-009–FR-010, FR-013–FR-015, FR-020; depends on T004).
- [ ] [T006] Implement authenticated, purpose-bound, idempotent request lifecycle and scoped projections in `atmem/unlearning/service.py` and `atmem/unlearning/projection.py`; authorize records, joins, counts and exports independently (FR-001–FR-003, FR-017–FR-018; SC-001–SC-002; depends on T005 and Specs 012/013 authority).
- [ ] [T007] Integrate request acceptance with Spec 015/023 external-memory revocation, controlled derivative invalidation and exposure-impact reporting; preserve prior exposure, unmanaged copy and propagation uncertainty when all model components are absent (FR-003; SC-003; depends on T006 and Spec 023 acceptance contracts).
- [ ] [T008] Implement scoped, expiring behavioral-suppression policies in `atmem/unlearning/suppression.py` through Spec 019/023 generation and pre-dispatch checks; record actual adapter coverage and resist stale caches without representing suppression as weight change (FR-004; SC-001, SC-003; depends on T006–T007).
- [ ] [T009] Expose requested-versus-achieved assurance, known effect, uncertainty, evidence, times/check age and permitted next action through common service, CLI, MCP and dashboard projections; closed-provider request/acknowledgment states remain separate (FR-001–FR-004, FR-017–FR-018; SC-001, SC-003; depends on T006–T008).

## Phase 3: Model/data lineage and forget-manifest review

- [ ] [T010] Implement evidence-backed model/data/artifact lineage validation in `atmem/unlearning/lineage.py` as an extension of Spec 024 inventory; unknown, similarity-inferred and exposure-only relationships cannot establish training inclusion (FR-005, FR-017, FR-020; SC-002; depends on T005 and stable Spec 024 inventory contracts).
- [ ] [T011] Implement read-only manifest preview in `atmem/unlearning/manifest.py`, separating exact forget examples, reviewed expansions, retain/neighbor constraints, evaluation-only cases and target-data staging/cleanup policy (FR-006; SC-002; depends on T010).
- [ ] [T012] Add minimized AtBot semantic-expansion request/result handling in `packages/atbot/src/atbot/unlearning.py` and strict AtMem validation in `atmem/unlearning/manifest.py`; require an authorized bounded input set, returned-ID subset and human review before scope expansion (FR-007, FR-018; SC-002; depends on T003, T011).
- [ ] [T013] Implement authenticated manifest approve/edit/reject operations with expected lineage/request generations, separation policy and immutable digest in `atmem/unlearning/manifest.py`; register content-bearing derivatives for retention/deletion and prohibit requester self-approval where configured (FR-006–FR-007, FR-013, FR-017; SC-002; depends on T011–T012).

## Phase 4: Privileged worker and artifact registration

- [ ] [T014] Implement worker registration, authentication, capability negotiation and least-privilege material access in `atmem/unlearning/workers.py`; ordinary agents, AtBot and caller-selected roles must be unable to dispatch training (FR-008–FR-009, FR-018; SC-002; depends on T003, T013 and Spec 013 authenticated administration).
- [ ] [T015] Implement idempotent dispatch, progress, cancellation and restart/late-result reconciliation in `atmem/unlearning/workers.py`, binding base model, manifest, method, environment, seed policy, output and content-handling generations (FR-009; SC-004; depends on T014).
- [ ] [T016] Implement returned artifact digest/format/parent-lineage validation and registration in `atmem/unlearning/lineage.py`; worker success cannot create evaluation assurance, approval or deployment (FR-010; SC-004–SC-005; depends on T015).
- [ ] [T017] Build a dependency-isolated fake/reference worker under `tools/unlearning_worker/` with deterministic success, timeout, cancellation, malformed artifact, late success and cleanup-verification profiles; keep training SDKs out of the base AtMem and AtBot distributions (FR-008–FR-010, FR-018; SC-004; depends on T014–T016).

## Phase 5: Evaluation and independent approval

- [ ] [T018] Implement preregistered evaluation-profile loading, disjoint dataset checks, fixed per-case execution and missing-coverage accounting in `atmem/unlearning/evaluation.py` and `atmem/unlearning/profiles/` (FR-011–FR-012, FR-019; SC-006; depends on T004, T016).
- [ ] [T019] Implement base/candidate/retrained-reference comparison, severe-case vetoes and separate forget/retain/neighbor/general/adversarial/relearning result projections without hiding cases behind one aggregate (FR-011–FR-012; SC-006; depends on T018).
- [ ] [T020] Add optional bounded AtBot attack/paraphrase proposals while retaining mandatory fixed cases; validate egress, target authorization and test-only separation so generated prompts cannot expand the forget manifest or enter training (FR-007, FR-011–FR-012; SC-002, SC-006; depends on T012, T018–T019).
- [ ] [T021] Implement independent, expiring and generation-checked candidate approval in `atmem/unlearning/approval.py`, binding exact base/candidate digests, manifest, worker/method, evaluation profile/data/configuration and results; failing or incomplete required coverage cannot pass (FR-013; SC-001, SC-005–SC-006; depends on T019–T020).

## Phase 6: Deployment, monitoring and protocol post-training

- [ ] [T022] Implement serving capability/identity contracts and explicit activation/rollback binding in `atmem/unlearning/deployment.py`; reject digest mismatch, unregistered conversion/quantization, stale approval and unsupported identity, and never silently replace an agent model (FR-014; SC-005; depends on T021 and stable Spec 024 deployment inventory).
- [ ] [T023] Implement explicitly configured synthetic post-deployment probes and leakage/model-mismatch findings in `atmem/unlearning/evaluation.py` and `atmem/unlearning/projection.py`; integrate permitted containment/rollback recommendations through Spec 021 without automatic model replacement (FR-015, FR-017; SC-005, SC-009; depends on T022 and stable Spec 020/021 contracts).
- [ ] [T024] Implement synthetic lifecycle/revocation protocol-training export in `atmem/unlearning/protocol_data.py`; deny real correction-history export without consent/purpose/scope/retention authority and prove forgotten/inaccessible content and derivatives are absent (FR-016, FR-018–FR-019; SC-002, SC-007; depends on T007, T013).
- [ ] [T025] Add scoped UI/service journeys for request, impact, manifest review, job state, evaluation comparison, approval, deployment identity and rollback in `atmem/control/assets/` and `atmem/service/application.py`; show progressive assurance and limitations instead of a single “unlearned” status (FR-001–FR-017; SC-001–SC-005; depends on T009, T013, T017, T021–T024).

## Phase 7: 2.10.0b1 research profile and release evidence

- [ ] [T026] Package the intended single-consumer-GPU open-weight worker/evaluation profile using Apache-2.0 `Qwen/Qwen2.5-0.5B-Instruct` at revision `c89bee90d9f811437d9735454613c35b4a3c4dc8`, with pinned dataset, code and environment outside the base dependency set; document exact download/egress and hardware requirements, and require reviewed spec/plan change for replacement (FR-018–FR-019; SC-008; depends on T017–T021).
- [ ] [T027] Execute the tiny end-to-end base → manifest → worker → candidate → evaluation → approval → isolated deployment flow, including retain damage, superficial refusal, extraction/jailbreak, multilingual/paraphrase and relearning cases supported by the profile; retain every case and limitation under `docs/implementation-evidence/027/` (FR-011–FR-015, FR-019; SC-004–SC-006, SC-008; depends on T022–T023, T026).
- [ ] [T028] Run authorization, poisoning, cross-tenant, semantic-expansion, target-staging cleanup, worker failure/restart, artifact substitution, serving mismatch, leakage regression, unapproved probing, rollback, upgrade and base-install dependency-isolation gates; record unavailable profiles rather than counting them as passes (FR-002–FR-020; SC-001–SC-009; depends on T024–T027).
- [ ] [T029] Publish a research-preview capability matrix and exact requested-versus-achieved assurance language in `docs/current-status.md` and feature documentation, clearly limiting closed-source models to verified provider/runtime controls and reserving `weight_erasure_proven` (FR-001, FR-017–FR-020; SC-001, SC-006, SC-008; depends on T028).
- [ ] [T030] Register and execute the Spec 027 assertions declared in `spec.md` through `atmem/invariants/` and the installed-package invariant gate; report worker/model/provider/serving configurations as proven, partially proven or unproven without retitling INV-001–INV-011 (FR-001–FR-020; SC-001–SC-009; depends on T029).

## Dependencies and release boundary

`T001 → T002 → T003 → T004 → T005`; `T005 → T006 → T007 → T008 → T009`; `T005 → T010 → T011 → T012 → T013`; `T003,T013 → T014 → T015 → T016 → T017`; `T004,T016 → T018 → T019`; `T012,T018,T019 → T020 → T021`; `T021 → T022 → T023`; `T007,T013 → T024`; `T009,T013,T017,T021–T024 → T025`; `T017–T021 → T026`; `T022,T023,T026 → T027`; `T024–T027 → T028 → T029 → T030`.

The **2.10.0b1** research-preview boundary requires T001–T030 plus its named prerequisite evidence from Specs 012/013/015/020/021/023/024. A small-profile pass does not establish large-model efficacy, closed-provider weight unlearning, equivalence to retraining or proven erasure. No task authorizes external egress, real-user training-data use, model deployment or release publication without the explicit operations and release process they require.
