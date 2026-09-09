# Implementation Plan: Durable Execution Evidence and Coverage

**Date**: 2026-09-09
**Status**: Planned; no implementation claim
**Specification**: [spec.md](spec.md)

## Technical context

Python 3.10–3.13; current SQLite/control evidence stores and optional declared backends; current dashboard JavaScript/CSS; optional framework/provider integrations. Reuse `atmem/contracts/execution.py`, `atmem/control/blackbox.py`, `atmem/control/store.py`, `atmem/adapters/base.py`. No new mandatory model dependency or frontend framework. All new paths below are proposed until implemented.

## Foundation prerequisites

For M0, 007 T110 delivers the non-task ExecutionIdentity subset of T088; use existing control-store migrations and baseline adapters/services/invariants. T089/T092 task-link storage and propagation are required only for task-enabled expansion. Context capture accepts optional 019 references; investigation-only capture is independent of 019, 022 and 025.

## Architecture and file ownership

- **FR-001** → `atmem/contracts/execution.py`: Extend Spec 007 ExecutionIdentity with a stable authenticated job/execution ID, parent execution, attempt and retry-of references; retain distinct session, run, turn, tool-call and optional task IDs. Never infer relationships from similar names, prompts or timestamps.
- **FR-002** → `atmem/execution/events.py`: Record append-only typed events for model/context/tool boundaries, lifecycle, explicit progress, waiting, retry and child execution. Event identity binds producer instance/epoch and sequence; duplicate same-payload events replay idempotently, conflicting duplicates remain visible integrity findings.
- **FR-003** → `atmem/execution/spool.py`: Persist a bounded local capture spool and acknowledgment checkpoints; acknowledge only durable acceptance. Restart resends unacknowledged events without duplicate evidence. Disk-full, dropped events, producer reset and expired retention create explicit coverage gaps.
- **FR-004** → `atmem/execution/ordering.py`: Retain event time and ingest time; use producer sequence and explicit dependencies for ordering, and label incomparable cross-producer ordering and clock skew. Render elapsed time without claiming a universal exact causal order.
- **FR-005** → `atmem/execution/coverage.py`: Publish per-adapter/version/configuration coverage for supported, observed and enforced boundaries, including omitted hooks. Static availability or successful retrieval cannot prove model placement, tool completion or blocking. Use the public Spec 011 conformance manifest format for published results, retaining actual runtime coverage and issuer assurance separately.
- **FR-006** → `atmem/execution/status.py`: Classify running, waiting, succeeded, failed, cancelled and incomplete executions from observed events; silence becomes missing heartbeat or suspected stall under a declared threshold, never automatic proof of failure.
- **FR-007** → `atmem/execution/projection.py`: Build bounded scope-filtered execution projections across attempts/children, with cycle rejection, orphan references, cancellation, late completion and partial children explicit. Late evidence produces revised projections with provenance, not rewritten events.
- **FR-008** → `atmem/adapters/base.py`: Keep investigation-only mode usable without native memory, embeddings, AtBot, task activation or context changes. Link optional context packages and task revisions when supplied by authenticated hosts.
- **FR-009** → `atmem/service/executions.py`: Expose execution/timeline/coverage resources through the existing application service; authorize joins, counts, cursors and export as well as row content. Old flights remain inspectable and unlinked unless actual provenance establishes a job relationship.
- **FR-010** → `atmem/execution/retention.py`: Use allocated persisted migrations and verified retention/deletion for spool and projections. Preserve content-minimizing Black Box payloads and existing verified-flight semantics; no new default transcript or chain-of-thought retention.

Shared router edits go through Spec 012; shared shell edits through Spec 022; canonical schema allocations through Spec 010; existing flight-store schema evolution through its current registry coordinated by Spec 020. Preserve existing task authority and reuse Spec 007 identities. Do not allocate duplicate public resource schemas in two feature packages.

## Contracts and persistence

Freeze required fields, optionality, authority provenance, reason-code enums, state transitions, time units, bounds, preconditions and schema negotiation before implementing consumers. Use independently authored golden vectors under `tests/fixtures/product/020/`. Public transport descriptions extend `docs/contracts/atmem-api-v1.openapi.yaml` through Spec 012; closed incompatible envelopes receive separately versioned schemas under `atmem/schemas/`. Clients project the same service decisions.

Persist only state requiring durable authority/evidence or rebuildable projections. Transactional mutations include scoped idempotency and expected generation; evidence and resolution append rather than overwrite. Allocate actual migration IDs at implementation after inspecting the current registries. Upgrade old rows without invented links, and test restart, rollback compatibility/forward recovery and retention. Read-only simulations and projections cannot write canonical memory.

## Execution sequence

1. Freeze contracts and failure vectors; resolve ownership with prerequisite specs.
2. Implement FR-001–FR-010 in requirement order, sharing baseline services. Commit contract/persistence primitives before adapter or UI consumers.
3. Exercise SC-001–SC-004 through public boundaries, then applicable migration/privacy and installed-host gates.
4. Record exact versions, commands, measurements, gaps and activation/rollback guidance; enable only supported capabilities.

## Verification strategy

Primary boundary suite: `tests/test_execution_capture.py`. Add fixture-level golden inputs and assertions per requirement before implementation. Cross-interface golden tests verify scope, IDs, reason codes and state parity. A fake provider/host supports deterministic tests but does not establish live compatibility. Browser tasks require actual keyboard, viewport and navigation checks; human timing remains a separate controlled protocol.

- **SC-001**: A virtual-clock 40-minute fixture with two children, recovered retry, cancellation and an orphan event reconstructs all supplied relationships and labels every planted gap.
- **SC-002**: Crash/restart, concurrent replay and out-of-order tests lose zero acknowledged events, create zero duplicate logical events and expose conflicting duplicates and disk exhaustion.
- **SC-003**: On 100,000 synthetic events, first-page (100 events) execution lookup p95 <= 200 ms on a documented local host; record write overhead and storage size separately.
- **SC-004**: Real supported host conformance plus an MCP-only fixture proves coverage differences; investigation-only operation causes zero canonical imports, context injections or inferred task bindings.

## Constitution check

| Principle | Planned enforcement |
| --- | --- |
| I — Authority before intelligence | Existing canonical admission remains exclusive; external proposals are checked; trusted delegation stays explicitly named. |
| II — Provenance and exact evidence | Stable scoped references and digests; observed, inferred and independently verified are distinct. |
| III — Safe defaults and reversibility | Non-influencing initial state, explicit activation, bounded failure and no silent replay. |
| IV — Scope, privacy and deletion | Authorize joins/actions/exports; retain minimum evidence and verify controlled derivative deletion. |
| V — Host neutrality | Extend shared contracts and service; preserve host checkpoints, tools and histories. |
| VI — Executable claims | Boundary and installed-artifact evidence required; planned tests are not proofs. |
| VII — Local operation and explicit egress | No required hosted model, no unapproved provider query, optional extras and deterministic explanation. |

No constitutional amendment is proposed. The separately named trusted-delegation exception remains governed by Principle VII and existing Spec 003; it does not transfer canonical native-memory authority.

## Rollout and rollback

Ship contracts and non-influencing inspection first. Negotiate capability per deployed adapter/configuration, validate the milestone fixtures, then enable supported influence or actions explicitly. Preserve legacy wire/CLI paths, add redirects where applicable and keep old evidence inspectable. Rollback stops new feature actions and preserves audit; it does not undo prior model disclosure or external effects.

## M0 release profile

[The M0 release slice](../m0-investigation-preview.md) defines independent OpenClaw investigation-only delivery and exact prerequisite tasks. It overrides full-feature sequencing for that profile only: shared non-task identity, capture and minimal findings in the existing dashboard can ship before task links, providers, other hosts or the new shell. Completing the slice does not complete broader requirements. Usability claims follow [the declared protocol](../usability-protocol.md).

Terminology and legacy projections follow the canonical mapping table in `specs/integration-ownership.md`; add one shared fixture set for unlinked flights, multi-flight executions, attention-to-finding reconciliation and receipt/package distinctions. Each owning boundary suite validates its projection; no UI-only verdict mapping is permitted.

## Product-wide integration (FR-011, SC-005)

Implement FR-011 through `atmem/execution/projection.py`, consuming Spec 012 space/membership and feedback contracts, 019 context authorization, 020 time/identity evidence and the owner mappings in `specs/product-requirements.md`. Allocate persisted changes through Spec 010; retain legacy scope behavior and keep new private/shared space behavior explicit. Domain code owns facts and permissions; UI and transports project the same result.

Add boundary fixtures in `tests/test_execution_capture.py` for SC-005, including positive/negative scope access, concurrent membership changes and real-versus-unknown verification time. Report unsupported host/provider coverage rather than infer it. Existing OpenClaw APIs are adapter compatibility surfaces, not required core fields. The relevant tasks below gate this requirement; broader future features do not block M0's scoped profile.


## Existing Black Box diagnostic fix (FR-012–FR-014)

Extend the current OpenClaw completion hooks and correlated terminal-event cache
with bounded redacted reasons and separate error digests. Permit the additional
metadata in Black Box normalization and carry reasons into report error rows.
Display reasons, honest legacy fallbacks and recovery guidance in both diagnosis
rows and expanded timeline events. No event rewrite, storage migration, version
bump, broader execution service implementation or automatic retry is required.

Validate with Black Box persistence tests, the bridge hook integration suite,
terminal-observation tests, dashboard diagnostic function tests, existing dashboard
copy tests, and TypeScript build/typecheck. This is local source verification; a
fresh real-host deployment is not established by these tests.

### Progress-card equivalence implementation

Add a narrow bridge result-comparison helper for the two inspected OpenClaw
2026.9.1 progress-card shapes. Persist profile, shape and comparison digest beside
the unchanged raw digest; project proven equivalence through the existing
coalesced-call report. Reject unknown shapes and preserve historical conflicts.
Use incident-hash reproduction, bridge-to-RPC integration and persisted negative
fixtures; clarify successful duplicate wording in the dashboard. No migration,
version bump, host package patch or historical evidence mutation is required.

### Selective context and timing slice

Reuse the calibrated `decide_retrieval` direct-support gate at automatic block
selection, with an additive MCP flag and persona exclusion list. Default bridge
persona and setup persona to disabled; preserve explicit opt-in and leave manual
search available. Apply the user's local config to this selective policy. Retain
current UTC microsecond storage; expose milliseconds locally without a storage
migration. Extract only the recognized wrapped HTTP prefix and distinguish
successful run completion from individual tool errors in Spec 022 presentation.
