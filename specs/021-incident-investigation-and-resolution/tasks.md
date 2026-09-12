# Tasks: Incident Investigation and Resolution

**Evidence policy**: Append verification to a new entry under `docs/implementation-evidence/021/` following `docs/implementation-evidence/README.md`. `docs/current-status.md` is a linked summary, not a raw test log; dated reviews are frozen. Task-ID suffixes are significant (see `specs/task-conventions.md`).

**Status**: Earlier M0 findings tasks T018–T020 are complete; standalone
reconstruction/diagnosis T025–T028 and the broader resolution scope remain open.
**Input**: [spec.md](spec.md), [plan.md](plan.md), [ownership](../integration-ownership.md).
**Prerequisites**: 020 execution evidence and baseline 007 task/locator contracts, 012 services and 018 invariants. Exact reconstruction T025–T028 also requires Spec 028's authorized AtMem plaintext projection and future implementation tasks; consumers never receive storage keys. Optional 019 context packages enrich investigation; missing context must not block tool-failure diagnosis.

## Phase 1: Setup and contracts

- [ ] [T001] Freeze the feature's versioned entity/operation/state/reason contracts and independent valid/invalid fixtures in `tests/fixtures/product/021/`, using the owning modules from `plan.md`; reconcile public schemas with Spec 012 and allocate any migrations through the existing registries (FR-001–FR-010).
- [ ] [T002] Add failing authorized, denied, missing, stale, replay/conflict and optional-dependency-unavailable boundary fixtures in `tests/test_incident_resolution.py`; map every FR and SC to an assertion and declare real-host versus simulated coverage (FR-001–FR-010, SC-001–SC-004; depends on T001).

## Phase 2: Foundation and primary user stories

- [ ] [T003] [US1] Implement FR-001 in `atmem/incidents/detect.py`: Derive deterministic findings distinguishing observed failure, missing evidence, recovered error, suspected cause and independently verified outcome. The earliest error is not automatically the root cause; locate the earliest unresolved relevant failure or report insufficient evidence. Verify its boundary assertions in `tests/test_incident_resolution.py` (depends on T002).
- [ ] [T004] [US1] Implement FR-002 in `atmem/incidents/explain.py`: Link every substantive incident statement to authorized event/package/policy/task references and an assurance class. Invalid or inaccessible references cannot support a statement; optional model explanation may paraphrase only supplied eligible evidence and falls back to deterministic text. Verify its boundary assertions in `tests/test_incident_resolution.py` (depends on T003).
- [ ] [T005] [US1] Implement FR-003 in `atmem/incidents/impact.py`: Trace affected work only through declared dependency/input/child links; report direct exposure separately from causal dependency and label unknown dependency coverage. Temporal adjacency, embedding similarity and ranking scores cannot establish causation. Verify its boundary assertions in `tests/test_incident_resolution.py` (depends on T004).
- [ ] [T006] [US1] Implement FR-004 in `atmem/incidents/projection.py`: Present outcome, important events, affected work, next actions and evidence in that order, including absolute timestamp, elapsed time, exact turn/tool and coverage limitations. Verify its boundary assertions in `tests/test_incident_resolution.py` (depends on T005).
- [ ] [T007] [US1] Implement FR-005 in `atmem/incidents/resolution.py`: Maintain finding state (open/acknowledged/dismissed), remediation state (not_started/in_progress/completed) and verification state (unverified/host_reported/independently_verified) independently with authenticated actors, reasons, timestamps and optimistic revisions. Verify its boundary assertions in `tests/test_incident_resolution.py` (depends on T006).
- [ ] [T008] [US2] Implement FR-006 in `atmem/incidents/reconcile.py`: Acknowledgment records review only; it cannot change execution outcomes, hide underlying evidence, claim a fix or trigger a retry. Late evidence can supersede a finding and reopen an investigation with a recorded reason. Verify its boundary assertions in `tests/test_incident_resolution.py` (depends on T007).
- [ ] [T009] [US2] Implement FR-007 in `atmem/incidents/actions.py`: Offer scope-authorized actions to inspect, assign, request correction, disable an applicable provider, revoke supported grants or record verification. Action availability comes from service authority/capabilities; unsupported remediation provides manual guidance. Verify its boundary assertions in `tests/test_incident_resolution.py` (depends on T008).
- [ ] [T010] [US2] Implement FR-008 in `atmem/incidents/recovery.py`: Before recommending executable retry/resume, require a host checkpoint reference, declared idempotency behavior and available evidence about prior external effects. Timeout after dispatch means unknown outcome until checked; absent prerequisites permit inspection advice but no automatic replay. Verify its boundary assertions in `tests/test_incident_resolution.py` (depends on T009).
- [ ] [T011] [US3] Implement FR-009 in `atmem/incidents/access.py`: Scope and audit explanations, assignment, exports and actionable commands while preserving full-fidelity evidence for authorized investigation; keep incident evidence distinct from automatically recalled personal memory. Verify its boundary assertions in `tests/test_incident_resolution.py` (depends on T010).
- [ ] [T012] [US3] Implement FR-010 in `atmem/service/incidents.py`: Expose one incident/resolution service to HTTP, SDKs, MCP and dashboard. Core schemas, classifications, APIs and default UI MUST be domain-neutral: no mandatory customer, order, refund or payment fields and no tool-name-based outcome inference. Domain-specific labels and verifier integrations are optional, registered and scoped; the same evidence and action rules apply to read-only, compute and side-effecting tools. Operator permissions are distinct from agent evidence submission. External verification requires a registered verifier and receipt rather than a model's success claim. Verify its boundary assertions in `tests/test_incident_resolution.py` (depends on T011).

## Phase 3: Acceptance, compatibility and handoff

- [ ] [T013] Execute SC-001 using `tests/test_incident_resolution.py` and the applicable installed-host/browser/load/human protocol from `plan.md`: Cross-domain software-engineering, research, enterprise-knowledge and business-operation fixtures covering successful runs, permission denial, recovered retry, missing hooks, child failure and failures unrelated to memory yield correct classification, exact evidence links and zero unsupported causation/outcome claims. Retain versioned evidence or explicitly record unavailable prerequisites (depends on T012).
- [ ] [T014] Execute SC-002 using `tests/test_incident_resolution.py` and the applicable installed-host/browser/load/human protocol from `plan.md`: An unknown external side-effect outcome produces no executable retry; acknowledgment leaves remediation and verification unchanged; replayed operator requests create one revision. Retain versioned evidence or explicitly record unavailable prerequisites (depends on T012).
- [ ] [T015] Execute SC-003 using `tests/test_incident_resolution.py` and the applicable installed-host/browser/load/human protocol from `plan.md`: Cross-scope explanation/action/export adversaries disclose zero inaccessible identifiers or content; model-unavailable runs retain a useful deterministic incident report. Retain versioned evidence or explicitly record unavailable prerequisites (depends on T012).
- [ ] [T016] Execute SC-004 using `tests/test_incident_resolution.py` and the applicable installed-host/browser/load/human protocol from `plan.md`: At least 9 of 10 operators complete the declared investigation protocol within two minutes per task, replicated on a second independent cohort of ten before advertising the usability capability; publish both cohorts and failures separately under specs/usability-protocol.md. Retain versioned evidence or explicitly record unavailable prerequisites (depends on T012).
- [ ] [T017] Run affected baseline regressions, Spec 018 assertions, privacy/deletion and applicable published-state upgrade/recovery gates; update `docs/current-status.md`, `docs/implementation-evidence/021/` (new append-only entry; see `docs/implementation-evidence/README.md`) and feature documentation with exact artifacts, commands, measurements, limitations and activation/rollback guidance (FR-001–FR-010, SC-001–SC-004; depends on T013–T016).

## Dependency and completion rules

T001 → T002 → T003–T012 in listed order → T013–T016 → T017. Cross-spec dependencies are the foundation/contract milestones named above, not every future integration task in the older specs. Shared baseline owners provide integration support after contracts freeze; they do not create a dependency cycle.

A task is complete only when its named boundary and evidence exist. Fake-host, mocked provider, browser automation and human usability measurements are different evidence classes. An unavailable optional test is not a pass for the corresponding advertised capability. No task authorizes a release, live customer action, migration of customer data or automatic external retry.

## M0 minimal findings and existing dashboard

These tasks independently deliver the profile in `specs/m0-investigation-preview.md`; they do not require completion of T001–T017 or Spec 022. Broader incident actions and dependency-impact requirements stay open.

- [x] [T018] Reuse `verify_flight` through `atmem/incidents/detect.py` for observed error, missing completion and recovered-error findings linked to scoped events; support late-evidence revisions, deterministic text and unknown external outcomes without models or context providers in `tests/test_incident_resolution.py` (FR-001–FR-002, FR-006, FR-009; depends on 020 T020).
- [x] [T019] Render these findings in existing Activity/Evidence views in `atmem/control/assets/app.{html,js,css}` through shared scoped service projections, following `specs/integration-ownership.md` terminology. Show timestamps, exact event and inspection guidance; no new navigation or executable remediation. Verify privacy, keyboard access and event pivots in `tests/test_dashboard.py` (FR-004, FR-009; depends on T018).
- [x] [T020] Run M0 success/error/gap/recovery, privacy, keyboard, timestamp and evidence-pivot UI gates in `tests/test_dashboard.py` and `tests/test_incident_resolution.py`; append technical results under `docs/implementation-evidence/021/` and link preview readiness in `docs/current-status.md`. Complete this task when technical gates pass; usability validation is independently tracked by T024 and does not block the engineering preview (SC-001, SC-003; depends on T019).

## Product-wide integration

- [ ] [T021] Define independent boundary fixtures for FR-011/SC-005 in `tests/test_incident_resolution.py` using `specs/product-requirements.md`, including private/shared scopes, readable feedback and timestamp provenance as applicable.
- [ ] [T022] Implement FR-011 through `atmem/incidents/projection.py` and the owning service contracts; preserve legacy scope behavior and authorize all displayed facts/actions (depends on T021).
- [ ] [T023] Verify SC-005 through the applicable public/host/UI boundary in `tests/test_incident_resolution.py`; retain versions, coverage, failures and usability evidence in a new entry under `docs/implementation-evidence/021/` and link changed capability status from `docs/current-status.md` before advertising the capability (depends on T022).

## Independent usability claim gate

- [ ] [T024] Register and execute `specs/usability-protocol.md` on the applicable M0 interface; retain protocol/build identity and both independent cohorts under `docs/implementation-evidence/021/`, then update `docs/current-status.md` with supported claims. Complete only when at least nine of ten operators pass in each cohort. This gates advertised measured usability, not completion of T020 or availability of the engineering preview (SC-004; depends on T019; a material interface change requires new protocol evidence).

## Standalone transparent diagnosis — 2026-09-13

- [ ] [T025] Add failing incident fixtures that consume only the copied Spec 020
  store and require exact prompt, memory/context, decision, model, call
  arguments/target, result/error and original multimodal artifacts; explicitly
  reject “a tool failed”, counts, hashes and ID-only explanations (FR-012–FR-015,
  SC-006–SC-007; depends on 020 T043).
- [ ] [T026] Implement store-only reconstruction-backed finding projections and
  exact multimodal render/export models in `atmem/incidents/`; do not query the
  original agent, logs, provider or memory store (depends on T025 and 020 T047).
- [ ] [T027] Implement deterministic inert replay-manifest inspection and clear
  reconstruction/simulation/new-execution states; no investigation action may
  cause an external effect (depends on T026).
- [ ] [T028] Execute SC-006–SC-007 through API/CLI/MCP/browser and the destructive
  installed-artifact dead-agent gate. Publish limitations and do not claim
  standalone investigation before every exact-content assertion passes
  (depends on T027 and 020 T050).
