# Spec 041 Alignment with Context Engine V3

Spec 040 remains controlling. Spec 041 supplies an optional, bounded decision
component and cannot create a second formation, authority, storage, retrieval or
delivery system.

| Spec 041 boundary | Spec 040 authority | Integration rule |
| --- | --- | --- |
| Authorized model input | FR-002 governance shell; FR-022 tenancy | `ContextEngineService` authorizes source ranges and active candidates before a decision request is built. No store handle or unrestricted identifier is exposed. |
| Formation operation proposal | FR-005–FR-008 formation and reconciliation | Laya selects only from typed operation and opaque target IDs. Formation V3 reloads sources, validates support and decides the mutation. |
| Evidence support | FR-004, FR-006 immutable source and coverage | AtMem computes quotes, offsets, hashes and coverage. A model score never becomes evidence. |
| Retrieval usefulness | FR-009–FR-015 obligation-first retrieval | Laya may rank the already frozen candidate pool. It cannot nominate, expand or authorize candidates. Sufficiency and packing remain Spec 040 services. |
| Generative escalation | FR-008 optional intelligence; FR-023 observability | Escalation uses AtBot with minimal authorized evidence and explicit egress. Its result is another proposal through the same validator. |
| Profiles | FR-020, FR-033 profiles and rollback | `laya-formation` is an intelligence selection inside a qualified engine profile, not a new engine profile. Legacy, fast and navigate identities remain unchanged. |
| Receipts | FR-006, FR-023 coverage and observability | Decision receipts are additive children of Formation V2 evidence and distinguish proposal, fallback/escalation and authoritative disposition. |
| Compatibility | FR-021, FR-030, FR-034 | Existing CLI/MCP/host contracts remain unchanged. Optional fields use new versioned contracts and old profiles safely ignore them. |
| Benchmarks | FR-024–FR-029, FR-035–FR-047 | Benchmark adapters stay under `research/`/`benchmarks/`; product modules contain no case IDs, expected answers or benchmark-specific behavior. |

## Canonical sequence

1. Load scope and canonical generation through Spec 040.
2. Authorize exact source ranges and candidate IDs.
3. Serialize a bounded typed-decision request.
4. Validate Laya output as an untrusted proposal.
5. Reload the canonical generation and recheck scope, lifecycle and evidence.
6. Apply the existing deterministic admission/mutation path or emit review.
7. Record proposal and final disposition separately.

Deletion, exclusion, expiry, revocation or a generation race between steps 2 and
5 invalidates the proposal. No model-assisted path may retry with wider scope.

## Persisted-data story

No existing canonical row changes in Phase 1. Future decision receipts are
additive, versioned evidence. Activation state must be separately namespaced and
default absent; an older profile sees neither a new default nor a required
migration. Final upgrade evidence must use the published AtMem 2.3.8 wheel.
