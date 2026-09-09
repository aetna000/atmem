# Implementation Plan: Unified Agent Workspace and Adoption

**Date**: 2026-09-09
**Status**: Planned; no implementation claim
**Specification**: [spec.md](spec.md)

## Technical context

Python 3.10–3.13; current SQLite/control evidence stores and optional declared backends; current dashboard JavaScript/CSS; optional framework/provider integrations. Reuse `atmem/control/web.py`, `atmem/control/server.py`, `atmem/onboarding.py`, `docs/dashboard-design-language.md`. No new mandatory model dependency or frontend framework. All new paths below are proposed until implemented.

## Foundation prerequisites

019 context, 020 execution and 021 incident public read/action contracts, baseline 007 tasks, 012 transport and 017 onboarding. Build read-only views on stable contracts before enabling mutations.

## Architecture and file ownership

- **FR-001** → `README.md`: Make the primary product promise: AtMem helps agents remember, controls the context they receive, and makes their work understandable when things go wrong. Describe native memory, external governance and investigation as adoption paths of the same product. Default navigation, onboarding and execution views MUST remain domain-neutral; examples are optional fixture content, not required workflow fields.
- **FR-002** → `atmem/control/assets/app.js`: Replace the legacy four-workspace navigation with Overview, Executions, Context, Connections, Policies, Tasks and Settings; provide legacy-route redirects and preserve authorized selected execution/task/time filters on pivots and browser back.
- **FR-003** → `atmem/control/web.py`: Overview MUST prioritize active executions and unresolved incidents with coverage and remediation summaries; memory-only users receive useful memory actions without fake executions or mandatory onboarding for unrelated capabilities.
- **FR-004** → `atmem/control/assets/app.html`: Execution detail MUST present outcome, important events, affected work, next actions and supporting evidence; display timestamps, elapsed duration, recovered errors and unknown outcomes, with technical IDs/JSON collapsed.
- **FR-005** → `atmem/control/assets/app.js`: Context MUST show native memory and external provider/source/package provenance using the same service projections; provider switching is not migration and requires no import. Policy views distinguish trusted delegation from AtMem content authorization.
- **FR-006** → `atmem/onboarding.py`: Provide three resumable onboarding paths: native memory, govern existing context, investigate existing agent. Investigation has no mandatory embeddings, AtBot, memory migration or task enablement; every context-influencing path requires explicit activation.
- **FR-007** → `atmem/task_state/observability.py`: Tasks remain an optional projection of canonical task authority with execution links; Connections holds provider authentication and connection lifecycle through Spec 025; Settings holds general integration, identity, deployment and retention configuration. No page creates a second authority, duplicate verdict logic or model-chosen task focus.
- **FR-008** → `atmem/control/assets/app.js`: Render observed/enforced/missing coverage and acknowledgment/remediation/verification separately; expose only service-authorized actions. Every label and color has a textual meaning and never implies verified success from acknowledgment.
- **FR-009** → `atmem/control/assets/app.css`: Provide keyboard-complete navigation, preserved focus, announced loading/errors, reduced motion, non-color status cues and responsive layouts at 375px and 1280px. Deep links must not disclose inaccessible resource existence.
- **FR-010** → `atmem/control/assets/app.js`: Allow execution-to-event/context/policy/task and incident-to-remediation pivots in at most two actions without manual ID copying; disabled, empty, loading, partial and failure states have honest guidance.

Shared router edits go through Spec 012; shared shell edits through Spec 022; canonical schema allocations through Spec 010; existing flight-store schema evolution through its current registry coordinated by Spec 020. Preserve existing task authority and reuse Spec 007 identities. Do not allocate duplicate public resource schemas in two feature packages.

## Contracts and persistence

Freeze required fields, optionality, authority provenance, reason-code enums, state transitions, time units, bounds, preconditions and schema negotiation before implementing consumers. Use independently authored golden vectors under `tests/fixtures/product/022/`. Public transport descriptions extend `docs/contracts/atmem-api-v1.openapi.yaml` through Spec 012; closed incompatible envelopes receive separately versioned schemas under `atmem/schemas/`. Clients project the same service decisions.

Persist only state requiring durable authority/evidence or rebuildable projections. Transactional mutations include scoped idempotency and expected generation; evidence and resolution append rather than overwrite. Allocate actual migration IDs at implementation after inspecting the current registries. Upgrade old rows without invented links, and test restart, rollback compatibility/forward recovery and retention. Read-only simulations and projections cannot write canonical memory.

## Execution sequence

1. Freeze contracts and failure vectors; resolve ownership with prerequisite specs.
2. Implement FR-001–FR-010 in requirement order, sharing baseline services. Commit contract/persistence primitives before adapter or UI consumers.
3. Exercise SC-001–SC-004 through public boundaries, then applicable migration/privacy and installed-host gates.
4. Record exact versions, commands, measurements, gaps and activation/rollback guidance; enable only supported capabilities.

## Verification strategy

Primary boundary suite: `tests/test_unified_workspace.py`. Add fixture-level golden inputs and assertions per requirement before implementation. Cross-interface golden tests verify scope, IDs, reason codes and state parity. A fake provider/host supports deterministic tests but does not establish live compatibility. Browser tasks require actual keyboard, viewport and navigation checks; human timing remains a separate controlled protocol.

- **SC-001**: Browser journeys cover all three adoption paths and the cross-domain acceptance matrix in the roadmap, including successful runs and 40-minute investigations with zero implicit migration or context activation.
- **SC-002**: Seven routes and legacy redirects preserve scope and selection; each required pivot takes <=2 actions and browser back restores the source view.
- **SC-003**: Keyboard and responsive checks at both widths pass all primary flows, including failed/missing/recovered evidence and denied actions.
- **SC-004**: The Spec 021 timed operator protocol meets its target through this UI; no unexecuted browser or human test is reported as passed.

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

Terminology and legacy projections follow the canonical mapping table in `specs/integration-ownership.md`; add one shared fixture set for unlinked flights, multi-flight executions, attention-to-finding reconciliation and receipt/package distinctions. Each owning boundary suite validates its projection; no UI-only verdict mapping is permitted.

## Product-wide integration (FR-011, SC-005)

Implement FR-011 through `atmem/control/assets/app.js`, consuming Spec 012 space/membership and feedback contracts, 019 context authorization, 020 time/identity evidence and the owner mappings in `specs/product-requirements.md`. Allocate persisted changes through Spec 010; retain legacy scope behavior and keep new private/shared space behavior explicit. Domain code owns facts and permissions; UI and transports project the same result.

Add boundary fixtures in `tests/test_unified_workspace.py` for SC-005, including positive/negative scope access, concurrent membership changes and real-versus-unknown verification time. Report unsupported host/provider coverage rather than infer it. Existing OpenClaw APIs are adapter compatibility surfaces, not required core fields. The relevant tasks below gate this requirement; broader future features do not block M0's scoped profile.
