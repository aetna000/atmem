# Product-wide requirements: agent neutrality, shared memory and clear evidence

**Status**: Required product behavior; implementation and claims require the acceptance evidence below.
**Applies to**: Specs 001–025, all public interfaces and every advertised deployment/adapter profile.

AtMem is an agent- and framework-neutral memory, context-governance and investigation product. It supports multiple agents using separate or explicitly shared memory, replaceable context providers, and understandable evidence about their work. OpenClaw is an initial delivered/tested integration; its identifiers and configuration do not define the core product.

## Binding product requirements

- **PR-001 — Agent neutrality**: Core identity, memory, context, policy, execution and feedback contracts MUST work without OpenClaw imports, identifiers or configuration. Host-specific mapping stays in adapters. Generic API/MCP clients can use applicable capabilities; automatic capture/enforcement is advertised only for tested host profiles. Framework and human-readable agent names are descriptive metadata, never authority.
- **PR-002 — Multiple agents**: Every operation identifies the authenticated actor and acting agent, tenant/workspace and relevant subject scope. Multiple agents may run concurrently and participate in one explicitly linked execution. Parent/child or collaboration links do not implicitly confer memory access. Agent identity collisions across hosts or tenants do not merge agents or histories. Agent names and host type are visible without requiring UUID correlation.
- **PR-003 — Private and shared memory**: New memory spaces default to private unless an authorized operator explicitly selects a shared space. A space has an owner, immutable identity, tenant/workspace boundary, versioned membership and separate read, write/propose and administration permissions. Agents may access their private space and several permitted shared spaces concurrently. Membership alone does not override subject/source/destination policy. Existing scopes retain their established behavior on upgrade and are labelled legacy where new metadata is unavailable; no automatic privatization, sharing, import or reclassification occurs.
- **PR-004 — Safe, traceable context**: Native and external providers use the same scoped request/package/evidence services while preserving their different authority modes. Record contributor/source version, producing and consuming agent where known, permitted space, policy/membership generation, content authorizer and delivery assurance. Authenticate and authorize before query egress, then revalidate use/delivery at the supported boundary. Shared-space membership does not authorize an external account's entire corpus. Unknown external access attributes cannot satisfy required access rules.
- **PR-005 — Explanatory feedback**: Every status/alert/detail view MUST say what happened, to which accessible agent/resource, when, what evidence supports it, what effect is known or unknown, and the permitted next action or why none is available. Use readable reason text alongside stable machine codes. Red/yellow/green, icons and isolated error codes cannot be the complete explanation. Distinguish authentication health, authorization, delivery, execution outcome, review, remediation and verification. Denied views explain the access limitation without revealing inaccessible names or existence.
- **PR-006 — Time and freshness clarity**: Show absolute event time with explicit timezone/offset and elapsed time where calculable. Keep source event time, AtMem receive time, evaluation/check time, expiry and last successful verification distinct. Display evidence age and freshness criteria for health/authentication/policy claims. A refresh request updates the display only; it cannot renew a verification timestamp. Missing time is unknown, not zero or now. Late arrival and skew are labelled; cross-producer ordering is based on known dependencies/sequence, never invented from clocks. Relative labels supplement absolute timestamps.

## Memory-space rules

Spec 012 owns the shared authenticated space/membership service contract and authorization projection, with persistence allocated through Spec 010. Spec 006 owns canonical admission; 019 owns provider retrieval/package authorization; 015 owns invalidation; 022/025 present the same state. These are additions to the existing scope authority, not a second memory store.

Membership changes require scoped permission, expected revision, audit actor/time/reason and idempotency. Read access never implies write, approve, share or administer. Writes/proposals select one authorized destination space explicitly; retrieval can read several permitted spaces and keeps per-source provenance. Duplicate or conflicting assertions from different spaces remain attributable and must not silently overwrite one another. A share action requires a preview and explicit authorization; moving/copying content keeps lineage and applicable restrictions.

Removing a member invalidates future access and affected controlled cached/prepared context. Dispatch checks current membership/policy at supported enforcement boundaries. Show in-flight or disconnected uncertainty and which external consumers remain uncontrolled. Prior disclosures are not retractable; historical audit visibility requires separate permission. Memory sharing does not automatically share execution logs, provider credentials, incident narratives or administrative privileges.

## Feedback and time contract

Spec 012 owns the transport-neutral feedback shape; 020 owns event/receive timestamps and ordering; each domain service owns its reason, state and verification facts; 021 owns findings and advice; 022 owns shared rendering. Required fields are a reason code, readable summary, accessible resource references, assurance, known effect/uncertainty, applicable timestamps with provenance, evidence references, and allowed next action or absence reason. Fields with unavailable evidence remain explicitly unknown. No explanation requires a model service.

A compact card can read: **Context withheld · 14:32:08 +10:00**; **Research agent · Team knowledge**; “The selected model destination is denied by the workspace policy. Delivery was blocked at dispatch.” Follow with the policy/evidence link, the check time and an allowed action. The wording must instead say “returned to host; dispatch not observed” when only that weaker evidence exists. Healthy cards identify the successful check and its age as clearly as failing cards identify an error.

## Acceptance matrix and ownership

| Owner | Required evidence |
| --- | --- |
| 001 | Cross-product fixtures for two collaborating agents plus an unauthorized third, private/shared spaces, provider parity and explanatory time-aware feedback |
| 006 | Authorized private/shared admission with contributor and destination provenance; read-only members cannot write or promote |
| 011 | Framework-neutral harness and two distinct real host profiles before advertising cross-framework shared-memory support; M0 single-host coverage stays explicit |
| 012 | One persisted space/membership and feedback contract across SDK, HTTP, MCP, CLI and dashboard; scoped counts, exports and joins |
| 015 | Membership-revocation races, source changes, prepared-context/cache invalidation and honest remaining exposure |
| 017 | Onboarding selects agents and private/shared spaces by readable names; existing memory and investigation-only profiles require no migration |
| 019 | Native and external retrieval enforce space/source/purpose/destination policies and preserve contributor/consumer attribution |
| 020 | Concurrent agent identities, explicit cooperation links, event/receive time, skew, late events, missing clocks and current coverage |
| 021 | Evidence-linked effects/uncertainty and permitted next actions for success, failure, recovered and incomplete runs |
| 022 | Consistent agent/space context, accessible status explanations and timestamp/freshness rendering across all sections |
| 025 | Connection access preview and monitoring reflect agent membership, authority mode, credential health and actual verification age |

Test cases include agents with the same display name in different hosts, a child without inherited membership, authorized shared reads, denied writes, concurrent member removal during delivery, private memory excluded from a shared query, stale credentials, denied destinations, absent verification times, daylight-saving/timezone changes, delayed events and unknown external outcomes. Require zero cross-scope exposure or fabricated effect/time claims. Core tests run without OpenClaw installed. Published host coverage and the two-cohort usability protocol remain distinct gates.

## Release applicability

M0 implements the applicable neutral identities, multi-agent capture when supplied, feedback and timestamp requirements in the existing dashboard. It does not advertise shared-memory functionality before its membership/admission/retrieval gates pass. M1 includes private/shared memory across the common services; additional real host profiles are required before broader interoperability claims. This document does not add the entire M1 backlog as an M0 prerequisite. Every release names implemented and unsupported capability profiles.

Requirement ownership is binding across the specs below. Existing requirement and task IDs remain stable; feature-specific amendments add implementation/verification work. This specification pass is not evidence that the runtime capabilities are implemented.

## Requirement and task traceability

| Feature | Added requirement | Acceptance | Implementation/verification tasks |
| --- | --- | --- | --- |
| [001](001-memory-quality-benchmarks/spec.md) | FR-021 | SC-010 | T033, T034, T035 |
| [006](006-memory-extraction-and-updating/spec.md) | FR-014 | SC-006 | T013, T014, T015 |
| [011](011-framework-adapter-conformance/spec.md) | FR-017 | SC-009 | T017, T018, T019 |
| [012](012-http-api-and-typescript-sdk/spec.md) | FR-015 | SC-007 | T013 fixtures; T016–T032 subsystem; T014 roll-up; T015 final acceptance |
| [015](015-memory-lifecycle-controls/spec.md) | FR-013 | SC-006 | T012, T013, T014 |
| [017](017-guided-onboarding-and-health/spec.md) | FR-012 | SC-007 | T013, T014, T015 |
| [019](019-provider-neutral-context-governance/spec.md) | FR-011 | SC-005 | T018, T019, T020 |
| [020](020-durable-execution-evidence/spec.md) | FR-011 | SC-005 | T023, T024, T025 |
| [021](021-incident-investigation-and-resolution/spec.md) | FR-011 | SC-005 | T021, T022, T023 |
| [022](022-unified-agent-workspace/spec.md) | FR-011 | SC-005 | T018, T019, T020 |
| [025](025-enterprise-provider-connections/spec.md) | FR-019 | SC-009 | T021–T023 (full wizard: T001–T023) |

Contract order: freeze 012 membership/feedback fields first, then integrate 006/015/019 and downstream views. 020 identity/time facts can develop independently; 021/022/025 consume stable projections. 001 validates the combined behavior. Dependencies are on those named contracts, not completion of all features. M0 continues through its independent scoped task sequence.
