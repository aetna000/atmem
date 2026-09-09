# Implementation Plan: Provider-Neutral Context Governance

**Date**: 2026-09-09
**Status**: Planned; no implementation claim
**Specification**: [spec.md](spec.md)

## Technical context

Python 3.10–3.13; current SQLite/control evidence stores and optional declared backends; current dashboard JavaScript/CSS; optional framework/provider integrations. Reuse `atmem/provider_adapters/`, `atmem/delegated/`, `atmem/memory.py`, `atmem/service/application.py`. No new mandatory model dependency or frontend framework. All new paths below are proposed until implemented.

## Foundation prerequisites

Baseline 003, 004, 008, 012 and 018. Reuse 007 ExecutionIdentity once its contract task T088 lands; optional execution references remain absent for memory-only use.

## Architecture and file ownership

- **FR-001** → `atmem/context/models.py`: Define a versioned provider-neutral request/package/decision contract shared by native memory, governed-external retrieval and explicitly trusted delegation. Persist and expose the selected authority mode, content authorizer and delegation-policy decision separately; a common envelope MUST NOT imply identical content authorization. Provider capability is not permission to switch mode: changes require explicit operator configuration, and failure MUST NOT silently escalate to trusted delegation. Identity is derived from authenticated runtime scope; a model cannot choose another principal or task.
- **FR-002** → `atmem/context/native.py`: Implement a native provider adapter that calls current admission/retrieval/revalidation without duplicating canonical storage; external providers retain their own stores and rankers. Retrieval never implicitly imports or remembers content.
- **FR-003** → `atmem/context/egress.py`: Authorize destination and minimum necessary query/attributes before outbound provider access; record allowed/denied request egress separately from returned-content authorization. Missing required purpose or access attributes withhold rather than broaden access.
- **FR-004** → `atmem/context/policy.py`: In governed-external mode, distinguish provider proposals from AtMem enterprise-policy authorization. Attribute every source/access/sensitivity claim as source-authoritative, operator-confirmed, model-inferred or unknown; only configured trusted attributes can satisfy access rules.
- **FR-005** → `atmem/context/packages.py`: Package provider/source versions, scope, purpose, destination, expiry, generation, content digest and bounded provenance; distinguish prepared, authorized, returned-to-host, observed-exposed and enforced states. No receipt proves model understanding.
- **FR-006** → `atmem/context/delegation.py`: Preserve the closed trusted-delegation v1 wire format and provider exact bytes. The registered provider authorizes that exact package; AtMem enforces delegation policy, scope/destination binding, expiry, replay protection and delivery evidence, without claiming independent content-policy authorization. An invalid delegation withholds context. Redaction or composition produces a new package with ordered parent digests, transformation version and authorization; never claim the provider signed transformed content.
- **FR-007** → `atmem/context/grants.py`: Issue an expiring delivery grant bound to package digest, policy generation, authenticated scope, execution/turn/model-call identity when available and destination. Supported adapters validate at dispatch, reject mismatch/expiry/replay and record exposure separately. Tool-only clients cannot claim this enforcement.
- **FR-008** → `atmem/context/providers.py`: Negotiate provider capabilities for source versions, access attributes, deletion, freshness and health. Unsupported fields remain explicit and cannot satisfy required policy; a provider switch alone changes no canonical memory.
- **FR-009** → `atmem/context/compatibility.py`: Keep legacy native APIs and disabled delegation compatible; begin new integrations non-influencing and activate explicitly. Native deterministic operation and incident evidence require no hosted model or provider SDK.
- **FR-010** → `atmem/service/context.py`: Expose shared context and decision resources through Spec 012 services. Deliver one-provider parity first, then explicitly configured native-plus-document composition for the cross-domain milestone: preserve ordered source segments, bound bytes, withhold when any required segment is denied/missing/over budget, and expose optional omissions and conflicting source claims without silently resolving them. Never combine trusted v1 authority with native retrieval.

Shared router edits go through Spec 012; shared shell edits through Spec 022; canonical schema allocations through Spec 010; existing flight-store schema evolution through its current registry coordinated by Spec 020. Preserve existing task authority and reuse Spec 007 identities. Do not allocate duplicate public resource schemas in two feature packages.

## Contracts and persistence

Freeze required fields, optionality, authority provenance, reason-code enums, state transitions, time units, bounds, preconditions and schema negotiation before implementing consumers. Use independently authored golden vectors under `tests/fixtures/product/019/`. Public transport descriptions extend `docs/contracts/atmem-api-v1.openapi.yaml` through Spec 012; closed incompatible envelopes receive separately versioned schemas under `atmem/schemas/`. Clients project the same service decisions.

Persist only state requiring durable authority/evidence or rebuildable projections. Transactional mutations include scoped idempotency and expected generation; evidence and resolution append rather than overwrite. Allocate actual migration IDs at implementation after inspecting the current registries. Upgrade old rows without invented links, and test restart, rollback compatibility/forward recovery and retention. Read-only simulations and projections cannot write canonical memory.

## Execution sequence

1. Freeze contracts and failure vectors; resolve ownership with prerequisite specs.
2. Implement FR-001–FR-010 in requirement order, sharing baseline services. Commit contract/persistence primitives before adapter or UI consumers.
3. Exercise SC-001–SC-004 through public boundaries, then applicable migration/privacy and installed-host gates.
4. Record exact versions, commands, measurements, gaps and activation/rollback guidance; enable only supported capabilities.

## Verification strategy

Primary boundary suite: `tests/test_context_governance.py`. Add fixture-level golden inputs and assertions per requirement before implementation. Cross-interface golden tests verify scope, IDs, reason codes and state parity. A fake provider/host supports deterministic tests but does not establish live compatibility. Browser tasks require actual keyboard, viewport and navigation checks; human timing remains a separate controlled protocol.

- **SC-001**: Native, injected Mem0 and document-search fixtures produce the same envelope and pivots with zero implicit import; real supported SDK/host versions must pass before being advertised.
- **SC-002**: Cross-scope, destination-denied, changed-byte, expired-grant, replay and unavailable-attribute fixtures result in zero unauthorized delivery or provider query egress.
- **SC-003**: All three authority modes identify the actual content authorizer and AtMem checks through service, SDK/HTTP, MCP and dashboard projections. A proposal cannot authorize governed-external delivery; unregistered delegation, changed bytes, invalid binding, expiry and replay are rejected with no silent mode fallback. Legacy native/trusted-v1 fixtures preserve exact bytes and single-path behavior; withhold returns no context or false exposure.
- **SC-004**: Report policy-only and packaging overhead separately across 1,000 local synthetic requests; p95 <= 25 ms on documented hardware excluding provider/model execution. A miss is a failed target, not an omitted sample.

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

## Product-wide integration (FR-011, SC-005)

Implement FR-011 through `atmem/context/policy.py`, consuming Spec 012 space/membership and feedback contracts, 019 context authorization, 020 time/identity evidence and the owner mappings in `specs/product-requirements.md`. Allocate persisted changes through Spec 010; retain legacy scope behavior and keep new private/shared space behavior explicit. Domain code owns facts and permissions; UI and transports project the same result.

Add boundary fixtures in `tests/test_context_governance.py` for SC-005, including positive/negative scope access, concurrent membership changes and real-versus-unknown verification time. Report unsupported host/provider coverage rather than infer it. Existing OpenClaw APIs are adapter compatibility surfaces, not required core fields. The relevant tasks below gate this requirement; broader future features do not block M0's scoped profile.
