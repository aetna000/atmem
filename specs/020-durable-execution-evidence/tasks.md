# Tasks: Durable Execution Evidence and Coverage

**Evidence policy**: Append verification to a new entry under `docs/implementation-evidence/020/` following `docs/implementation-evidence/README.md`. `docs/current-status.md` is a linked summary, not a raw test log; dated reviews are frozen. Task-ID suffixes are significant (see `specs/task-conventions.md`).

**Status**: All work below is planned and unchecked.
**Input**: [spec.md](spec.md), [plan.md](plan.md), [ownership](../integration-ownership.md).
**Prerequisites**: For M0, 007 T110 delivers the non-task ExecutionIdentity subset of T088; use existing control-store migrations and baseline adapters/services/invariants. T089/T092 task-link storage and propagation are required only for task-enabled expansion. Context capture accepts optional 019 references; investigation-only capture is independent of 019, 022 and 025.

## Phase 1: Setup and contracts

- [ ] [T001] Freeze the feature's versioned entity/operation/state/reason contracts and independent valid/invalid fixtures in `tests/fixtures/product/020/`, using the owning modules from `plan.md`; reconcile public schemas with Spec 012 and allocate any migrations through the existing registries (FR-001–FR-010).
- [ ] [T002] Add failing authorized, denied, missing, stale, replay/conflict and optional-dependency-unavailable boundary fixtures in `tests/test_execution_capture.py`; map every FR and SC to an assertion and declare real-host versus simulated coverage (FR-001–FR-010, SC-001–SC-004; depends on T001).

## Phase 2: Foundation and primary user stories

- [ ] [T003] [US1] Implement FR-001 in `atmem/contracts/execution.py`: Extend Spec 007 ExecutionIdentity with a stable authenticated job/execution ID, parent execution, attempt and retry-of references; retain distinct session, run, turn, tool-call and optional task IDs. Never infer relationships from similar names, prompts or timestamps. Verify its boundary assertions in `tests/test_execution_capture.py` (depends on T002).
- [ ] [T004] [US1] Implement FR-002 in `atmem/execution/events.py`: Record append-only typed events for model/context/tool boundaries, lifecycle, explicit progress, waiting, retry and child execution. Event identity binds producer instance/epoch and sequence; duplicate same-payload events replay idempotently, conflicting duplicates remain visible integrity findings. Verify its boundary assertions in `tests/test_execution_capture.py` (depends on T003).
- [ ] [T005] [US1] Implement FR-003 in `atmem/execution/spool.py`: Persist a bounded local capture spool and acknowledgment checkpoints; acknowledge only durable acceptance. Restart resends unacknowledged events without duplicate evidence. Disk-full, dropped events, producer reset and expired retention create explicit coverage gaps. Verify its boundary assertions in `tests/test_execution_capture.py` (depends on T004).
- [ ] [T006] [US1] Implement FR-004 in `atmem/execution/ordering.py`: Retain event time and ingest time; use producer sequence and explicit dependencies for ordering, and label incomparable cross-producer ordering and clock skew. Render elapsed time without claiming a universal exact causal order. Verify its boundary assertions in `tests/test_execution_capture.py` (depends on T005).
- [ ] [T007] [US1] Implement FR-005 in `atmem/execution/coverage.py`: Publish per-adapter/version/configuration coverage for supported, observed and enforced boundaries, including omitted hooks. Static availability or successful retrieval cannot prove model placement, tool completion or blocking. Use the public Spec 011 conformance manifest format for published results, retaining actual runtime coverage and issuer assurance separately. Verify its boundary assertions in `tests/test_execution_capture.py` (depends on T006).
- [ ] [T008] [US2] Implement FR-006 in `atmem/execution/status.py`: Classify running, waiting, succeeded, failed, cancelled and incomplete executions from observed events; silence becomes missing heartbeat or suspected stall under a declared threshold, never automatic proof of failure. Verify its boundary assertions in `tests/test_execution_capture.py` (depends on T007).
- [ ] [T009] [US2] Implement FR-007 in `atmem/execution/projection.py`: Build bounded scope-filtered execution projections across attempts/children, with cycle rejection, orphan references, cancellation, late completion and partial children explicit. Late evidence produces revised projections with provenance, not rewritten events. Verify its boundary assertions in `tests/test_execution_capture.py` (depends on T008).
- [ ] [T010] [US2] Implement FR-008 in `atmem/adapters/base.py`: Keep investigation-only mode usable without native memory, embeddings, AtBot, task activation or context changes. Link optional context packages and task revisions when supplied by authenticated hosts. Verify its boundary assertions in `tests/test_execution_capture.py` (depends on T009).
- [ ] [T011] [US3] Implement FR-009 in `atmem/service/executions.py`: Expose execution/timeline/coverage resources through the existing application service; authorize joins, counts, cursors and export as well as row content. Old flights remain inspectable and unlinked unless actual provenance establishes a job relationship. Verify its boundary assertions in `tests/test_execution_capture.py` (depends on T010).
- [ ] [T012] [US3] Implement FR-010 in `atmem/execution/retention.py`: Use allocated persisted migrations and verified retention/deletion for spool and projections. Preserve content-minimizing Black Box payloads and existing verified-flight semantics; no new default transcript or chain-of-thought retention. Verify its boundary assertions in `tests/test_execution_capture.py` (depends on T011).

## Phase 3: Acceptance, compatibility and handoff

- [ ] [T013] Execute SC-001 using `tests/test_execution_capture.py` and the applicable installed-host/browser/load/human protocol from `plan.md`: A virtual-clock 40-minute fixture with two children, recovered retry, cancellation and an orphan event reconstructs all supplied relationships and labels every planted gap. Retain versioned evidence or explicitly record unavailable prerequisites (depends on T012).
- [ ] [T014] Execute SC-002 using `tests/test_execution_capture.py` and the applicable installed-host/browser/load/human protocol from `plan.md`: Crash/restart, concurrent replay and out-of-order tests lose zero acknowledged events, create zero duplicate logical events and expose conflicting duplicates and disk exhaustion. Retain versioned evidence or explicitly record unavailable prerequisites (depends on T012).
- [ ] [T015] Execute SC-003 using `tests/test_execution_capture.py` and the applicable installed-host/browser/load/human protocol from `plan.md`: On 100,000 synthetic events, first-page (100 events) execution lookup p95 <= 200 ms on a documented local host; record write overhead and storage size separately. Retain versioned evidence or explicitly record unavailable prerequisites (depends on T012).
- [ ] [T016] Execute SC-004 using `tests/test_execution_capture.py` and the applicable installed-host/browser/load/human protocol from `plan.md`: Real supported host conformance plus an MCP-only fixture proves coverage differences; investigation-only operation causes zero canonical imports, context injections or inferred task bindings. Retain versioned evidence or explicitly record unavailable prerequisites (depends on T012).
- [ ] [T017] Run affected baseline regressions, Spec 018 assertions, privacy/deletion and applicable published-state upgrade/recovery gates; update `docs/current-status.md`, `docs/implementation-evidence/020/` (new append-only entry; see `docs/implementation-evidence/README.md`) and feature documentation with exact artifacts, commands, measurements, limitations and activation/rollback guidance (FR-001–FR-010, SC-001–SC-004; depends on T013–T016).

## Dependency and completion rules

T001 → T002 → T003–T012 in listed order → T013–T016 → T017. Cross-spec dependencies are the foundation/contract milestones named above, not every future integration task in the older specs. Shared baseline owners provide integration support after contracts freeze; they do not create a dependency cycle.

A task is complete only when its named boundary and evidence exist. Fake-host, mocked provider, browser automation and human usability measurements are different evidence classes. An unavailable optional test is not a pass for the corresponding advertised capability. No task authorizes a release, live customer action, migration of customer data or automatic external retry.

## M0 independent release sequence

The sequence below supersedes the all-T001–T017 ordering only for the non-context OpenClaw profile. Reuse delivered subwork without marking broader tasks complete. Later task/child/framework/provider acceptance remains open.

- [ ] [T018] Freeze M0 event/identity/coverage fixtures in `tests/test_execution_capture.py` after 007 T110, using `atmem/contracts/execution.py`; map full-feature requirements to in-scope and deferred assertions (FR-001–FR-010).
- [ ] [T019] Implement durable OpenClaw capture, bounded spool/replay and allocated control-store migrations in `atmem/execution/` and `integrations/openclaw/`; verify restart, duplicates, loss reporting and retention in `tests/test_execution_capture.py` (FR-001–FR-004, FR-010; depends on T018).
- [ ] [T020] Add scoped non-task execution projections and coverage to `atmem/service/executions.py`, preserving flights and honest missing relationships; prove zero memory injection/task activation and no unauthorized joins (FR-005–FR-009; depends on T019).
- [ ] [T021] Exercise the M0 virtual 40-minute and installed OpenClaw scenarios from `specs/m0-investigation-preview.md` in `tests/test_execution_capture.py` and `integrations/openclaw/test/`; record real host versions and restore/disable evidence separately from mocks (SC-001–SC-004, scoped to M0; depends on T020).
- [ ] [T022] After 021 T019, run affected installed-artifact, upgrade, privacy and regression gates; publish M0 limitations and coverage in `docs/current-status.md` and `docs/framework-adapters.md`. M0 can release without 019, 022, other hosts or completing broad 007 Amendment B (depends on T021 and completed 021 T020; 021 T024 is the separate later usability claim gate).

## Product-wide integration

- [ ] [T023] Define independent boundary fixtures for FR-011/SC-005 in `tests/test_execution_capture.py` using `specs/product-requirements.md`, including private/shared scopes, readable feedback and timestamp provenance as applicable.
- [ ] [T024] Implement FR-011 through `atmem/execution/projection.py` and the owning service contracts; preserve legacy scope behavior and authorize all displayed facts/actions (depends on T023).
- [ ] [T025] Verify SC-005 through the applicable public/host/UI boundary in `tests/test_execution_capture.py`; retain versions, coverage, failures and usability evidence in a new entry under `docs/implementation-evidence/020/` and link changed capability status from `docs/current-status.md` before advertising the capability (depends on T024).


## Existing Black Box error diagnostics — 2026-09-09

- [x] [T026] Implement FR-012–FR-013 for typed and correlated terminal tool completions, including redacted bounded reasons, independent error digests, absent-result metadata and persisted report propagation.
- [x] [T027] Implement FR-014 in the existing dashboard diagnosis list and expanded timeline: explain uncertainty, show the reason or legacy fallback, and direct operators to host logs and bridge verification before retrying.
- [x] [T028] Verify SC-006 with `tests/test_blackbox.py`, relevant dashboard checks in `tests/test_control_plane.py`, `test/hooks.mjs`, `test/tool-observations.mjs`, `test/blackbox-diagnostics.mjs`, and TypeScript build/typecheck. Local checks pass; no real-host deployment or reconstruction of historical errors is claimed.

## Progress-card duplicate observations — 2026-09-09

- [x] [T029] Trace local OpenClaw runner/native-relay reporting and independently reproduce both progress-card incident result hashes (FR-016, SC-007).
- [x] [T030] Add strict shape validation, comparison metadata and scoped projection without removing raw observations; cover changed/unknown/error/legacy cases (FR-016–FR-017).
- [x] [T031] Complete bridge, Python and presentation checks, install tested local artifacts and document limits; no fresh live-host conformance claim (SC-007).

## Selective context and timestamp clarity — 2026-09-09

- [x] [T032] Inspect latest run and component audits; distinguish one nine-record context block from repeated injections and identify wrapped HTTP 403 errors.
- [x] [T033] Implement direct-support automatic recall, opt-in persona, exclusion of duplicate persona IDs and selection metadata (FR-018).
- [x] [T034] Extract bounded known wrapper diagnostics and show local millisecond time with original UTC evidence (FR-019–FR-020).
- [x] [T035] Verify selection, bridge/MCP, wrapped errors, UTC/local timezone and mobile layout; install tested local artifacts and document limits (SC-008–SC-009).
