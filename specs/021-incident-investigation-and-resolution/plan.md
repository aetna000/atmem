# Implementation Plan: Incident Investigation and Resolution

**Date**: 2026-09-09
**Status**: Planned; no implementation claim
**Specification**: [spec.md](spec.md)

## Technical context

Python 3.10–3.13; current SQLite/control evidence stores and optional declared backends; current dashboard JavaScript/CSS; optional framework/provider integrations. Reuse `atmem/control/blackbox.py`, `atmem/investigation/`, `atmem/service/application.py`, `atmem/task_state/observability.py`. No new mandatory model dependency or frontend framework. All new paths below are proposed until implemented.

## Foundation prerequisites

020 execution evidence and baseline 007 task/locator contracts, 012 services and 018 invariants. Optional 019 context packages enrich investigation; missing context must not block tool-failure diagnosis.

## Architecture and file ownership

- **FR-001** → `atmem/incidents/detect.py`: Derive deterministic findings distinguishing observed failure, missing evidence, recovered error, suspected cause and independently verified outcome. The earliest error is not automatically the root cause; locate the earliest unresolved relevant failure or report insufficient evidence.
- **FR-002** → `atmem/incidents/explain.py`: Link every substantive incident statement to authorized event/package/policy/task references and an assurance class. Invalid or inaccessible references cannot support a statement; optional model explanation may paraphrase only supplied eligible evidence and falls back to deterministic text.
- **FR-003** → `atmem/incidents/impact.py`: Trace affected work only through declared dependency/input/child links; report direct exposure separately from causal dependency and label unknown dependency coverage. Temporal adjacency, embedding similarity and ranking scores cannot establish causation.
- **FR-004** → `atmem/incidents/projection.py`: Present outcome, important events, affected work, next actions and evidence in that order, including absolute timestamp, elapsed time, exact turn/tool and coverage limitations.
- **FR-005** → `atmem/incidents/resolution.py`: Maintain finding state (open/acknowledged/dismissed), remediation state (not_started/in_progress/completed) and verification state (unverified/host_reported/independently_verified) independently with authenticated actors, reasons, timestamps and optimistic revisions.
- **FR-006** → `atmem/incidents/reconcile.py`: Acknowledgment records review only; it cannot change execution outcomes, hide underlying evidence, claim a fix or trigger a retry. Late evidence can supersede a finding and reopen an investigation with a recorded reason.
- **FR-007** → `atmem/incidents/actions.py`: Offer scope-authorized actions to inspect, assign, request correction, disable an applicable provider, revoke supported grants or record verification. Action availability comes from service authority/capabilities; unsupported remediation provides manual guidance.
- **FR-008** → `atmem/incidents/recovery.py`: Before recommending executable retry/resume, require a host checkpoint reference, declared idempotency behavior and available evidence about prior external effects. Timeout after dispatch means unknown outcome until checked; absent prerequisites permit inspection advice but no automatic replay.
- **FR-009** → `atmem/incidents/privacy.py`: Keep explanations, assignment, exports and actionable commands tenant/scope filtered and content-minimizing; do not store incident narratives as durable personal memory automatically.
- **FR-010** → `atmem/service/incidents.py`: Expose one incident/resolution service to HTTP, SDKs, MCP and dashboard. Core schemas, classifications, APIs and default UI MUST be domain-neutral: no mandatory customer, order, refund or payment fields and no tool-name-based outcome inference. Domain-specific labels and verifier integrations are optional, registered and scoped; the same evidence and action rules apply to read-only, compute and side-effecting tools. Operator permissions are distinct from agent evidence submission. External verification requires a registered verifier and receipt rather than a model's success claim.

Shared router edits go through Spec 012; shared shell edits through Spec 022; canonical schema allocations through Spec 010; existing flight-store schema evolution through its current registry coordinated by Spec 020. Preserve existing task authority and reuse Spec 007 identities. Do not allocate duplicate public resource schemas in two feature packages.

## Contracts and persistence

Freeze required fields, optionality, authority provenance, reason-code enums, state transitions, time units, bounds, preconditions and schema negotiation before implementing consumers. Use independently authored golden vectors under `tests/fixtures/product/021/`. Public transport descriptions extend `docs/contracts/atmem-api-v1.openapi.yaml` through Spec 012; closed incompatible envelopes receive separately versioned schemas under `atmem/schemas/`. Clients project the same service decisions.

Persist only state requiring durable authority/evidence or rebuildable projections. Transactional mutations include scoped idempotency and expected generation; evidence and resolution append rather than overwrite. Allocate actual migration IDs at implementation after inspecting the current registries. Upgrade old rows without invented links, and test restart, rollback compatibility/forward recovery and retention. Read-only simulations and projections cannot write canonical memory.

## Execution sequence

1. Freeze contracts and failure vectors; resolve ownership with prerequisite specs.
2. Implement FR-001–FR-010 in requirement order, sharing baseline services. Commit contract/persistence primitives before adapter or UI consumers.
3. Exercise SC-001–SC-004 through public boundaries, then applicable migration/privacy and installed-host gates.
4. Record exact versions, commands, measurements, gaps and activation/rollback guidance; enable only supported capabilities.

## Verification strategy

Primary boundary suite: `tests/test_incident_resolution.py`. Add fixture-level golden inputs and assertions per requirement before implementation. Cross-interface golden tests verify scope, IDs, reason codes and state parity. A fake provider/host supports deterministic tests but does not establish live compatibility. Browser tasks require actual keyboard, viewport and navigation checks; human timing remains a separate controlled protocol.

- **SC-001**: Cross-domain software-engineering, research, enterprise-knowledge and business-operation fixtures covering successful runs, permission denial, recovered retry, missing hooks, child failure and failures unrelated to memory yield correct classification, exact evidence links and zero unsupported causation/outcome claims.
- **SC-002**: An unknown external side-effect outcome produces no executable retry; acknowledgment leaves remediation and verification unchanged; replayed operator requests create one revision.
- **SC-003**: Cross-scope explanation/action/export adversaries disclose zero inaccessible identifiers or content; model-unavailable runs retain a useful deterministic incident report.
- **SC-004**: At least 9 of 10 operators complete the declared investigation protocol within two minutes per task, replicated on a second independent cohort of ten before advertising the usability capability; publish both cohorts and failures separately under specs/usability-protocol.md.

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

Implement FR-011 through `atmem/incidents/projection.py`, consuming Spec 012 space/membership and feedback contracts, 019 context authorization, 020 time/identity evidence and the owner mappings in `specs/product-requirements.md`. Allocate persisted changes through Spec 010; retain legacy scope behavior and keep new private/shared space behavior explicit. Domain code owns facts and permissions; UI and transports project the same result.

Add boundary fixtures in `tests/test_incident_resolution.py` for SC-005, including positive/negative scope access, concurrent membership changes and real-versus-unknown verification time. Report unsupported host/provider coverage rather than infer it. Existing OpenClaw APIs are adapter compatibility surfaces, not required core fields. The relevant tasks below gate this requirement; broader future features do not block M0's scoped profile.
