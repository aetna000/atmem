# Feature Specification: Incident Investigation and Resolution

**Feature directory**: `specs/021-incident-investigation-and-resolution`
**Created**: 2026-09-09
**Status**: Specified; not implemented
**Input**: Unified memory, governance and investigation product direction; [roadmap](../product-roadmap.md).

## Overview

An operator investigates an agent execution in any business or technical domain, locates observed failures and evidence gaps across turns and tools, sees affected work, and chooses a justified next action. Investigation works whether context was native, externally retrieved, delegated or absent; it does not depend on a payment workflow.

Product moment: **After a problem**. This feature extends the existing product; the shared identity, application service, canonical authority and invariant owners remain as declared in [integration ownership](../integration-ownership.md).

## User scenarios and acceptance

### US1 — Complete the primary workflow (P1)

An operator investigates an agent execution in any business or technical domain, locates observed failures and evidence gaps across turns and tools, sees affected work, and chooses a justified next action. Investigation works whether context was native, externally retrieved, delegated or absent; it does not depend on a payment workflow.

**Independent test**: Execute the scoped synthetic primary journey through the public service and a supported host. Assert FR-001–FR-010 and SC-001–SC-004; record unavailable capabilities rather than infer them.

**Acceptance**: Given authenticated scope and configured capabilities, when the primary workflow runs, then its result identifies the exact decision/event evidence and preserves the claimed boundary.

### US2 — Understand a failure without overstating evidence (P1)

An operator receives a useful deterministic result when optional intelligence or a provider/host boundary is unavailable.

**Acceptance**: Given a denied, missing, stale, replayed or unavailable input, when the workflow executes, then its failure/coverage reason is explicit, no authority widens and no external outcome is invented.

### US3 — Adopt incrementally and retain history (P2)

An existing user enables this capability explicitly and retains native memory, trusted delegation, old receipts and host state.

**Acceptance**: Given pre-feature persisted state, when upgrade and rollback/recovery are exercised, then old evidence remains inspectable, no historical relationship is fabricated and disabled capabilities do not affect execution.

## Functional requirements

- **FR-001**: Derive deterministic findings distinguishing observed failure, missing evidence, recovered error, suspected cause and independently verified outcome. The earliest error is not automatically the root cause; locate the earliest unresolved relevant failure or report insufficient evidence.
- **FR-002**: Link every substantive incident statement to authorized event/package/policy/task references and an assurance class. Invalid or inaccessible references cannot support a statement; optional model explanation may paraphrase only supplied eligible evidence and falls back to deterministic text.
- **FR-003**: Trace affected work only through declared dependency/input/child links; report direct exposure separately from causal dependency and label unknown dependency coverage. Temporal adjacency, embedding similarity and ranking scores cannot establish causation.
- **FR-004**: Present outcome, important events, affected work, next actions and evidence in that order, including absolute timestamp, elapsed time, exact turn/tool and coverage limitations.
- **FR-005**: Maintain finding state (open/acknowledged/dismissed), remediation state (not_started/in_progress/completed) and verification state (unverified/host_reported/independently_verified) independently with authenticated actors, reasons, timestamps and optimistic revisions.
- **FR-006**: Acknowledgment records review only; it cannot change execution outcomes, hide underlying evidence, claim a fix or trigger a retry. Late evidence can supersede a finding and reopen an investigation with a recorded reason.
- **FR-007**: Offer scope-authorized actions to inspect, assign, request correction, disable an applicable provider, revoke supported grants or record verification. Action availability comes from service authority/capabilities; unsupported remediation provides manual guidance.
- **FR-008**: Before recommending executable retry/resume, require a host checkpoint reference, declared idempotency behavior and available evidence about prior external effects. Timeout after dispatch means unknown outcome until checked; absent prerequisites permit inspection advice but no automatic replay.
- **FR-009**: Keep explanations, assignment, exports and actionable commands tenant/scope filtered and content-minimizing; do not store incident narratives as durable personal memory automatically.
- **FR-010**: Expose one incident/resolution service to HTTP, SDKs, MCP and dashboard. Core schemas, classifications, APIs and default UI MUST be domain-neutral: no mandatory customer, order, refund or payment fields and no tool-name-based outcome inference. Domain-specific labels and verifier integrations are optional, registered and scoped; the same evidence and action rules apply to read-only, compute and side-effecting tools. Operator permissions are distinct from agent evidence submission. External verification requires a registered verifier and receipt rather than a model's success claim.

## Key entities

- **IncidentFinding**: Finding ID/execution, classification/severity, earliest relevant event, open/acknowledged/dismissed state, supersession and evidence references.
- **EvidenceClaim**: Bounded statement, observed/inferred/independently-verified assurance, supporting event/package/policy references and unavailable evidence reasons.
- **AffectedStep**: Step ID, declared dependency path, direct exposure reference where relevant, observed outcome and completeness of known relationships.
- **ResolutionAction**: Action ID/type, scoped actor/target, allowed preconditions, effect preview, idempotency key and execution/result evidence.
- **ResolutionRevision**: Immutable revision, expected predecessor, actor/time/reason and independent finding/remediation/verification state fields.
- **OutcomeVerification**: Registered verifier ID, external operation reference, receipt digest/status/time and exact outcome verified; host reports remain lower assurance.

## Success criteria

- **SC-001**: Cross-domain software-engineering, research, enterprise-knowledge and business-operation fixtures covering successful runs, permission denial, recovered retry, missing hooks, child failure and failures unrelated to memory yield correct classification, exact evidence links and zero unsupported causation/outcome claims.
- **SC-002**: An unknown external side-effect outcome produces no executable retry; acknowledgment leaves remediation and verification unchanged; replayed operator requests create one revision.
- **SC-003**: Cross-scope explanation/action/export adversaries disclose zero inaccessible identifiers or content; model-unavailable runs retain a useful deterministic incident report.
- **SC-004**: Controlled usability with at least 10 representative operators achieves >=90% finding the relevant break, affected work/uncertainty and justified next action within two minutes; publish failures separately from automated fixture results.

## Failure and edge cases

Missing identity, inaccessible parent/reference, duplicate or conflicting delivery, timeout after external dispatch, stale generation, late evidence, deleted source, unavailable provider/model, process restart, cancellation and scope changes must have explicit bounded outcomes. Authorization covers joins, explanations, totals and exports. A source reference or signature does not establish semantic truth. Where a boundary is unsupported, report it rather than emulate a stronger guarantee.

## Dependencies and ownership

020 execution evidence and baseline 007 task/locator contracts, 012 services and 018 invariants. Optional 019 context packages enrich investigation; missing context must not block tool-failure diagnosis.

The dependency list distinguishes existing baseline modules from new contract milestones. Feature-specific assertions feed Spec 018; Spec 018's existing registry is a baseline prerequisite, not a cycle requiring future consumer code before its contracts exist.

## Compatibility, privacy and migration

Keep Python 3.10–3.13, optional provider/model/framework imports, local operation, explicit activation and egress, unchanged host-owned state and distinct canonical memory/task/evidence authorities. Closed wire schemas get new versions when needed; additive fields require negotiation. Allocate migrations through existing registries, retain legacy projections, test supported published floors, and never fabricate historical links. No default raw transcript, chain-of-thought or secret retention. Evidence metadata and hashes still require access control and retention.

## Out of scope

Autonomous compensation, owning runtime checkpoints, semantic proof of answer correctness, or universal diagnosis when hooks omitted evidence.

## Invariant Attestation

Touches INV-001, INV-002, INV-006, INV-008, INV-010, INV-011 through `spec021.scope`, `spec021.evidence`, `spec021.compatibility` and `spec021.failure`. These are planned assertion identifiers, not claims of executing tests. They become proven only when boundary tests and installed-artifact evidence exist.
