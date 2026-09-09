# Feature Specification: Durable Execution Evidence and Coverage

**Product-wide requirements**: [Agent neutrality, multiple agents, private/shared memory, governed providers and clear time-aware feedback](../product-requirements.md) (PR-001–PR-006). Applies to this feature's advertised capabilities; implementation status below remains authoritative.

**Feature directory**: `specs/020-durable-execution-evidence`
**Created**: 2026-09-09
**Status**: Specified; not implemented
**Input**: Unified memory, governance and investigation product direction; [roadmap](../product-roadmap.md).

## Overview

An operator opens a 40-minute job containing retries and child agents and sees one ordered execution with explicit gaps, even after a process restart.

Product moment: **During execution**. This feature extends the existing product; the shared identity, application service, canonical authority and invariant owners remain as declared in [integration ownership](../integration-ownership.md).

## User scenarios and acceptance

### US1 — Complete the primary workflow (P1)

An operator opens a 40-minute job containing retries and child agents and sees one ordered execution with explicit gaps, even after a process restart.

**Independent test**: Execute the scoped synthetic primary journey through the public service and a supported host. Assert FR-001–FR-010 and SC-001–SC-004; record unavailable capabilities rather than infer them.

**Acceptance**: Given authenticated scope and configured capabilities, when the primary workflow runs, then its result identifies the exact decision/event evidence and preserves the claimed boundary.

### US2 — Understand a failure without overstating evidence (P1)

An operator receives a useful deterministic result when optional intelligence or a provider/host boundary is unavailable.

**Acceptance**: Given a denied, missing, stale, replayed or unavailable input, when the workflow executes, then its failure/coverage reason is explicit, no authority widens and no external outcome is invented.

### US3 — Adopt incrementally and retain history (P2)

An existing user enables this capability explicitly and retains native memory, trusted delegation, old receipts and host state.

**Acceptance**: Given pre-feature persisted state, when upgrade and rollback/recovery are exercised, then old evidence remains inspectable, no historical relationship is fabricated and disabled capabilities do not affect execution.

## Functional requirements

- **FR-001**: Extend Spec 007 ExecutionIdentity with a stable authenticated job/execution ID, parent execution, attempt and retry-of references; retain distinct session, run, turn, tool-call and optional task IDs. Never infer relationships from similar names, prompts or timestamps.
- **FR-002**: Record append-only typed events for model/context/tool boundaries, lifecycle, explicit progress, waiting, retry and child execution. Event identity binds producer instance/epoch and sequence; duplicate same-payload events replay idempotently, conflicting duplicates remain visible integrity findings.
- **FR-003**: Persist a bounded local capture spool and acknowledgment checkpoints; acknowledge only durable acceptance. Restart resends unacknowledged events without duplicate evidence. Disk-full, dropped events, producer reset and expired retention create explicit coverage gaps.
- **FR-004**: Retain event time and ingest time; use producer sequence and explicit dependencies for ordering, and label incomparable cross-producer ordering and clock skew. Render elapsed time without claiming a universal exact causal order.
- **FR-005**: Publish per-adapter/version/configuration coverage for supported, observed and enforced boundaries, including omitted hooks. Static availability or successful retrieval cannot prove model placement, tool completion or blocking. Use the public Spec 011 conformance manifest format for published results, retaining actual runtime coverage and issuer assurance separately.
- **FR-006**: Classify running, waiting, succeeded, failed, cancelled and incomplete executions from observed events; silence becomes missing heartbeat or suspected stall under a declared threshold, never automatic proof of failure.
- **FR-007**: Build bounded scope-filtered execution projections across attempts/children, with cycle rejection, orphan references, cancellation, late completion and partial children explicit. Late evidence produces revised projections with provenance, not rewritten events.
- **FR-008**: Keep investigation-only mode usable without native memory, embeddings, AtBot, task activation or context changes. Link optional context packages and task revisions when supplied by authenticated hosts.
- **FR-009**: Expose execution/timeline/coverage resources through the existing application service; authorize joins, counts, cursors and export as well as row content. Old flights remain inspectable and unlinked unless actual provenance establishes a job relationship.
- **FR-010**: Use allocated persisted migrations and verified retention/deletion for spool and projections. Preserve content-minimizing Black Box payloads and existing verified-flight semantics; no new default transcript or chain-of-thought retention.

## Key entities

- **JobExecution**: Authenticated job ID, owning scope, optional parent, associated run/turn references, observed start/end and coverage-aware status.
- **ExecutionAttempt**: Attempt ID, execution ID, explicit retry-of reference, host attempt number and observed lifecycle.
- **StepLink**: Scoped source/target event or step IDs, dependency/child/input relationship, declaring producer and evidence reference.
- **EvidenceEvent**: Producer instance/epoch/sequence, event ID/type, execution/attempt/turn/tool references, event and ingest times, safe payload digest and assurance.
- **CoverageManifest**: Adapter/host/version/configuration identity, supported/observed/enforced boundary sets, gaps, last producer sequence and assessment time.
- **CaptureCheckpoint**: Durable spool position, acknowledged producer sequence, retained range, replay state and loss/backpressure reason.

## Success criteria

- **SC-001**: A virtual-clock 40-minute fixture with two children, recovered retry, cancellation and an orphan event reconstructs all supplied relationships and labels every planted gap.
- **SC-002**: Crash/restart, concurrent replay and out-of-order tests lose zero acknowledged events, create zero duplicate logical events and expose conflicting duplicates and disk exhaustion.
- **SC-003**: On 100,000 synthetic events, first-page (100 events) execution lookup p95 <= 200 ms on a documented local host; record write overhead and storage size separately.
- **SC-004**: Real supported host conformance plus an MCP-only fixture proves coverage differences; investigation-only operation causes zero canonical imports, context injections or inferred task bindings.

## Failure and edge cases

Missing identity, inaccessible parent/reference, duplicate or conflicting delivery, timeout after external dispatch, stale generation, late evidence, deleted source, unavailable provider/model, process restart, cancellation and scope changes must have explicit bounded outcomes. Authorization covers joins, explanations, totals and exports. A source reference or signature does not establish semantic truth. Where a boundary is unsupported, report it rather than emulate a stronger guarantee.

## Dependencies and ownership

For M0, 007 T110 delivers the non-task ExecutionIdentity subset of T088; use existing control-store migrations and baseline adapters/services/invariants. T089/T092 task-link storage and propagation are required only for task-enabled expansion. Context capture accepts optional 019 references; investigation-only capture is independent of 019, 022 and 025.

The dependency list distinguishes existing baseline modules from new contract milestones. Feature-specific assertions feed Spec 018; Spec 018's existing registry is a baseline prerequisite, not a cycle requiring future consumer code before its contracts exist.

## Compatibility, privacy and migration

Keep Python 3.10–3.13, optional provider/model/framework imports, local operation, explicit activation and egress, unchanged host-owned state and distinct canonical memory/task/evidence authorities. Closed wire schemas get new versions when needed; additive fields require negotiation. Allocate migrations through existing registries, retain legacy projections, test supported published floors, and never fabricate historical links. No default raw transcript, chain-of-thought or secret retention. Evidence metadata and hashes still require access control and retention.

## Out of scope

Owning host scheduling/checkpoints, guaranteeing capture of unreported events, treating heartbeat absence as proof of task failure, or automated restart.

## Invariant Attestation

Touches INV-004, INV-005, INV-006, INV-008, INV-010, INV-011 through `spec020.scope`, `spec020.evidence`, `spec020.compatibility` and `spec020.failure`. These are planned assertion identifiers, not claims of executing tests. They become proven only when boundary tests and installed-artifact evidence exist.

## M0 release profile

[The M0 release slice](../m0-investigation-preview.md) defines independent OpenClaw investigation-only delivery and exact prerequisite tasks. It overrides full-feature sequencing for that profile only: shared non-task identity, capture and minimal findings in the existing dashboard can ship before task links, providers, other hosts or the new shell. Completing the slice does not complete broader requirements. Usability claims follow [the declared protocol](../usability-protocol.md).

## Product-wide requirements — agent neutrality and clear evidence

**Required, not yet implemented:** [Product requirements](../product-requirements.md) PR-001–PR-002, PR-005–PR-006. This amendment applies to this feature's public and UI boundaries; host-specific integrations cannot redefine core identity or authority.

- **FR-011**: Preserve authenticated framework-qualified agent identities across concurrent and explicitly linked parent/child work without inheriting access. Publish event time, receive time, clock/source provenance, elapsed duration where calculable and last actual coverage verification. Unknown/skewed clocks and late events remain explicit; display refresh cannot change event or verification time.
- **SC-005**: Concurrent agents with colliding display names retain distinct scope and evidence; time fixtures cover late arrival, absent timestamps, clock skew, timezone/daylight-saving changes and refresh without re-verification, with zero invented ordering or timestamp claims.

This work extends existing authority and preserves legacy scopes. Private/shared memory and multi-framework claims require their own evidence; M0 delivers only its applicable capture/feedback subset. See the central ownership and release matrix.
