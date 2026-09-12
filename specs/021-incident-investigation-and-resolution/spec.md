# Feature Specification: Incident Investigation and Resolution

**Product-wide requirements**: [Agent neutrality, standalone full-fidelity evidence and encrypted privileged plaintext](../product-requirements.md) (PR-001–PR-008). Applies to this feature's advertised capabilities; implementation status below remains authoritative.

**Feature directory**: `specs/021-incident-investigation-and-resolution`
**Created**: 2026-09-09
**Status**: Earlier deterministic findings are implemented, but standalone reconstruction/diagnosis T025–T028 is open and the revised 2.3.0b1 profile is not release-ready
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
- **FR-009**: Keep explanations, assignment, exports and actionable commands tenant/scope filtered while exposing full-fidelity evidence to authorized owners/investigators. Store the canonical incident narrative as execution evidence, not as automatically recalled personal memory.
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
- **SC-004**: At least 9 of 10 operators complete the declared investigation protocol within two minutes per task, replicated on a second independent cohort of ten before advertising the usability capability; publish both cohorts and failures separately under specs/usability-protocol.md.

## Failure and edge cases

Missing identity, inaccessible parent/reference, duplicate or conflicting delivery, timeout after external dispatch, stale generation, late evidence, deleted source, unavailable provider/model, process restart, cancellation and scope changes must have explicit bounded outcomes. Authorization covers joins, explanations, totals and exports. A source reference or signature does not establish semantic truth. Where a boundary is unsupported, report it rather than emulate a stronger guarantee.

## Dependencies and ownership

020 execution evidence and baseline 007 task/locator contracts, 012 services and 018 invariants. Optional 019 context packages enrich investigation; missing context must not block tool-failure diagnosis.

The dependency list distinguishes existing baseline modules from new contract milestones. Feature-specific assertions feed Spec 018; Spec 018's existing registry is a baseline prerequisite, not a cycle requiring future consumer code before its contracts exist.

## Compatibility, privacy and migration

Keep Python 3.10–3.13, optional provider/model/framework imports, local operation, explicit activation and egress, unchanged host-owned state and distinct canonical memory/task/evidence authorities. Closed wire schemas get new versions when needed; additive fields require negotiation. Allocate migrations through existing registries, retain legacy projections, test supported published floors, and never fabricate historical links or content. Full-fidelity boundary evidence is retained by default; access is scoped/audited and credentials receive reversible protection.

## Out of scope

Autonomous compensation, owning runtime checkpoints, semantic proof of answer correctness, or universal diagnosis when hooks omitted evidence.

## Invariant Attestation

Touches INV-001, INV-002, INV-006, INV-008, INV-010, INV-011 through `spec021.scope`, `spec021.evidence`, `spec021.compatibility` and `spec021.failure`. These are planned assertion identifiers, not claims of executing tests. They become proven only when boundary tests and installed-artifact evidence exist.

## M0 release profile

[The M0 release slice](../m0-investigation-preview.md) defines independent OpenClaw investigation-only delivery and exact prerequisite tasks. It overrides full-feature sequencing for that profile only: shared non-task identity, store-only diagnosis and the evidence-specific Spec 022 destinations can ship before task links, providers, other hosts or the broader application shell. Completing the slice does not complete broader requirements. Usability claims follow [the declared protocol](../usability-protocol.md).

## Product-wide requirements — agent neutrality and standalone evidence

**Required, not yet implemented:** [Product requirements](../product-requirements.md) PR-002 and PR-005–PR-007. This amendment applies to this feature's public and UI boundaries; host-specific integrations cannot redefine core identity or authority.

- **FR-011**: Every finding/summary states what happened, the accessible acting agent/resource, absolute time, evidence basis, known effect or uncertainty and authorized next action or reason none is available. Keep status, severity, acknowledgment and assurance independent. Domain services supply deterministic reasons and timestamps; denied explanations do not disclose hidden agents, spaces or sources.
- **SC-005**: Successful, recovered, denied, failed and missing-evidence fixtures yield understandable explanations without a model or color; inspection advice is evidence-linked, stale checks show age, and unavailable time/impact/action remain explicitly unknown.

This work extends existing authority and preserves legacy scopes. Private/shared memory and multi-framework claims require their own evidence; M0 delivers only its applicable capture/feedback subset. See the central ownership and release matrix.

## Standalone reconstruction and transparent diagnosis amendment — 2026-09-13

This amendment supersedes FR-009 and the compatibility section wherever
“content-minimizing” or “no default raw transcript” would prevent an authorized
owner from seeing full evidence captured under Spec 020.

- **FR-012**: Build every finding from the standalone AtMem evidence store. The
  primary narrative MUST state the exact user request, relevant memory/context
  and decision, exact model step, exact tool name/call/arguments/target, exact
  result or error and known outcome. “A tool failed”, a count, hash, opaque ID or
  instruction to ask the original agent/log is never a sufficient diagnosis.
- **FR-013**: Render and export original multimodal evidence—text, links/fetched
  pages, files, images, screenshots, audio and video—in its captured order.
  Captions and transcripts assist search and accessibility but do not replace
  original artifacts.
- **FR-014**: Investigation MUST remain functional when the agent, logs,
  workspace, memory/provider database, model and network are unavailable. Live
  external references may enrich current evidence but cannot be required to
  explain a retained run.
- **FR-015**: Present replay as three distinct states: historical reconstruction,
  effect-free simulation and newly authorized execution. A replay manifest shows
  exact captured inputs and missing prerequisites. It cannot silently call a
  tool, repeat an external effect or rewrite the historical run.

- **SC-006**: From the Spec 020 dead-agent fixture and copied AtMem store alone,
  ten of ten scripted investigations recover the planted prompt, memory/context,
  decision, model exchange, exact tool target/arguments, result/error and all
  multimodal artifacts. Expected wording tests reject generic nouns and counts
  when exact evidence exists.
- **SC-007**: Full-capture, metadata-only, missing-boundary and legacy hash-only
  runs are visibly distinct. Only full capture is described as reconstructable;
  every missing byte names the exact unavailable boundary without referring the
  user to destroyed host logs.
