# Feature Specification: Provider-Neutral Context Governance

**Feature directory**: `specs/019-provider-neutral-context-governance`
**Created**: 2026-09-09
**Status**: Specified; not implemented
**Input**: Unified memory, governance and investigation product direction; [roadmap](../product-roadmap.md).

## Overview

A developer starts with native memory, switches to Mem0 or a registered document provider without importing its data, and retains the same policy and exposure evidence.

Product moment: **Before the model call**. This feature extends the existing product; the shared identity, application service, canonical authority and invariant owners remain as declared in [integration ownership](../integration-ownership.md).

## Three explicit authority modes

| Mode | Provider responsibility | AtMem responsibility |
| --- | --- | --- |
| Native memory | AtMem's native provider retrieves candidates | Canonical admission, policy authorization, packaging, delivery controls and evidence |
| Governed external retrieval | External provider proposes context with provenance | Enterprise policy authorizes its use and delivery; provider claims alone do not authorize access |
| Trusted delegation | Registered provider authorizes an exact package | Delegation policy, binding, expiry, replay protection and delivery evidence; no implied independent content-policy authorization |

These are authority modes, not separate products or the three onboarding paths. They share inspectable context and execution references, but preserve who authorized content and which checks AtMem actually enforced. Selection is explicit; a failed governed request cannot silently fall back to trusted delegation. Native memory admission remains exclusively AtMem-owned. Existing signed delegated-v1 payloads remain unchanged; shared projections wrap or reference them without rewriting signed bytes.

## User scenarios and acceptance

### US1 — Complete the primary workflow (P1)

A developer starts with native memory, switches to Mem0 or a registered document provider without importing its data, and retains the same policy and exposure evidence.

**Independent test**: Execute the scoped synthetic primary journey through the public service and a supported host. Assert FR-001–FR-010 and SC-001–SC-004; record unavailable capabilities rather than infer them.

**Acceptance**: Given authenticated scope and configured capabilities, when the primary workflow runs, then its result identifies the exact decision/event evidence and preserves the claimed boundary.

### US2 — Understand a failure without overstating evidence (P1)

An operator receives a useful deterministic result when optional intelligence or a provider/host boundary is unavailable.

**Acceptance**: Given a denied, missing, stale, replayed or unavailable input, when the workflow executes, then its failure/coverage reason is explicit, no authority widens and no external outcome is invented.

### US3 — Adopt incrementally and retain history (P2)

An existing user enables this capability explicitly and retains native memory, trusted delegation, old receipts and host state.

**Acceptance**: Given pre-feature persisted state, when upgrade and rollback/recovery are exercised, then old evidence remains inspectable, no historical relationship is fabricated and disabled capabilities do not affect execution.

## Functional requirements

- **FR-001**: Define a versioned provider-neutral request/package/decision contract shared by native memory, governed-external retrieval and explicitly trusted delegation. Persist and expose the selected authority mode, content authorizer and delegation-policy decision separately; a common envelope MUST NOT imply identical content authorization. Provider capability is not permission to switch mode: changes require explicit operator configuration, and failure MUST NOT silently escalate to trusted delegation. Identity is derived from authenticated runtime scope; a model cannot choose another principal or task.
- **FR-002**: Implement a native provider adapter that calls current admission/retrieval/revalidation without duplicating canonical storage; external providers retain their own stores and rankers. Retrieval never implicitly imports or remembers content.
- **FR-003**: Authorize destination and minimum necessary query/attributes before outbound provider access; record allowed/denied request egress separately from returned-content authorization. Missing required purpose or access attributes withhold rather than broaden access.
- **FR-004**: In governed-external mode, distinguish provider proposals from AtMem enterprise-policy authorization. Attribute every source/access/sensitivity claim as source-authoritative, operator-confirmed, model-inferred or unknown; only configured trusted attributes can satisfy access rules.
- **FR-005**: Package provider/source versions, scope, purpose, destination, expiry, generation, content digest and bounded provenance; distinguish prepared, authorized, returned-to-host, observed-exposed and enforced states. No receipt proves model understanding.
- **FR-006**: Preserve the closed trusted-delegation v1 wire format and provider exact bytes. The registered provider authorizes that exact package; AtMem enforces delegation policy, scope/destination binding, expiry, replay protection and delivery evidence, without claiming independent content-policy authorization. An invalid delegation withholds context. Redaction or composition produces a new package with ordered parent digests, transformation version and authorization; never claim the provider signed transformed content.
- **FR-007**: Issue an expiring delivery grant bound to package digest, policy generation, authenticated scope, execution/turn/model-call identity when available and destination. Supported adapters validate at dispatch, reject mismatch/expiry/replay and record exposure separately. Tool-only clients cannot claim this enforcement.
- **FR-008**: Negotiate provider capabilities for source versions, access attributes, deletion, freshness and health. Unsupported fields remain explicit and cannot satisfy required policy; a provider switch alone changes no canonical memory.
- **FR-009**: Keep legacy native APIs and disabled delegation compatible; begin new integrations non-influencing and activate explicitly. Native deterministic operation and incident evidence require no hosted model or provider SDK.
- **FR-010**: Expose shared context and decision resources through Spec 012 services. Deliver one-provider parity first, then explicitly configured native-plus-document composition for the cross-domain milestone: preserve ordered source segments, bound bytes, withhold when any required segment is denied/missing/over budget, and expose optional omissions and conflicting source claims without silently resolving them. Never combine trusted v1 authority with native retrieval.

## Key entities

- **ProviderCapabilities**: Provider ID/version, supported contract/mode, source-version/access/freshness/deletion support, health, configured scope and attribute trust basis.
- **ContextRequest**: Authenticated principal/scope, query, permitted provider/destination, declared purpose, byte/deadline budget, optional execution/task references and policy generation.
- **ContextPackage**: Package ID/version, provider-qualified source versions, ordered segments, digest/byte length, expiry, source generations, omissions and parent transformation references.
- **SourceClaim**: Source reference/version, claim kind, asserted value, origin assurance and authoritative attester; unknown attributes stay unknown.
- **PolicyDecision**: Decision ID, allow/withhold, policy version/generation, evaluated scope/destination/purpose, reason codes and package/request digest.
- **TransformationReceipt**: Parent package digests, transformation type/version, ordered output digest, omissions and independent authorization reference.
- **DeliveryGrant**: Grant ID, package digest, principal/scope, destination, model-call/turn binding, policy/source generation, expiry and one-use/replay state.

## Success criteria

- **SC-001**: Native, injected Mem0 and document-search fixtures produce the same envelope and pivots with zero implicit import; real supported SDK/host versions must pass before being advertised.
- **SC-002**: Cross-scope, destination-denied, changed-byte, expired-grant, replay and unavailable-attribute fixtures result in zero unauthorized delivery or provider query egress.
- **SC-003**: All three authority modes identify the actual content authorizer and AtMem checks through service, SDK/HTTP, MCP and dashboard projections. A proposal cannot authorize governed-external delivery; unregistered delegation, changed bytes, invalid binding, expiry and replay are rejected with no silent mode fallback. Legacy native/trusted-v1 fixtures preserve exact bytes and single-path behavior; withhold returns no context or false exposure.
- **SC-004**: Report policy-only and packaging overhead separately across 1,000 local synthetic requests; p95 <= 25 ms on documented hardware excluding provider/model execution. A miss is a failed target, not an omitted sample.

## Failure and edge cases

Missing identity, inaccessible parent/reference, duplicate or conflicting delivery, timeout after external dispatch, stale generation, late evidence, deleted source, unavailable provider/model, process restart, cancellation and scope changes must have explicit bounded outcomes. Authorization covers joins, explanations, totals and exports. A source reference or signature does not establish semantic truth. Where a boundary is unsupported, report it rather than emulate a stronger guarantee.

## Dependencies and ownership

Baseline 003, 004, 008, 012 and 018. Reuse 007 ExecutionIdentity once its contract task T088 lands; optional execution references remain absent for memory-only use.

The dependency list distinguishes existing baseline modules from new contract milestones. Feature-specific assertions feed Spec 018; Spec 018's existing registry is a baseline prerequisite, not a cycle requiring future consumer code before its contracts exist.

## Compatibility, privacy and migration

Keep Python 3.10–3.13, optional provider/model/framework imports, local operation, explicit activation and egress, unchanged host-owned state and distinct canonical memory/task/evidence authorities. Closed wire schemas get new versions when needed; additive fields require negotiation. Allocate migrations through existing registries, retain legacy projections, test supported published floors, and never fabricate historical links. No default raw transcript, chain-of-thought or secret retention. Evidence metadata and hashes still require access control and retention.

## Out of scope

Replacing external memory stores, general model routing, automatic provider setup, or attributing semantic causation from context presence.

## Invariant Attestation

Touches INV-001, INV-002, INV-003, INV-004, INV-005, INV-008, INV-010, INV-011 through `spec019.scope`, `spec019.evidence`, `spec019.compatibility` and `spec019.failure`. These are planned assertion identifiers, not claims of executing tests. They become proven only when boundary tests and installed-artifact evidence exist.
