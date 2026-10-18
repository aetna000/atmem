# AtMem Code implementation plan

**Status:** Phases 0–8 implemented to the qualified subset in [implementation-status.md](implementation-status.md); remaining host and evidence gates are explicit blockers in [tasks.md](tasks.md). The release candidate version is not selected.
**Inputs:** [spec.md](spec.md), [market-research.md](market-research.md), AtMem Constitution, published 2.3.8 source.

## Technical context

The historical structural efficiency sequence is recorded in Spec 043, including
`covered-navigation-loop-v10.md`. The cross-repository direction below supersedes
further scored Click tuning. P8 passed installed qualification but its frozen
comparison failed: 3/5 each, unknown C usage and no accepted saving. Inspection
revealed example/implementation priority inversion. P9 changes shared allocation,
not traversal, authority, source/secret/freshness gates or budgets. Installed
qualification and scoring completed: 5/5 functional each, all usage known,
19.551447% input saving, below the unchanged 20% fallback. No transfer dispatched
or acceptance claimed. P10 completed qualification and ten attempts: 5/5
functional each, all-cap passes native 3/5 and structure 5/5. Delivered source
equivalence passes, but native hard-stop usage is unknown; no saving accepted.
The next bounded diagnostic is `usage-transport-diagnostic.md`; its zero-model
actual read/denial control passed. Scored transport remains unchanged.
P11 completed its ten-attempt frozen comparison: native 5/5 functional versus
structure 2/5, unknown structure total usage; no accepted saving or confirmation.
The requested Claude Opus 5.5 medium read-only review and retained tool audit
motivate retiring further scored tuning on the familiar five Click tasks.
The active prospective evaluation direction is
`cross-repository-evaluation-plan.md`: external task/environment qualification,
exposure/full-usage gates, bounded repository-disjoint validation and locked
confirmation. The Windows validation cohort has since completed 30 eligible
attempts: pack plus tools uses 24.817175% fewer aggregate input tokens with
4/10 full task passes each, but lower partial target correctness. The original
36-slot manifest retains six unqualified environment slots. See the completed
RandD Windows cohort report; no independent confirmation is complete.
No new memory engine is introduced.
No token-saving acceptance or release claim has been established.

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

- **Copilot CLI identity (T018):** Qualify CLI 1.0.98 separately on macOS and Windows. Use native `exec`/`args` hook entries to avoid shell-quoting differences, and configure an
  explicit event argument because native hook payloads omit the event name.
  Resolve each event against its exact `hook.start` entry in the local,
  version-checked session journal and use `hookInvocationId`, not text or a
  timestamp alone, for idempotency. Read only the named session's bounded tail;
  missing, ambiguous or mismatched entries withhold capture/context. The journal
  is a live adapter input, never canonical authority or a required future
  evidence dependency. Ordinary prompt context is empirically supported in this
  version; omit startup recall to avoid injecting the same context twice.
  Activation requires existing user-approved workspace trust and an offline,
  isolated real-CLI probe; never modify the owner's trust configuration.
  Windows npm shims are resolved to Node plus the installed CLI loader rather
  than sending prompts through `cmd.exe`. Offline probe environments preserve
  Windows system variables but exclude provider credentials. Windows runtime
  household access uses true shared `LockFileEx` locks; migrations retain
  exclusive locks on the same byte. Test the four cross-process shared/exclusive
  combinations, release/reacquisition and encrypted migration rejection.

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

## Proposed extension: source-incorporated AtMem Knowledge

The code-first implementation sequence is now detailed in
[code-knowledge-plan.md](code-knowledge-plan.md) (owner direction, 2026-10-17).
It extends the existing Code branch rather than replacing its adapters or
starting a parallel memory service. The upstream structural extraction and
query capabilities drive the capability checklist; AtMem remains the authority.
This new plan does not mark the expansion implemented or close existing gates.
Its upstream-first rule requires incorporation/reuse before replacement, a
source-to-capability parity register and differential tests against the pinned
upstream implementation. Any rewrite needs a documented incompatibility and
evidence; a limited Python milestone cannot be labelled full code-knowledge parity.
User transparency and substantially easier memory exploration are primary
acceptance goals, not optional dashboard polish. The companion plan defines a
unified Memory Explorer, source-to-use explanations, corrective actions and
baseline-relative usability gates. Existing search screens alone do not satisfy
this expanded goal.

**Owner direction, 2026-10-16:** incorporate and modify licensed upstream source
inside an AtMem-owned implementation. This supersedes the earlier proposal to
connect an independently installed knowledge product, and the intervening proposal
to borrow concepts only. Product branding, APIs, setup and management remain
AtMem. This is a planning addendum, not completed implementation or a new release
commitment. Existing phase 0–8 status, host blockers and the phase-9 execution
deferral remain unchanged. The core workstream is now specified as pending
FR-017–FR-028 and SC-008–SC-013 in `spec.md`, with T043–T060 in `tasks.md`.
Those requirements/tasks supersede the placeholder for an unspecified independent
feature. They do not retroactively extend completed phase 0–8 gates or authorize
runtime work in this documentation correction. Click execution remains separately
gated by Spec 043.

### Outcome and scope

Extend AtMem with one source-aware knowledge engine for documents, structured
data, conversations and code. AtMem Code becomes a domain-specific user of this
engine. The objective is capability coverage and measured improvements, not an
unsupported claim that all upstream features become production-ready on import.

This is **source incorporation**, not a required external SaaS, SDK wrapper,
rebranded upstream dashboard or second memory service. Maintain adapted modules
and their tests under AtMem ownership, with exact upstream lineage recorded in
the legal/source inventory. Third-party parsers, database drivers, model packages
and binaries remain separately licensed dependencies until individually audited.

### Preserve and extend existing AtMem components

| Existing component | Reuse | Necessary extension |
| --- | --- | --- |
| Canonical memory and evidence | Authority, access, lifecycle, source linkage and protected retention | Versioned source/fragment catalogs and admitted knowledge objects |
| `atmem/graph/` | Entity/relation contracts and authorized traversal | Domain types, source-anchor identities, extraction assurance and source-generation applicability |
| `atmem/retrieve/` | Ranking/fusion, evidence assembly, budgets, contradiction/sufficiency handling | Typed source and structural candidate providers; common planner and progressive detail |
| `atmem/code/` | Scope binding, authenticated intake, context receipts and qualified hooks | Thin domain facade over common source/knowledge contracts |
| CLI/dashboard/MCP | Existing management and authenticated product boundaries | Document/data/code ingestion, extraction progress, knowledge exploration and freshness |
| Deletion/export | Canonical lifecycle and portable encrypted state | Dependency cascades, rebuildable knowledge projections, worker/cache/backup coverage |
| Benchmark infrastructure | Manifests, resource/result accounting and existing safety tests | Cross-source and repository-task runners; full-pipeline stage diagnostics |

### Proposed structure and ownership

Proposed paths, not existing public APIs:

```text
atmem/knowledge/
  contracts.py          # SourceSnapshot, Fragment, Claim, Relation, Query, Receipt
  sources/              # authorized document, structured-data and repository inputs
  admission.py          # proposals enter existing AtMem authority, once
  projections.py        # rebuildable views, scoped outbox and generation tracking
  query.py              # nominations -> authority validation -> existing assembly
  lifecycle.py          # updates, tombstones, revalidation, scoped rebuilds
  worker.py             # authenticated, bounded extraction jobs and results
packages/knowledge-runtime/
  ...                   # adapted, isolated extraction/retrieval implementation
third_party/
  ...                   # source inventory, licenses, notices and modification map
```

Exact package boundaries are frozen after the dependency/storage feasibility
spike. An optional runtime may be a separate AtMem-managed process/distribution
to isolate heavyweight dependencies; it is still an incorporated AtMem component,
not an independent canonical memory product. The base package remains useful
without its installation. Code-specific hosts do not gain new core authority.

### Architecture and non-negotiable boundaries

1. **Authorize before extraction.** AtMem approves roots, files, source versions,
   operations, principal and permitted model egress. Connector configuration
   cannot grant scope. Source URLs are subject to network/redirect/SSRF policy;
   document parsers and archives have file, page, depth, expansion and time limits.
2. **One admission path.** Adapted extractors produce bounded candidates and
   evidence anchors. AtMem validates them through its authority boundary. No
   imported `remember`, auto-improve, merge, permission or delete path may bypass
   admission. Avoid running two independent semantic classifiers on each write.
3. **Distinct object meanings.** Raw sources, parsed structure, attributed claims,
   inferred relations and verified observations are different objects. Code
   edges declare syntax/resolver/runtime assurance. Foreign-key edges require
   declared or verified schema evidence; similar field names are not proof.
   A timestamp alone does not establish supersession or code applicability.
4. **Current source authority.** Snapshot identity includes repository/worktree,
   commit and dirty-content digests where applicable; structured records have
   key/schema/version identity; documents have source version and anchors.
   Models cannot invent missing source bytes, author intent or historical results.
5. **Rebuildable projections.** Accepted knowledge is committed before indexing
   through an idempotent outbox. Publish coherent projection generations and
   enforce deletion/permission epochs on replay. An index nominates records;
   AtMem rehydrates authorized evidence and assembles the final context.
6. **Encryption end to end.** Inventory all imported storage: raw files, graph,
   vectors, semantic metadata, caches, extraction spools, logs, backups and
   exports. Adapt I/O through AtMem's authorized encrypted storage/key-release
   boundary. Decrypted processing is scoped and ephemeral. No stock plaintext
   graph/vector backend or temporary directory is an acceptable implicit fallback.
   SQLCipher alone must not be relabelled the constitution's complete
   quantum-resistant evidence profile. If the selected imported component cannot
   meet the required storage boundary, adapting or replacing it is blocking work.
7. **Worker isolation.** No broad household credentials or shared DB key in the
   extraction worker. Use authenticated scoped job/result channels with deadlines,
   cancellation, resource caps and crash recovery. Disable inherited telemetry,
   update checks, remote-client routes, automatic provider/model downloads and
   arbitrary code/tool execution unless separately authorized. A worker crash
   leaves deterministic memory usable or withholds additional knowledge.
8. **Deletion before delivery.** Canonical tombstones immediately withhold affected
   evidence and derived descendants. Track physical cleanup independently,
   including vector/graph/cache copies. Retained backup policy is explicit; restore
   replays deletion state before making knowledge searchable. No 'fully deleted'
   receipt until required representations have been verified.
9. **Compatibility.** Preserve current APIs and deterministic defaults. New features
   are explicit opt-ins with additive migrations, upgrade/rollback tests and no
   destructive downgrade. Validate Python 3.10–3.13, macOS/Windows/Linux installed
   artifacts and each supported optional runtime separately. Preserve current
   AtBot/OpenClaw authority and existing provider routes.
10. **Generic access.** One versioned CLI/MCP/API and dashboard view exposes source,
    knowledge and context operations. Hooks remain per-host automation, not a
    prerequisite for indexing/querying code. Do not inherit upstream automatic-host
    claims without testing the exact incorporated adapter/version/platform.

### Capability coverage register

Before selecting files to import, enumerate upstream capabilities and label each
`reuse-existing`, `incorporate-and-adapt`, `replace`, `defer` or `not-applicable`,
with source revision, dependencies, owner, tests and release status. No deferred
capability is counted as parity. Required tracks are:

- Document loaders, section/table/chunk preservation, entity/relation proposals
  and source attribution. Start with Markdown/text; audit PDF/office parsers
  before claiming those formats. Preserve original authorized artifacts.
- Structured CSV/JSON/schema ingestion, typed values, stable record identity,
  declared relationships and updates. Live database connectors are a separately
  scoped credential/egress capability, not implied by file ingestion.
- Code extraction: symbols, imports/references, available dependency/API/test
  relationships, architecture/path/impact queries, snapshot deltas and source
  evidence. Retain explicit unsupported/unresolved states per language.
- Connected retrieval: lexical/semantic/graph nomination, relationship expansion,
  source-grounded assembly, progressive disclosure and abstention. No free-form
  generated answer silently replaces a retrieved evidence object.
- Incremental updates, contradiction handling, feedback and knowledge maintenance
  under AtMem authority. Feedback weight is not factual verification and repeated
  access must not promote an unsupported claim to truth.
- Lifecycle, permissions, inspection, correction, deletion, portability and
  background-job observability for every incorporated representation.

### Benchmark-first execution order and gates

The broad K0–K7 sequence below describes the longer cross-source program; it is
not a second task inventory. Code-first CK0–CK6 and T043–T060 implement the pending
FR-017–FR-028 workstream. Document/structured-data connectors beyond the code
surface need later explicit requirements/tasks and are not claimed completed by CK.

| Phase | Deliverable | Exit gate |
| --- | --- | --- |
| K0 | Independent core spec/tasks, capability register, exact source/dependency/license inventory and frozen AtMem 2.3.8 plus current Code baselines | No release/version or historical benchmark relabelling; representative tasks and held-out split defined before tuning |
| K1 | Small source-incorporation and storage feasibility spike in isolated public-data fixtures | Scoped proposals, no default network traffic, reproducible build and actual encrypted-copy inspection; no owner installation/data changes |
| K2 | Common source/fragment/knowledge contracts and authority/storage bridge | Scope, mutation, invalid-result, tamper, concurrency, crash, migration and delete/restore tests pass |
| K3 | First vertical slice: Markdown documents, CSV/JSON and Python source | Correct typed knowledge and cross-source evidence queries through AtMem, with unsupported links left unknown |
| K4 | Required code-knowledge builder and structural queries; broaden format/language coverage by cell | Verified extraction/relationship precision and coverage, update/delete/rename behavior, branch/worktree isolation and bounded impact results |
| K5 | Integrated task-context planner, source applicability and engineering experiences | Matched ablations isolate structure, record shape, freshness and gating; no regression hidden by more abstention |
| K6 | AtMem-branded CLI/dashboard/setup, agent integration and encrypted portability | Normal-user install/query/update/delete/restore journeys on claimed platforms; no automatic activation inferred from MCP availability |
| K7 | Separately authorized held-out comparative evaluation and release preparation | Quality, harm, full cost, p50/p95 latency, reproducibility, dependency attribution and coordinated release gates all pass |

K3 is the first useful integrated slice, not completion of all gaps. Code knowledge
in K4 is required for the expanded Code promise, not a discretionary optimization.
Later connectors, formats and languages need explicit coverage entries; no
automatic claim of 'all upstream capabilities' follows from copying the package.

Diagnostic pilots may use 20–30 authentic tasks across several repositories or
source collections; pilot results are not publication-level evidence. Freeze a
separate repository/collection-disjoint chronological confirmation set before
tuning. Synthetic unit fixtures validate boundaries only, not product quality
or model training. No training is required by this plan.

Compare a strong native-tool/no-memory control, current AtMem, current Code
memory-only/structure-only/combined configurations, the exact upstream baseline
in a separate benchmark environment, and the incorporated AtMem engine with
incremental features ablated. The competitor baseline is not shipped in AtMem.
Keep solver, authorized source/history boundary, resources and grading equal.
Target fixes, future data and hidden tests remain evaluator-only. Log ingestion,
update, nomination, assembly, delivery and solver stages with cold/warm latency,
total cost, executable/answer correctness, coverage, abstention, harmful recall,
scope failures and uncertainty. VibeMemBench execution remains blocked until its
actual runnable licensed artifacts are available; use independently specified
authentic tasks without calling them a VibeMemBench reproduction. Large paid
benchmark execution and release publication require separate authorization.

### Source incorporation, rebranding and required legal records

Product presentation uses **AtMem** and **AtMem Code**. There is no proposed
upstream logo, co-branding, separate upstream account, public upstream-specific
command or settings workflow. AtMem does not claim original authorship of
incorporated third-party source or endorse unmeasured superiority. Source and
dependency provenance and reproducible benchmark reporting remain accurate.

The inspected incorporation candidate is **Cognee**, Apache-2.0, commit
`f154b32a9e544dac73e7ddf2010327cf9988edcd` (source declares 1.6.4).
This is a source-review pin, not proof of a released package or compatible build.
Its [LICENSE](https://github.com/topoteretes/cognee/blob/f154b32a9e544dac73e7ddf2010327cf9988edcd/LICENSE)
and [NOTICE.md](https://github.com/topoteretes/cognee/blob/f154b32a9e544dac73e7ddf2010327cf9988edcd/NOTICE.md)
must be included as applicable in the distributed legal materials. Retain
relevant copyright, patent, trademark and attribution notices in source; mark
modified files prominently and keep a source/import modification map. Apache-2.0
does not grant upstream trademark rights or remove separate dependency licenses.
Required attribution is retained even when ordinary UI is wholly AtMem-branded.

Inventory every incorporated file and transitive parser/model/binary license,
including Enola when code extraction depends on it. If source is vendored and
imports renamed, automate and test the transformation; do not mass-remove
copyrights or edit notices as a branding step. Produce a packaged license/notice
bundle and dependency manifest/SBOM, and verify their presence in wheels,
installers, containers and offline bundles. A new dependency-version import
requires the same review; the top-level license is not a blanket clearance of
the whole dependency tree. Resolve ambiguous obligations before distribution.

Maintain an AtMem-controlled source fork/import registry, explicit patches,
reproducible build hashes, security-update intake and upstream-diff review.
Disable automatic replacement from upstream main. Prefer narrowly adapting
useful extraction/retrieval components and their tests over importing unrelated
cloud billing, telemetry, user management, web UI or an autonomous second
knowledge lifecycle. Track discarded functionality honestly in the coverage
register. A source fork creates an ongoing maintenance obligation.

### Completion definition

The extension is complete only when admitted source families have tested
ingestion, connected queries, updates, access boundaries, verifiable deletion,
encrypted portability and installed-product evidence. A copied code tree,
renamed package, successful import or working upstream demo is not completion.
No universal parity, '10x', leadership, full-reconstruction or published-release
claim is made by this plan.

The Windows structural-efficiency confirmation also requires the benchmark-only
source/runtime separation and bounded lossless result transport in
`source-runtime-projection-v2.md` (T082). This qualification work does not change
the frozen product, pool, task tests or efficacy thresholds. Its implementation
and installed controls must complete before affected T081 model runs.

The subsequently observed valid-source encoding failures are addressed by the
bounded new-preview correction in `source-text-compatibility-v1.md` (T084).
This does not mutate the frozen confirmation wheel or resolve its separate
generation-row size failure. Installed replay and explicit evaluation treatment
remain mandatory before scoring the changed product.

The independent generation-row failure has a bounded, lossless storage plan in
`generation-storage-compatibility-v1.md` (T085). It preserves the existing
physical row/source/worker limits and full original artifacts, with explicit
logical decode bounds, legacy-read compatibility and no plaintext side store.
This is a new preview format, not a patch to the locked benchmark candidate.

Any scored use of that independently installed compatibility preview follows
`windows-confirmation-v3.md`: disclose qualification-informed development,
retain all nineteen frozen identities and old failures, restage all 76 cases,
and preserve unchanged token/quality/authority/archive gates. At that prospective
checkpoint no model outcome had been observed in this repository-disjoint cohort.

The subsequently completed v3 comparison records 5.299941045% lower TOTAL input
and 13/38 full passes versus 12/38 native. It fails the 20% fallback; the goal
remains open. Preserve that frozen comparison and its archive. T087's all-case
trace/query audit and nineteen exact pack replays identify a generic substring
matching defect. The bounded correction follows
`strict-identifier-ranking-v1.md` (T088), not an in-place update of the scored
installation. Any candidate informed by these results treats this cohort as
reused development evidence and needs separately disclosed confirmation.

The compound correction removes a real false match but is not sufficient by
itself: five of nineteen pack-only replays change, and some roots remain
unrelated. T089/T090 follow `typed-query-nomination-v1.md`: preserve symbol type
when binding syntax, and use only explicitly observed query aliases as location
hints. These changes do not remove graph facts, relax authority, encode benchmark
identities or turn static replay into a performance result.

The next installed/model step follows `corrective-development-screen-v1.md`
(T091/T092): exact one-file preview delta, real installed controls, then fresh
native/corrective cases for all nineteen reused issues, one repeat and 38 total
attempts. Old native results are not substituted for fresh controls. This is
development screening; a passing result cannot itself close T062.

CD1 subsequently completes with 9.317165272% lower TOTAL input, 6/19 full passes
in each arm, and independently verified archives. Both token targets fail.
The all-case trace diagnostic (T093) remains descriptive, not causal evidence.
T094 follows `query-layout-ranking-v1.md`: Markdown subsection-label-only terms
receive lower lexical weight while body content, titles, literal fenced code,
standalone headings and explicit references remain intact. Preserve the entire
CD1 packer before editing, enforce the helper/query-weight-only delta, then
reproduce all nineteen original packs and record every static counterfactual
from authenticated archives. No model execution or efficacy claim follows from
this source change or pack replay. Further installed and scored work requires
its separate prospective gate and untouched confirmation remains necessary.

T095 and T096 extend the same query-nomination boundary through
`query-reference-ranking-v1.md` and `query-source-location-v1.md`: actual
syntactic call support instead of prose-parenthesis promotion, and existing
authorized symbols nominated by bounded source-URL line hints without network
access. Each step retains its complete source ancestry and all-case static
counterfactuals. The reusable diagnostic runner supports explicit profiles and
bounded stdin reader transport; it is not a new solver or grader stack.
T097/T098 follow `query-nomination-development-screen-v1.md` only after terminal
static gates: separate full-source preview/install qualification, then 38 fresh
matched development attempts. A passing development screen still cannot close
the original efficiency goal without untouched confirmation.

CD2 subsequently completes matched scoring with 26.231768438% fewer TOTAL input
tokens, but 7/19 full tasks versus native tools' 8/19. The quality condition fails;
the combined fallback is not accepted. Preserve the original candidate and all
38 outcomes. All 310 required evidence runs export successfully; MEM transfer
and separate-process recovery remain the final T098 execution gate. No new
candidate or untouched-confirmation inference follows from the token number
alone. Inspect the complete recovered traces and discordant pairs first, without
claiming a causal explanation from aggregate results or tool-output byte proxies.

T099 subsequently verifies all 38 traces and directly inspects all discordant
patches. It identifies source-localization gaps, separate repair reasoning
failures and weak public-test feedback without a causal claim. T100 repairs only
registered directory ancestry; exactly two original valid requests become
accepted while seventeen invalid source-path selectors remain rejected. T101
implements `query-literal-anchors-v1.md`: verified source-local literal bindings
to existing callable/class targets and named-symbol precedence over conflicting
unverified line hints. Exact source-delta/all-nineteen static replay and 785
regression checks pass; three packs change, with no new efficacy claim. The
next runtime/study must freeze this candidate and explicitly qualify the repaired
public selector in both host and sandbox, preserving old artifacts, paired
controls, budgets, all failures and the separate untouched-confirmation gate.

T102 subsequently completes the separate installed literal-anchor preview:
all nineteen packs reproduce and all five fresh source/scope/freshness/audit/
encrypted-bundle/MCP controls qualify, with zero inference. T103's archive-only
check proves exact validator-only changes in all 38 original server/worker
programs; actual runtime qualification remains separate. T104 follows
`literal-anchor-development-screen-v1.md`: fresh balanced 38-attempt CD3,
unchanged model/budgets/private graders, common repaired public selectors in
both arms, real nested-root/node and negative-selector readiness probes before
inference. No prior native result is substituted. This remains reused-task
selection; even a positive comparison still needs untouched confirmation.

While CD3 inference is live and before any quality/token result inspection,
T105 freezes `unexposed-confirmation-pool-v4.md`. Exclude every thirteen prior
catalog repository groups, including metadata/environment-only exposure, and
use the remaining five groups. Freeze eight identity-only feasibility candidates
per group before task metadata/recipes; retain failures and open no gold/tests/
hints or problem statements at this stage. This avoids selecting a holdout from
the current repair outcomes. It neither changes CD3 nor starts confirmation.
Later confirmation still needs positive complete development selection,
independent recovery, all forty eligibility results and an exact twenty-issue
execution lock; missing qualification cannot silently shrink the design.
