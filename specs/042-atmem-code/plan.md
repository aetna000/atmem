# AtMem Code implementation plan

**Status:** High-level plan; dependency-ordered work is in [tasks.md](tasks.md), pending SpecKit analysis and qualification. The release candidate version is not selected.
**Inputs:** [spec.md](spec.md), [market-research.md](market-research.md), AtMem Constitution, published 2.3.8 source.

## Technical context

AtMem is a Python 3.10–3.13 package with SQLite canonical memory, derived vector/graph surfaces, MCP and HTTP interfaces, a local dashboard, generic host control, OpenClaw and framework adapters, and a delegated context-provider contract with a Mem0 adapter. The default installation pins AtBot and AtFlows. AtMem Code remains in this repository with optional host packages and parser dependencies. Muse Code, Claude Code, Grok CLI, GitHub Copilot CLI, and Codex are named host-adapter targets. Their hook packaging and context-delivery behavior must be validated against pinned versions; none is assumed to expose identical events or injection boundaries. Copilot editor and cloud agent are separate targets, not implied by Copilot CLI support.

## Architecture

1. **One AtMem package and contract.** Code is an onboarding/installation flavour of the existing package and canonical service. Introduce versioned `code_observation`, `code_memory_candidate`, `code_context_request`, `code_context_package`, `code_exposure`, and deletion receipts. Events carry stable project/profile/agent/user/session identities, source digests and Git revision. The core service is host-neutral.
2. **Host adapters.** Define a host adapter interface for capability declaration, installation/restore, authenticated event intake, context submission, acknowledgement and health probing. Package separate assets for Muse Code, Claude Code, Grok CLI, GitHub Copilot CLI, and Codex; each invokes one local AtMem Code service where its verified events permit. Installation alone is non-influencing. Installers snapshot prior host configuration, provide a preview, explicitly enable only user-selected hosts, run real hook probes, and restore on failure or explicit uninstall. Disable only pauses automatic capture and context injection, leaving the hook and memory intact; enable resumes them. Enabled adapters operate immediately; there is no shadow mode. An MCP server supplies explicit search/remember commands for hosts without a verified automatic path.
3. **Capture and formation.** Capture bounded user/task/test/change evidence without making a transcript dump into canonical memory. Queue idempotent candidates; run pre-write secret screening on the complete intake and every derived field. Use deterministic formation first, with source evidence and time-valid correction. Store only accepted canonical memories. Secret-bearing original bytes required for full-fidelity evidence go only into reversibly protected encrypted fields; no plaintext secret enters ordinary storage or egress. Advanced model extraction may be added only as an optional proposal source.
4. **Shared identity.** Derive a stable repository identifier from canonical remote identity when available, with a persisted local UUID for unremoted repositories. Bind all reads and writes to authenticated user, project, profile and agent scopes. Sharing among agents uses one authorized local service; cross-machine use is explicit export/import rather than live sync. A remote URL or hash alone does not authorize sharing.
5. **Retrieval and injection.** At task start, route the typed request, retrieve current authorized memories, optionally nominate graph slices, pack to a token/byte budget and return source-linked context. The host adapter submits at its documented boundary and records exact bytes/digest, any host acknowledgement, and independently observed model input only if that observation is available. During task work, explicit MCP search can retrieve more. Missing hooks or delivery confirmation produce degraded receipts rather than an unearned model-exposure claim.
6. **Optional code graph.** Build a derived SQLite-backed code index from eligible files using an optional parser. Begin with definitions, imports and references; add call and route edges only where language-specific resolution is supported. Index by content digest and Git revision, invalidate on edits/branch change, and expose bounded structural queries. Unsupported languages use file/symbol search; no fabricated edges.
7. **Tagged provider routing.** Extend the existing signed delegated-context machinery with a versioned provider contract and deterministic tag-to-route table. Each route has allowlisted tags, scopes, provider identity and credential reference, egress policy, request/response schema, time/byte budget and fallback. Authorize and screen the outbound query before egress. A `delegated-context` route may ask the provider instead of local memory; the returned content is attributed, validated and labelled delegated, not independently fact-verified or silently promoted to canonical AtMem state.
8. **CLI and dashboard.** Extend the existing dashboard with a Coding Memory view and mirror its supported controls in CLI. Search and filter canonical memories; show source, scope, validity and delivered-context history where available. Host, scope, provider, budget and review-workflow settings are readable and changeable from both surfaces. Bulk clear uses an exact preview token and verifies local derived deletion and registered provider outcomes. Optional review UI may be off; core enforcement and required receipts remain.
9. **Portable project bundle.** Build on AtMem Home restore, but scope an export to one project with a versioned encrypted manifest, canonical state, lifecycle and evidence. Verify integrity and authorization before import; preview identity collisions; rebind a clone only on explicit approval. Rebuild vector/graph indexes from canonical state. Exclude machine-bound credentials and host-hook configuration, then run search-parity and cross-scope tests on a fresh install.

## Delivery sequence and gates

| Phase | Deliverable | Required gate |
| --- | --- | --- |
| 0 | VibeMemBench protocol, unfiltered real-issue control and five-host capability matrix | Pin primary sources, corpus license/revision and task IDs, chronological histories, host/model versions, event/injection surfaces, supported operating systems and baselines before automatic or performance claims |
| 1 | Secret-safe intake foundation | Reproduce and close the 2.3.8 raw-episode and interpreted-fact bypasses; test persistent and outbound surfaces |
| 2 | Host-neutral code contracts and scoped storage | Idempotency, migration, cross-scope isolation, exact deletion and 2.3.8 compatibility tests |
| 3 | Muse Code, Claude Code, Grok CLI, GitHub Copilot CLI and Codex adapters with guided installer | Installation is non-influencing; explicit enablement starts active operation with no shadow period; each claimed host/OS combination passes fresh install, existing-config preservation, hook probe, boundary-level delivery evidence and rollback; unqualified cells are labelled manual or unavailable |
| 4 | Automatic capture, formation and recall | Cross-session and cross-agent task replay; no manual tool call required for claimed automatic path; bounded latency and context |
| 5 | Coding dashboard and clear operations | Search, source inspection, exact preview, scoped deletion, partial external failure reporting |
| 6 | Tagged native/RAG/Mem0 routes | Authorized routing, no unintended egress, provider failure/fallback and delivery receipts |
| 7 | Optional code graph | Incremental freshness, symbol/call accuracy by supported language, branch invalidation, map and file-search baseline comparison |
| 8 | Portable project bundle and CLI/dashboard parity | Fresh-install encrypted bundle round trip, explicit project rebinding, index rebuild, cross-scope isolation and configuration parity |
| 9 | Paired VibeMemBench and unfiltered real-task evaluation, then release | Freeze retrieval/settings and task splits before scoring; compare complete agent runs under matched histories, models and budgets; report executable quality, tokens, p50/p95 latency, cost, leakage, safety, uncertainty, installed-artifact and coordinated release gates |

All phases 0–8 are in this development request. Graph and external routing remain opt-in for users, not omitted from implementation. Phase 9 benchmark and release work is deferred by the owner's later instruction; required unit and integration verification still applies throughout phases 0–8. The `v2.3.9b1` Laya tag is historical and immutable; any future AtMem Code release candidate receives a distinct version selected during separate release preparation.

## Design decisions and risks

- **Governance switch:** The user can disable optional review queues and approval workflow in the Code experience. Full-fidelity capture remains the default supported evidence profile; reduced capture requires an explicit, recorded `not_reconstructable` choice. Core authorization, scope, provenance, encryption, secret screening, lifecycle, deletion verification and required audit cannot be disabled under the constitution. A genuine zero-governance mode would require a constitutional/product-contract change before specification.
- **Full-fidelity boundary:** The first coding adapters may verify memory capture and context delivery without covering every model/tool/media boundary. Status and release notes must say so. They cannot inherit the OpenClaw full Agent Black Box claim.
- **Secret detection:** Pattern and entropy checks are fallible. A bounded fixture set is necessary but insufficient; staged egress must also be inspectable and controlled. The default remains local with no provider egress.
- **Graph freshness:** Derived edges can be incomplete or stale. Every graph answer includes its indexed revision and exact source references; exact code behavior requires source inspection.
- **External deletion:** Local clear cannot claim that a remote provider deleted data without a provider-confirmed receipt.
- **Provider routing:** Request tags choose an authorized route; they never authorize a scope, network destination or provider themselves.
- **Benchmark selection:** VibeMemBench's 111 targets from 90 repositories are selected for experience usefulness in a reference setting, so they measure whether the memory pipeline can recover and apply available experience, not the unconditional gain on arbitrary coding work. Keep a separately frozen unfiltered real-issue control. Never feed the verified experience directly to AtMem; that is an oracle upper-bound arm, not the product result. Histories stop before each target, and no target patch, future issue or hidden test enters memory formation. Report per-host results rather than pooling incompatible agent integrations.

## Constitution Check

| Principle | Design constraint | Verification boundary |
| --- | --- | --- |
| I. Authority before intelligence | Host and provider outputs are proposals or delegated context; AtMem alone authorizes canonical writes and local context. | Contract, scope and provider rejection tests in phases 2, 4 and 6. |
| II. Full-fidelity evidence | Full-fidelity is the default supported capture profile; formation selects a smaller canonical memory. Model input is claimed only when observed, not inferred from a submitted hook result. | Evidence-profile, capture-coverage and receipt-assurance tests in phases 3–5. |
| III. Safe defaults | Installation is non-influencing; explicit enablement starts active operation with no shadow period. Failed enablement restores the prior host configuration. | Installed-host probe and rollback tests in phase 3. |
| IV. Scope, deletion and encryption | Project/profile/agent scope is enforced; secrets are excluded from searchable/outbound memory but protected in evidence where required; persistent copies and bundles are encrypted. | Secret, isolation, deletion and stolen-copy tests in phases 1, 2, 5, 7 and 8. |
| V. Host-neutral contracts | All adapters use one versioned Code service and preserve host configuration on uninstall. | Schema and adapter-conformance tests in phases 2–3. |
| VI. Executable claims | An automatic host claim requires a real session hook and context-submission probe; each host/OS cell is reported separately. | Phase 3 host matrix and phase 4 handoff tests. |
| VII. Local-first egress | Base install needs no cloud account. External routes need explicit registration, query authorization, signed provider response and visible delegated provenance. | Phase 6 no-egress and failure tests. |
| VIII. Production-level evidence | VibeMemBench and an unfiltered real-issue control are frozen before any production-quality claim. | Phase 0 protocol; Phase 9 remains deferred by the owner in this request. |

The current 2.3.8 runtime may not satisfy the constitution's full encrypted-evidence profile on every supported install. This plan does not treat a new Code adapter as evidence of that guarantee; the installed-artifact gate must test the actual storage profile and label unsupported coverage. No Code benchmark or release claim is authorized by phases 0–8 alone.

## Requirement-to-gate crosswalk

| Requirements | Build tasks | Acceptance gate |
| --- | --- | --- |
| FR-001–FR-003, FR-012 | T009–T020 | Installation is non-influencing, explicit enablement/restore works, and each claimed host/OS has a successful hook and context-submission probe. |
| FR-004–FR-008 | T006–T012, T021–T024 | Secret-safe scoped formation, automatic turns, distinct exposure assurance, cross-agent sharing and governance-switch boundaries pass. |
| FR-009, FR-016 | T025–T027, T036 | CLI/dashboard search, settings parity, correction, clear and adjacent-scope isolation pass. |
| FR-010 | T028–T030 | A configured delegated route passes signed-contract, scope, egress, fallback and provenance tests. |
| FR-011 | T031–T033 | Optional graph installation, freshness/invalidation, source linkage and structural-baseline tests pass. |
| FR-015 | T034–T036 | Encrypted project bundle restores on a fresh install with identity preview, no credentials and search/lifecycle parity. |
| FR-013 | T004, T037–T039 | Protocol is frozen in phase 0; outcome evaluation is explicitly deferred to phase 9 and no benefit claim is made yet. |
| FR-014 | T005, T040–T041 | Roadmap consistency starts in phase 0; release preparation/publication is deferred to phase 9. |

All phases 0–8 are in the implementation scope of this request. “Opt-in” describes the user-facing graph, provider and adapter switches, not a waiver of their engineering gates. Phase 9 is not in scope now.

## Release and installation outline

The user chooses Code during normal AtMem onboarding or runs `atmem code setup` for one repository. Package installation leaves Code disabled. Setup lists detected hosts, storage location, capture mode, local/remote routes and compatibility, and previews changes before the user explicitly enables selected adapters. Active capture and injection begin at enablement; there is no shadow stage. A developer can later add an agent, run `atmem code doctor`, switch optional review workflow, pause capture, search, configure providers or clear through CLI/dashboard, and disable the adapter without losing unrelated AtMem state. Portable project export/import is a separate explicit operation, not an automatic cross-machine sync. Exact command flags and package extras are frozen only after implementation and installed-wheel verification.

Release completion follows `docs/release-coordination.md`: align AtMem, AtBot and OpenClaw bridge pins, add a versioned release note, test installed artifacts, prepare the separate owner-reviewed website source-pin PR, tag a clean reviewed commit and verify registry publication. Website PR merge and live deployment remain separate states.
