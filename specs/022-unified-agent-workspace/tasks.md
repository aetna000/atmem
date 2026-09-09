# Tasks: Unified Agent Workspace and Adoption

**Evidence policy**: Append verification to a new entry under `docs/implementation-evidence/022/` following `docs/implementation-evidence/README.md`. `docs/current-status.md` is a linked summary, not a raw test log; dated reviews are frozen. Task-ID suffixes are significant (see `specs/task-conventions.md`).

**Status**: All work below is planned and unchecked.
**Input**: [spec.md](spec.md), [plan.md](plan.md), [ownership](../integration-ownership.md).
**Prerequisites**: 019 context, 020 execution and 021 incident public read/action contracts, baseline 007 tasks, 012 transport and 017 onboarding. Build read-only views on stable contracts before enabling mutations.

## Phase 1: Setup and contracts

- [ ] [T001] Freeze the feature's versioned entity/operation/state/reason contracts and independent valid/invalid fixtures in `tests/fixtures/product/022/`, using the owning modules from `plan.md`; reconcile public schemas with Spec 012 and allocate any migrations through the existing registries (FR-001–FR-010).
- [ ] [T002] Add failing authorized, denied, missing, stale, replay/conflict and optional-dependency-unavailable boundary fixtures in `tests/test_unified_workspace.py`; map every FR and SC to an assertion and declare real-host versus simulated coverage (FR-001–FR-010, SC-001–SC-004; depends on T001).

## Phase 2: Foundation and primary user stories

- [ ] [T003] [US1] Implement FR-001 in `README.md`: Make the primary product promise: AtMem helps agents remember, controls the context they receive, and makes their work understandable when things go wrong. Describe native memory, external governance and investigation as adoption paths of the same product. Default navigation, onboarding and execution views MUST remain domain-neutral; examples are optional fixture content, not required workflow fields. Verify its boundary assertions in `tests/test_unified_workspace.py` (depends on T002).
- [ ] [T004] [US1] Implement FR-002 in `atmem/control/assets/app.js`: Replace the legacy four-workspace navigation with Overview, Executions, Context, Connections, Policies, Tasks and Settings; provide legacy-route redirects and preserve authorized selected execution/task/time filters on pivots and browser back. Verify its boundary assertions in `tests/test_unified_workspace.py` (depends on T003).
- [ ] [T005] [US1] Implement FR-003 in `atmem/control/web.py`: Overview MUST prioritize active executions and unresolved incidents with coverage and remediation summaries; memory-only users receive useful memory actions without fake executions or mandatory onboarding for unrelated capabilities. Verify its boundary assertions in `tests/test_unified_workspace.py` (depends on T004).
- [ ] [T006] [US1] Implement FR-004 in `atmem/control/assets/app.html`: Execution detail MUST present outcome, important events, affected work, next actions and supporting evidence; display timestamps, elapsed duration, recovered errors and unknown outcomes, with technical IDs/JSON collapsed. Verify its boundary assertions in `tests/test_unified_workspace.py` (depends on T005).
- [ ] [T007] [US1] Implement FR-005 in `atmem/control/assets/app.js`: Context MUST show native memory and external provider/source/package provenance using the same service projections; provider switching is not migration and requires no import. Policy views distinguish trusted delegation from AtMem content authorization. Verify its boundary assertions in `tests/test_unified_workspace.py` (depends on T006).
- [ ] [T008] [US2] Implement FR-006 in `atmem/onboarding.py`: Provide three resumable onboarding paths: native memory, govern existing context, investigate existing agent. Investigation has no mandatory embeddings, AtBot, memory migration or task enablement; every context-influencing path requires explicit activation. Verify its boundary assertions in `tests/test_unified_workspace.py` (depends on T007).
- [ ] [T009] [US2] Implement FR-007 in `atmem/task_state/observability.py`: Tasks remain an optional projection of canonical task authority with execution links; Connections holds provider authentication and connection lifecycle through Spec 025; Settings holds general integration, identity, deployment and retention configuration. No page creates a second authority, duplicate verdict logic or model-chosen task focus. Verify its boundary assertions in `tests/test_unified_workspace.py` (depends on T008).
- [ ] [T010] [US2] Implement FR-008 in `atmem/control/assets/app.js`: Render observed/enforced/missing coverage and acknowledgment/remediation/verification separately; expose only service-authorized actions. Every label and color has a textual meaning and never implies verified success from acknowledgment. Verify its boundary assertions in `tests/test_unified_workspace.py` (depends on T009).
- [ ] [T011] [US3] Implement FR-009 in `atmem/control/assets/app.css`: Provide keyboard-complete navigation, preserved focus, announced loading/errors, reduced motion, non-color status cues and responsive layouts at 375px and 1280px. Deep links must not disclose inaccessible resource existence. Verify its boundary assertions in `tests/test_unified_workspace.py` (depends on T010).
- [ ] [T012] [US3] Implement FR-010 in `atmem/control/assets/app.js`: Allow execution-to-event/context/policy/task and incident-to-remediation pivots in at most two actions without manual ID copying; disabled, empty, loading, partial and failure states have honest guidance. Verify its boundary assertions in `tests/test_unified_workspace.py` (depends on T011).

## Phase 3: Acceptance, compatibility and handoff

- [ ] [T013] Execute SC-001 using `tests/test_unified_workspace.py` and the applicable installed-host/browser/load/human protocol from `plan.md`: Browser journeys cover all three adoption paths and the cross-domain acceptance matrix in the roadmap, including successful runs and 40-minute investigations with zero implicit migration or context activation. Retain versioned evidence or explicitly record unavailable prerequisites (depends on T012).
- [ ] [T014] Execute SC-002 using `tests/test_unified_workspace.py` and the applicable installed-host/browser/load/human protocol from `plan.md`: Seven routes and legacy redirects preserve scope and selection; each required pivot takes <=2 actions and browser back restores the source view. Retain versioned evidence or explicitly record unavailable prerequisites (depends on T012).
- [ ] [T015] Execute SC-003 using `tests/test_unified_workspace.py` and the applicable installed-host/browser/load/human protocol from `plan.md`: Keyboard and responsive checks at both widths pass all primary flows, including failed/missing/recovered evidence and denied actions. Retain versioned evidence or explicitly record unavailable prerequisites (depends on T012).
- [ ] [T016] Execute SC-004 using `tests/test_unified_workspace.py` and the applicable installed-host/browser/load/human protocol from `plan.md`: The Spec 021 timed operator protocol meets its target through this UI; no unexecuted browser or human test is reported as passed. Retain versioned evidence or explicitly record unavailable prerequisites (depends on T012).
- [ ] [T017] Run affected baseline regressions, Spec 018 assertions, privacy/deletion and applicable published-state upgrade/recovery gates; update `docs/current-status.md`, `docs/implementation-evidence/022/` (new append-only entry; see `docs/implementation-evidence/README.md`) and feature documentation with exact artifacts, commands, measurements, limitations and activation/rollback guidance (FR-001–FR-010, SC-001–SC-004; depends on T013–T016).

## Dependency and completion rules

T001 → T002 → T003–T012 in listed order → T013–T016 → T017. Cross-spec dependencies are the foundation/contract milestones named above, not every future integration task in the older specs. Shared baseline owners provide integration support after contracts freeze; they do not create a dependency cycle.

A task is complete only when its named boundary and evidence exist. Fake-host, mocked provider, browser automation and human usability measurements are different evidence classes. An unavailable optional test is not a pass for the corresponding advertised capability. No task authorizes a release, live customer action, migration of customer data or automatic external retry.

## Product-wide integration

- [ ] [T018] Define independent boundary fixtures for FR-011/SC-005 in `tests/test_unified_workspace.py` using `specs/product-requirements.md`, including private/shared scopes, readable feedback and timestamp provenance as applicable.
- [ ] [T019] Implement FR-011 through `atmem/control/assets/app.js` and the owning service contracts; preserve legacy scope behavior and authorize all displayed facts/actions (depends on T018).
- [ ] [T020] Verify SC-005 through the applicable public/host/UI boundary in `tests/test_unified_workspace.py`; retain versions, coverage, failures and usability evidence in a new entry under `docs/implementation-evidence/022/` and link changed capability status from `docs/current-status.md` before advertising the capability (depends on T019).


## Current dashboard usability slice — 2026-09-09

- [x] [T021] Implement FR-012–FR-014: outcome/evidence separation, background identification, compact summaries, grouped conflicts and exact-event navigation.
- [x] [T022] Implement FR-015: scoped revision polling, non-overlapping refresh, visible reconnect state, and preservation of inspected details.
- [x] [T023] Implement FR-016: bounded initial run load, on-demand stories, progressive disclosure for technical/configuration controls, and collapsed assistant.
- [x] [T024] Complete browser and affected regression validation for this slice, record local measurements/limitations in `docs/implementation-evidence/022/20260909-dashboard-usability.md`, and install the local preview. This does not complete T013–T020 or the wider human usability protocol.

- [x] [T025] Implement and verify completed-with-tool-errors presentation, context-decision wording and precise local/UTC timestamps (FR-017–FR-018, SC-007); record local installation evidence with Spec 020 T035.
