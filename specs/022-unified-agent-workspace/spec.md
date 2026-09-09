# Feature Specification: Unified Agent Workspace and Adoption

**Feature directory**: `specs/022-unified-agent-workspace`
**Created**: 2026-09-09
**Status**: Specified; not implemented
**Input**: Unified memory, governance and investigation product direction; [roadmap](../product-roadmap.md).

## Overview

A customer chooses memory, governance of existing providers, or investigation of existing agents and follows a single job from context to failure and next action without copying IDs.

Product moment: **Before, during and after execution**. This feature extends the existing product; the shared identity, application service, canonical authority and invariant owners remain as declared in [integration ownership](../integration-ownership.md).

## User scenarios and acceptance

### US1 — Complete the primary workflow (P1)

A customer chooses memory, governance of existing providers, or investigation of existing agents and follows a single job from context to failure and next action without copying IDs.

**Independent test**: Execute the scoped synthetic primary journey through the public service and a supported host. Assert FR-001–FR-010 and SC-001–SC-004; record unavailable capabilities rather than infer them.

**Acceptance**: Given authenticated scope and configured capabilities, when the primary workflow runs, then its result identifies the exact decision/event evidence and preserves the claimed boundary.

### US2 — Understand a failure without overstating evidence (P1)

An operator receives a useful deterministic result when optional intelligence or a provider/host boundary is unavailable.

**Acceptance**: Given a denied, missing, stale, replayed or unavailable input, when the workflow executes, then its failure/coverage reason is explicit, no authority widens and no external outcome is invented.

### US3 — Adopt incrementally and retain history (P2)

An existing user enables this capability explicitly and retains native memory, trusted delegation, old receipts and host state.

**Acceptance**: Given pre-feature persisted state, when upgrade and rollback/recovery are exercised, then old evidence remains inspectable, no historical relationship is fabricated and disabled capabilities do not affect execution.

## Functional requirements

- **FR-001**: Make the primary product promise: AtMem helps agents remember, controls the context they receive, and makes their work understandable when things go wrong. Describe native memory, external governance and investigation as adoption paths of the same product. Default navigation, onboarding and execution views MUST remain domain-neutral; examples are optional fixture content, not required workflow fields.
- **FR-002**: Replace the legacy four-workspace navigation with Overview, Executions, Context, Policies, Tasks and Settings; provide legacy-route redirects and preserve authorized selected execution/task/time filters on pivots and browser back.
- **FR-003**: Overview MUST prioritize active executions and unresolved incidents with coverage and remediation summaries; memory-only users receive useful memory actions without fake executions or mandatory onboarding for unrelated capabilities.
- **FR-004**: Execution detail MUST present outcome, important events, affected work, next actions and supporting evidence; display timestamps, elapsed duration, recovered errors and unknown outcomes, with technical IDs/JSON collapsed.
- **FR-005**: Context MUST show native memory and external provider/source/package provenance using the same service projections; provider switching is not migration and requires no import. Policy views distinguish trusted delegation from AtMem content authorization.
- **FR-006**: Provide three resumable onboarding paths: native memory, govern existing context, investigate existing agent. Investigation has no mandatory embeddings, AtBot, memory migration or task enablement; every context-influencing path requires explicit activation.
- **FR-007**: Tasks remain an optional projection of canonical task authority with execution links; Settings holds integration, identity, deployment and retention configuration. No page creates a second authority, duplicate verdict logic or model-chosen task focus.
- **FR-008**: Render observed/enforced/missing coverage and acknowledgment/remediation/verification separately; expose only service-authorized actions. Every label and color has a textual meaning and never implies verified success from acknowledgment.
- **FR-009**: Provide keyboard-complete navigation, preserved focus, announced loading/errors, reduced motion, non-color status cues and responsive layouts at 375px and 1280px. Deep links must not disclose inaccessible resource existence.
- **FR-010**: Allow execution-to-event/context/policy/task and incident-to-remediation pivots in at most two actions without manual ID copying; disabled, empty, loading, partial and failure states have honest guidance.

## Key entities

- **WorkspaceRoute**: One of six route names, legacy alias mapping, authorized resource selection and browser-history state.
- **AdoptionProfile**: Memory/governance/investigation selection, required capability checks, optional components, activation boundaries and setup checkpoint.
- **ExecutionDetailProjection**: Outcome, ordered important events, affected steps/uncertainty, authorized next actions and scoped evidence links.
- **NavigationContext**: Selected execution/task/context references, filters, time range and focus-return target; resolved under current access rules.
- **ActionAvailability**: Action ID, permitted/disabled state, authority/capability reason, effect preview and required confirmation/preconditions.

## Success criteria

- **SC-001**: Browser journeys cover all three adoption paths and the cross-domain acceptance matrix in the roadmap, including successful runs and 40-minute investigations with zero implicit migration or context activation.
- **SC-002**: Six routes and legacy redirects preserve scope and selection; each required pivot takes <=2 actions and browser back restores the source view.
- **SC-003**: Keyboard and responsive checks at both widths pass all primary flows, including failed/missing/recovered evidence and denied actions.
- **SC-004**: The Spec 021 timed operator protocol meets its target through this UI; no unexecuted browser or human test is reported as passed.

## Failure and edge cases

Missing identity, inaccessible parent/reference, duplicate or conflicting delivery, timeout after external dispatch, stale generation, late evidence, deleted source, unavailable provider/model, process restart, cancellation and scope changes must have explicit bounded outcomes. Authorization covers joins, explanations, totals and exports. A source reference or signature does not establish semantic truth. Where a boundary is unsupported, report it rather than emulate a stronger guarantee.

## Dependencies and ownership

019 context, 020 execution and 021 incident public read/action contracts, baseline 007 tasks, 012 transport and 017 onboarding. Build read-only views on stable contracts before enabling mutations.

The dependency list distinguishes existing baseline modules from new contract milestones. Feature-specific assertions feed Spec 018; Spec 018's existing registry is a baseline prerequisite, not a cycle requiring future consumer code before its contracts exist.

## Compatibility, privacy and migration

Keep Python 3.10–3.13, optional provider/model/framework imports, local operation, explicit activation and egress, unchanged host-owned state and distinct canonical memory/task/evidence authorities. Closed wire schemas get new versions when needed; additive fields require negotiation. Allocate migrations through existing registries, retain legacy projections, test supported published floors, and never fabricate historical links. No default raw transcript, chain-of-thought or secret retention. Evidence metadata and hashes still require access control and retention.

## Out of scope

A second dashboard, changing canonical task semantics, introducing a design framework without need, or automatic recovery from a UI click without prerequisites.

## Invariant Attestation

Touches INV-004, INV-005, INV-006, INV-008, INV-009, INV-010 through `spec022.scope`, `spec022.evidence`, `spec022.compatibility` and `spec022.failure`. These are planned assertion identifiers, not claims of executing tests. They become proven only when boundary tests and installed-artifact evidence exist.
