# Product-wide requirements: agent neutrality, standalone full-fidelity evidence and encrypted privileged access

**Status**: Required product behavior; implementation and claims require the acceptance evidence below.
**Applies to**: Specs 001–028, all public interfaces and every advertised deployment/adapter profile.

AtMem is an agent- and framework-neutral memory, context-governance and investigation product. It supports multiple agents using separate or explicitly shared memory, replaceable context providers, and understandable evidence about their work. OpenClaw is an initial delivered/tested integration; its identifiers and configuration do not define the core product.

## Binding product requirements

- **PR-001 — Agent neutrality**: Core identity, memory, context, policy, execution and feedback contracts MUST work without OpenClaw imports, identifiers or configuration. Host-specific mapping stays in adapters. Generic API/MCP clients can use applicable capabilities; automatic capture/enforcement is advertised only for tested host profiles. Framework and human-readable agent names are descriptive metadata, never authority.
- **PR-002 — Multiple agents**: Every operation identifies the authenticated actor and acting agent, tenant/workspace and relevant subject scope. Multiple agents may run concurrently and participate in one explicitly linked execution. Parent/child or collaboration links do not implicitly confer memory access. Agent identity collisions across hosts or tenants do not merge agents or histories. Agent names and host type are visible without requiring UUID correlation.
- **PR-003 — Private and shared memory**: New memory spaces default to private unless an authorized operator explicitly selects a shared space. A space has an owner, immutable identity, tenant/workspace boundary, versioned membership and separate read, write/propose and administration permissions. Agents may access their private space and several permitted shared spaces concurrently. Membership alone does not override subject/source/destination policy. Existing scopes retain their established behavior on upgrade and are labelled legacy where new metadata is unavailable; no automatic privatization, sharing, import or reclassification occurs.
- **PR-004 — Safe, traceable context**: Native and external providers use the same scoped request/package/evidence services while preserving their different authority modes. Record contributor/source version, producing and consuming agent where known, permitted space, policy/membership generation, content authorizer and delivery assurance. Authenticate and authorize before query egress, then revalidate use/delivery at the supported boundary. Shared-space membership does not authorize an external account's entire corpus. Unknown external access attributes cannot satisfy required access rules.
- **PR-005 — Explanatory feedback**: Every status/alert/detail view MUST say what happened, to which accessible agent/resource, when, what evidence supports it, what effect is known or unknown, and the permitted next action or why none is available. Use readable reason text alongside stable machine codes. Red/yellow/green, icons and isolated error codes cannot be the complete explanation. Distinguish authentication health, authorization, delivery, execution outcome, review, remediation and verification. Denied views explain the access limitation without revealing inaccessible names or existence.
- **PR-006 — Time and freshness clarity**: Show absolute event time with explicit timezone/offset and elapsed time where calculable. Keep source event time, AtMem receive time, evaluation/check time, expiry and last successful verification distinct. Display evidence age and freshness criteria for health/authentication/policy claims. A refresh request updates the display only; it cannot renew a verification timestamp. Missing time is unknown, not zero or now. Late arrival and skew are labelled; cross-producer ordering is based on known dependencies/sequence, never invented from clocks. Relative labels supplement absolute timestamps.
- **PR-007 — Standalone full-fidelity transparency and replay evidence**: AtMem is the independent evidence system of record, not an index into agent logs. Full-fidelity standalone capture is the default. Given only a supported AtMem evidence-store backup and the AtMem software, an owner or explicitly authorized investigator MUST recover the exact user prompt, system/model input, memory state and records used, context delivered, governance decisions, model output, tool name and call ID, exact arguments and target including URLs, paths and commands, exact result or error, timing, ordering, retries and observed effects. The evidence model is natively multimodal at every boundary and retains ordered text, links and fetched pages, files, images/screenshots, audio and video with original bytes, MIME type, timing and source linkage. A digest, caption, transcript, thumbnail, count, generic error, external pointer or opaque ID MUST NOT replace available evidence. Reconstruction MUST work after the agent is dead and its logs, workspace, original memory store, provider database and caches are deleted. Every view starts with a readable account of what was attempted and what failed, then renders or downloads the exact evidence without manual ID correlation. When the tool contract and captured state permit replay, emit a deterministic replay manifest; simulation/reconstruction is distinct from a newly authorized real execution. Credentials unrelated to the user's instruction use protected references or reversible protection, not destructive removal of the surrounding call. Access, export, replay and deletion are themselves audited. A user MAY explicitly disable capture or select metadata-only mode, but AtMem MUST audit that choice and label affected runs `not_reconstructable`; reduced capture MUST NOT be presented as complete Black Box evidence. Legacy hash-only events remain visible as `hash_only_legacy` and `not_reconstructable`.
- **PR-008 — Encrypted evidence and privileged plaintext**: Every durable evidence object and semantic metadata field—including envelopes, identities, scopes, timestamps, indexes, audit, spool, temporary durable data, backups, exports and original/derived text, link/page, file, image, audio and video artifacts—MUST be encrypted at rest. Direct storage inspection yields no session plaintext; only an authenticated AtMem application may decrypt or render exact content after scope/operation authorization and key release. The minimum hierarchy is Level 1 Viewer, Level 2 Investigator and Level 3 Evidence Collector; submitters and key custodians gain no read privilege automatically. Only a Level 3 Evidence Collector may export plaintext, after reauthorization and explicit confirmation; Level 2 may create recipient-encrypted exports. The supported full-fidelity profile uses a versioned quantum-resistant suite, initially AES-256-GCM for content, ML-KEM-768 or stronger for portable recipient wrapping and ML-DSA-65 or stronger for export/recovery manifests, with algorithm agility and downgrade rejection. The concise Evidence protection setting defaults `Data` on, encrypting exact text, link/page, file, image, audio and video data plus metadata; switching `Data` off retains encrypted metadata and marks runs `not_reconstructable`. A separate Recorder control stores nothing. AtMem MUST NOT silently store plaintext or describe metadata-only, disabled or unencrypted capture as a supported Black Box.

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
| 020 | Concurrent identities/time plus full-fidelity text, memory, decision, model, tool and multimodal capture; crash-safe standalone persistence; reconstruction manifests; legacy hash-only classification; exact boundary round trips |
| 021 | Evidence-linked effects/uncertainty, complete call narratives and permitted next actions for success, failure, recovered and incomplete runs |
| 022 | Consistent agent/space context, accessible status explanations, full evidence disclosure and timestamp/freshness rendering across all sections |
| 025 | Connection access preview and monitoring reflect agent membership, authority mode, credential health and actual verification age |
| 028 | Stolen-store secrecy, application-only decryption, three-level privilege enforcement, post-quantum recipient protection, rotation/recovery, encrypted backup/export and compact protection settings |

Test cases include agents with the same display name in different hosts, a child without inherited membership, authorized shared reads, denied writes, concurrent member removal during delivery, private memory excluded from a shared query, stale credentials, denied destinations, absent verification times, daylight-saving/timezone changes, delayed events and unknown external outcomes. They also include exact prompt/tool/URL/command/result/error round trips, agent death after capture, crash recovery, authorized disclosure, denied disclosure, replay-manifest determinism, audited access and legacy hash-only evidence. Require zero cross-scope exposure, zero fabricated effect/time claims and zero hash substitution where full-fidelity capture is advertised. Core tests run without OpenClaw installed. Published host coverage and the two-cohort usability protocol remain distinct gates.

## Release applicability

M0 requires the applicable neutral identities, multi-agent capture when supplied, standalone full-fidelity evidence, feedback and timestamp behavior through the evidence-specific workspace. These capabilities remain unimplemented until their named tasks and gates pass. M0 does not advertise shared-memory functionality before its membership/admission/retrieval gates pass. M1 includes private/shared memory across the common services; additional real host profiles are required before broader interoperability claims. This document does not add the entire M1 backlog as an M0 prerequisite. Every release names implemented and unsupported capability profiles.

Requirement ownership is binding across the specs below. PR-007 supersedes content-minimizing or hash-only requirements in feature specs wherever they would discard execution evidence needed for reconstruction. Existing requirement and task IDs remain stable; feature-specific amendments add implementation/verification work. This specification pass is not evidence that the runtime capabilities are implemented.

## Requirement and task traceability

| Feature | Added requirement | Acceptance | Implementation/verification tasks |
| --- | --- | --- | --- |
| [001](001-memory-quality-benchmarks/spec.md) | FR-021 | SC-010 | T033, T034, T035 |
| [003](003-delegated-context-provider/spec.md) | FR-038–FR-042 | SC-017–SC-018 | T054–T058 |
| [006](006-memory-extraction-and-updating/spec.md) | FR-014 | SC-006 | T013, T014, T015 |
| [011](011-framework-adapter-conformance/spec.md) | FR-017 | SC-009 | T017, T018, T019 |
| [012](012-http-api-and-typescript-sdk/spec.md) | FR-015 | SC-007 | T013 fixtures; T016–T032 subsystem; T014 roll-up; T015 final acceptance |
| [015](015-memory-lifecycle-controls/spec.md) | FR-013 | SC-006 | T012, T013, T014 |
| [017](017-guided-onboarding-and-health/spec.md) | FR-012 | SC-007 | T013, T014, T015 |
| [019](019-provider-neutral-context-governance/spec.md) | FR-011 | SC-005 | T018, T019, T020 |
| [020](020-durable-execution-evidence/spec.md) | FR-011, FR-024–FR-031 | SC-005, SC-011–SC-015 | T023–T025, T042–T053 |
| [021](021-incident-investigation-and-resolution/spec.md) | FR-011–FR-015 | SC-005–SC-007 | T021–T023, T025–T028 |
| [022](022-unified-agent-workspace/spec.md) | FR-011, FR-019–FR-022 | SC-005, SC-008–SC-009 | T018–T020, T026–T029 |
| [025](025-enterprise-provider-connections/spec.md) | FR-019 | SC-009 | T021–T023 (full wizard: T001–T023) |
| [026](026-temporal-memory-consolidation/spec.md) | FR-016 | SC-006–SC-007 | T014–T015, T020–T027 (full feature: T001–T027) |
| [027](027-model-unlearning-orchestration/spec.md) | FR-017–FR-018 | SC-001–SC-003, SC-008 | T001–T009, T014–T017, T025–T030 (full preview: T001–T030) |
| [028](028-encrypted-evidence-and-privileged-access/spec.md) | FR-001–FR-017 | SC-001–SC-010 | T001–T009 source slice implemented; T010–T012 acceptance remains release-blocking |

Contract order for the standalone Black Box is 020 full-fidelity envelope/artifact contracts plus 028 encrypted container/privilege contracts, then encrypted persistence, 021 reconstruction, 022 rendering and the encrypted dead-agent installed-artifact gate. Membership/feedback work in 012 and 006/015/019 integration can proceed independently where it does not weaken this evidence path. Spec 026 consumes those foundations in staged releases; Spec 027 additionally waits for 023 revocation and 024 model/deployment inventory before its preview. 001 validates combined memory quality, 020 owns evidence completeness, and 028 owns at-rest confidentiality and plaintext authorization.

## PR-007 cross-spec supersession matrix

The following is binding even where an older feature document still describes
content-free, redacted-only or digest-only evidence. Minimal public telemetry and
synthetic CI summaries are allowed; the canonical authorized evidence store is
not minimal telemetry.

| Owner | Required full-fidelity contribution |
| --- | --- |
| 002 retrieval/ranking | Exact query, eligible candidates, selected memory content, scores/reasons and final ordering used for the run |
| 003 delegated context | Exact provider request/query, returned context, authority decision, signatures and delivered bytes; content-free delivery rows may remain indexes only |
| 004 adapters | Exact provider request/result/context and original multimodal artifacts at every supported capture boundary |
| 006/008/015/026 memory lifecycle | Exact memory version/state used, extraction/consolidation proposal and decision; later mutation or deletion does not rewrite historical run evidence |
| 007 governed tasks | Exact task context, observed tool input/result and decision delta associated with the run; content-minimized projections may remain secondary indexes |
| 011 host conformance | Boundary manifest declares whether exact text, image, audio, video, file, link, model and tool content is captured; metadata-only boundaries cannot pass Black Box conformance |
| 012 public contracts | Versioned ordered multimodal evidence parts, artifact transfer/download and completeness fields are available consistently across HTTP, SDK and MCP |
| 016 multimodal memory | Original captured image/audio/video/file/link bytes and exact delivered representation remain available in run evidence; captions/transcripts are supplemental |
| 018 invariants | CI output stays synthetic and credential-free, while tests assert production evidence retains exact synthetic fixture content byte-for-byte |
| 019 providers | Exact authorization inputs, policy version, candidate/context package and delivery decision are snapshotted into run evidence |
| 020 execution evidence | Owns the canonical envelope/artifact store, crash durability, reconstruction, replay manifests and dead-agent disaster gate |
| 021 incidents | Produces concrete store-only prompt-to-outcome explanations and never directs users to destroyed agents/logs |
| 022 workspace | Renders/downloads exact content and media first; counts, IDs and hashes are supporting proof |
| 023/024/025/027 operations | Exact policy, connection, fleet, revocation and unlearning actions/results/artifacts required to reconstruct an affected run or administrative execution |
| 028 encrypted evidence | Encrypts the canonical evidence, semantic metadata, derivatives, audit, backups and exports; owns three-level plaintext privileges, key lifecycle, quantum-safe recipient protection and compact Evidence protection settings |

## Global standalone evidence acceptance gate

One independently authored campaign MUST:

1. Run text, image, audio, video, file and fetched-link inputs through native
   memory, one external provider and no-memory investigation profiles.
2. Exercise allowed/withheld context, policy decisions, model input/output,
   read-only tools, shell/file tools, network tools, a side-effecting tool,
   success, failure, timeout, retry, child agent and crash during capture.
3. Record exact expected prompts, memory versions/content, contexts, decisions,
   tool arguments/targets, results/errors, media bytes and known outcomes outside
   AtMem as the test oracle.
4. Stop and remove the fixture agents; delete their logs, workspaces, caches,
   original memory/provider stores and model/tool fixtures; deny network access.
5. Copy only the encrypted AtMem evidence store into a fresh installed process;
   prove direct inspection reveals none of the planted content or semantic
   metadata, then authorize AtMem/key recovery and compare every reconstructed
   field and artifact byte-for-byte with the oracle.
6. Generate the same inert replay manifest twice and prove it causes no external
   effect. A separately authorized re-execution must create a new linked run.
7. Exhaust the Spec 028 submitter, Viewer, Investigator, Evidence Collector, key-custodian and
   unrelated-principal matrix; audit reveal/export/replay/rotation/deletion and
   verify plaintext is emitted only by authorized AtMem operations.
8. Repeat with explicit metadata-only/off and legacy evidence; require visible
   `not_reconstructable` and exact missing-boundary explanations.

The gate fails if any supported full-fidelity run requires the original agent or
logs, if any original multimodal artifact is replaced by derived text/metadata,
or if any UI/API answer uses only a count, digest, opaque ID or generic statement
when exact evidence was captured.
