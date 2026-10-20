# AtMem Code: maintained repository knowledge

**Date:** 2026-10-17. **Status:** implementation plan, not implemented capability.
**Working branch:** `feature/atmem-code-2.3.9` in the Code worktree.
**Parents:** [spec.md](spec.md), [plan.md](plan.md), and the source-incorporated
AtMem Knowledge extension. Existing phase 0–8 qualification and blockers remain
accurate; the new work is not retroactively included in their completed tasks.
**Governing pending requirements:** FR-017–FR-028 and SC-008–SC-013 in
[spec.md](spec.md), implemented by T043–T060 in [tasks.md](tasks.md).

## Product decision

Extend the Code implementation already built. Incorporate and adapt useful
licensed upstream code, including the required structural extraction dependency,
instead of merely attaching another memory product. Cognee's code-knowledge
capabilities lead the coverage checklist; its existing authority, telemetry,
account system and storage defaults do not replace AtMem's boundaries.

The user gets two complementary kinds of context through the same AtMem service:

- **Current repository structure:** components, symbols, dependencies, endpoints,
  resources, discovered test links, and evidence-backed paths between them.
- **Engineering experience:** existing source-bound user assertions plus a pending
  governed coding-attempt proposal path. Current adapters do not automatically
  turn solver/tool outcomes into durable lessons. Product experience formation
  and cross-revision applicability are prerequisites, not completed capabilities.

The graph describes discovered structure. It does not prove developer intent,
runtime execution, a successful fix or exhaustive change impact. Absence of a
discovered edge is not proof that a dependency does not exist.

**Primary user goal: transparent, easy-to-explore memory.** The user must be able
to see what AtMem knows, where it came from, where it applies, what changed and
what an agent actually received, without reading database rows or learning graph
query syntax. Improving this experience substantially over the current dashboard
is a required outcome alongside upstream code-knowledge capability coverage.

## Actual reuse and gaps

### Upstream-first implementation rule

Owner clarification, 2026-10-17: do not independently reinvent Cognee's
code-knowledge pipeline. The default is to incorporate/adapt its working
implementation and tests, together with the required audited extractor, then
bridge it into AtMem. Inspiration alone is not completion.

For each capability, apply this order:

1. Reuse an existing AtMem implementation when it demonstrably provides the same
   behavior; do not retain duplicate services or algorithms.
2. Incorporate the pinned upstream implementation and relevant tests where
   licensing, dependencies and AtMem's boundaries allow it. Preserve useful
   upstream data semantics, extraction behavior and query algorithms; map their
   interfaces at a narrow boundary rather than designing parallel equivalents.
3. Adapt only what is necessary for authority, encrypted storage, lifecycle,
   packaging or host integration. Record the reason and test each semantic
   difference against the pinned baseline.
4. Replace an upstream component only with a written decision identifying the
   concrete incompatibility, alternatives and differential evidence. Convenience,
   unfamiliarity or a smaller demo is not justification for a rewrite.

New contracts in this plan are boundary contracts, not instructions to rebuild
upstream internals from scratch. New module paths do not require a new algorithm.
The existing AST fallback must not become the main implementation merely because
it is already available. Enola is the preferred extraction candidate subject to
the required audit; an alternative needs the replacement decision above.

### Mandatory parity register and differential gates

CK0 must create a checked-in register with one row per pinned upstream capability
and language/framework/platform cell: source file/symbol and revision, upstream
test/example, dependencies and license, AtMem counterpart, reuse/adaptation
decision, differences, test IDs, result artifacts and completion state. Inspect
upstream source and runnable examples rather than infer capability from product
copy. Audit graph loading, queries and maintenance as well as extraction.

Required rows cover all object kinds and relation families listed below, all six
query operations, extraction receipts/findings, snapshot identity, unchanged
snapshot handling, incremental updates and invalidation, and supported language
and framework behavior. The baseline envelope is frozen before implementation;
it cannot be narrowed afterwards merely to make the parity report pass.

Run pinned upstream and adapted AtMem components on identical authorized public
repository snapshots and edits. Normalize only opaque IDs, ordering and other
documented nonsemantic differences; compare object/edge types, source anchors,
assurance, query/path results, findings, deltas and failure/unsupported behavior.
Reuse upstream regression fixtures where licensed and add tests for AtMem's
authority and lifecycle boundary. Investigate differences; matching an upstream
bug is not required, but intentional fixes require evidence and documentation.

Every supported baseline cell must have a passing comparison or an explicit,
tested behavioral difference. Deferred, missing, blocked and fallback-only cells
remain parity gaps and prevent an unqualified code-knowledge parity claim. A
Python-first milestone is useful delivery, not parity with broader upstream
coverage. Structural conformance does not establish equal agent task quality or
latency; those require the separate matched outcome evaluation already planned.

This register and differential suite are completion deliverables, not optional
research notes. Keep source patches small and traceable so later upstream fixes
can be reviewed and adopted without reconstructing an independently rewritten
engine. AtMem's additional memory/agent capabilities are measured separately;
they cannot compensate for a missing structural capability in the parity report.

| Existing branch component | Keep | Extend or replace |
| --- | --- | --- |
| `atmem/code/graph.py` | `CodeGraph` facade, ignore/secret checks, bound-root authorization, syntax-only fallback | Replace single `graph/current` payload with versioned typed snapshot projections; add relationship traversal and deltas |
| `atmem/graph/models.py` | Evidence references, entities, relations and authorized paths | Add source-anchor and code-domain contracts without relabelling semantic entities as resolved symbols |
| `atmem/code/context.py` | Authorized memory recall and context budgets | Compose experience and structural evidence under one budget; anchor-based applicability rather than blanket dirty-repository exclusion |
| `atmem/code/runtime.py` | Recall-before-capture, host delivery and graph evidence checks | Replace appended graph text with one planner/assembler; revalidate final snapshot before submission |
| `atmem/code/identity.py`, `application.py` | Repository binding, project/private lanes, settings and authorization | Snapshot/worktree identities and shared query service |
| `atmem/code/adapters/`, `hook.py` | Existing qualified host boundaries and truthful assurance levels | Pass current snapshot/task identity; do not rewrite each CLI for each knowledge type |
| `atmem/code/portable.py`, deletion and dashboard | Encrypted bundles, scoped clear and common management | Knowledge catalogs, projection rebuild, lifecycle cascades and graph exploration |

The current Python index extracts definitions/imports/call references. Calls are
explicitly `syntax_only`; other eligible languages receive file entries. It does
not already implement the full endpoint/resource/test graph described here.

## Target architecture

1. **Snapshot:** authorize a bound root; enumerate eligible source bytes under
   ignore, secret, path, size and egress rules; create an immutable manifest.
2. **Extract:** an isolated deterministic code-analysis worker consumes only the
   approved snapshot and returns facts, relationships, findings and a receipt.
3. **Validate/admit:** AtMem checks job binding, schema, source anchors, allowed
   types, scope, limits and extraction version. Reject invented or unknown source
   references. Deterministic extraction is still untrusted input to authority.
4. **Project:** commit admitted structural records and an idempotent projection
   outbox; publish a coherent derived graph generation after indexing completes.
5. **Query:** bounded graph/lexical queries nominate evidence; AtMem reauthorizes
   nodes, edges and source anchors before returning the visible subgraph.
6. **Compose:** merge relevant structure with applicable engineering experiences
   into one bounded context package and existing exposure receipt.
7. **Maintain:** source deltas invalidate affected evidence, rebuild affected
   projections and preserve inspectable historical snapshots where authorized.

### Governed experience and applicability (required for B and D)

Extend `atmem/code/formation.py` with an explicitly versioned coding-attempt
proposal contract, without relaxing current user-assertion rules. A proposed
experience cites authorized intent/action spans and producer-bound execution
receipts: command, source/environment hashes, attempt identity and retained
result. Validate provenance and permitted scope before interpreting any content.
Use the existing single admission path; assertions and model proposals do not
verify themselves. Preserve observed failures and unknown outcomes; a passing
test supports only its declared bounded result, not overall correctness.

Add a product applicability service under `atmem/knowledge/code/applicability.py`
usable by experience-only mode without requiring the rich extractor. It validates
source/config/environment anchors and declared dependencies, retains applicability
across irrelevant edits, and withholds changed/unresolved evidence. Signed
evaluator identity mappings must bind actual sanitized source manifests and
authorized projects; the benchmark cannot merely spoof a Git revision. Recheck
at context delivery and keep historical results separately inspectable.

Disjoint authentic product diagnostics must demonstrate eligible formation,
later-revision recall and required withholding. Report candidate/admitted/
applicable/retrieved/delivered counts and zero-result reasons. Do not choose the
five Click targets for likely memory usefulness or manufacture a lesson if no
eligible experience exists. Click `history.py` orchestrates calls only; it may
not implement replacement formation, applicability or admission.

No second semantic writer, unrestricted graph database, mandatory embedding
model or mandatory hosted LLM. Structural queries must work offline without
embeddings or a generative model. Models may interpret the returned evidence.

### Proposed module boundary

Common source/snapshot/admission/projection/lifecycle contracts belong in
`atmem/knowledge/` as proposed in the parent plan. Code-specific modules live in
`atmem/knowledge/code/`: `extractor.py`, `mapping.py`, `queries.py`,
`applicability.py` and `delta.py`. These are proposed files, not existing APIs.
`atmem/code/graph.py` becomes a compatibility facade; the Code application,
runtime, CLI, dashboard and MCP call one application service.

An optional AtMem-managed worker isolates incorporated heavyweight dependencies.
It receives scoped jobs, not household keys or unrestricted database access.
Keep the existing Python AST fallback, labelled limited, if the worker is absent.
A fallback is not a passed full-knowledge capability gate.

## Extractor incorporation is required work

Use the parent plan's reviewed Cognee source pin
`f154b32a9e544dac73e7ddf2010327cf9988edcd` as the initial inspection reference,
not an assertion of current release status. Inventory exact code loader,
contracts, query algorithms and tests worth adapting. Do not copy an entire
platform merely to acquire a code loader.

Before selecting Enola, independently resolve its exact source/binary revision,
license/notices, transitive dependencies, supported language/platform matrix,
distribution size, schema, reproducible build and network/telemetry behavior.
Audit subprocess and filesystem behavior: extraction must not run repository
build scripts, install packages, fetch dependencies, execute tests or follow
symlinks outside approved roots without a separate authorized operation.

Choose either (a) pinned, audited Enola incorporated/packaged under the AtMem
worker, or (b) an equivalent extractor passing the same capability tests. A
loader-only implementation cannot pass. Record unsupported cells explicitly;
do not silently substitute AST name matching for resolved dependencies.

Retain applicable licenses/NOTICE, copyright and modification records in source
and distributed artifacts; produce a dependency/SBOM inventory. Product UX is
AtMem-branded. Accurate legal and reproducibility records are not removed.

## Typed data and assurance

| Contract | Required information |
| --- | --- |
| `RepositorySnapshot` | Project/repository/worktree identity, commit, branch as metadata, dirty manifest, file hashes, extractor/config/schema revisions and snapshot digest |
| `CodeObject` | Opaque ID, kind, qualified identity, snapshot, language, file/span, source digest, scope and lifecycle |
| `CodeRelation` | Typed endpoints, evidence anchors, snapshot, assurance, resolver/version and unresolved state |
| `ArchitectureFinding` | Rule ID/version, supporting subgraph, bounded finding and limitations; never an unlabelled verified fact |
| `ExtractionReceipt` | Bound job/snapshot, input coverage, parsed/skipped/failed files and reasons, supported capabilities, output hashes, durations and resource usage |
| `KnowledgeQueryReceipt` | Authorized snapshot/generation, operation, evidence IDs, bounds, unresolved/truncated/stale state and returned-content digest |

Object kinds: repository, module/file, symbol, API endpoint, storage resource,
external dependency and test reference. Relations include containment, imports,
references, calls, route-to-handler, dependency usage, resource access and test
links **only where supported by concrete extraction evidence**. Exact predicates
and cardinalities must be frozen in the versioned contract before implementation.

Distinguish `syntax_observed`, `statically_resolved`, `heuristic` and
`runtime_observed` assurance. A syntactic call name is not a resolved edge. A
name resembling a database table is not a discovered storage access. A test
filename match is not proof of coverage. Runtime evidence requires a separately
captured execution receipt bound to the tested source and environment.

IDs must distinguish duplicate symbol names and scopes. Snapshot object IDs may
change across renames; cross-snapshot correspondence is explicit and qualified,
not asserted as permanent identity from line numbers alone.

## Shared query contract

Expose the following operations through one versioned service, mirrored in CLI,
MCP and dashboard. Command spelling is provisional until contract tests exist.

| Operation | Required output |
| --- | --- |
| Explore component | Typed object, source anchors and bounded neighbourhood |
| Dependencies/dependents | Directional typed edges, unresolved references and coverage |
| Find path | Evidence-backed path with relation/assurance filters; no path means none found within declared coverage/bounds |
| Potential impact | Candidate affected nodes, explaining paths and analysis limitations; not an exhaustive guarantee |
| Architecture overview | Evidence-backed structural summary and rule findings, without invented design intent |
| Snapshot diff | Added/removed/changed objects and edges, source changes, correspondence assurance and extraction coverage differences |

Every request binds authenticated project/profile, snapshot, operation, seeds,
edge/assurance filters, maximum hops/nodes/bytes and deadline. Stable pagination
binds the same snapshot. Prevent forbidden intermediate nodes from leaking via
path counts, names, findings or inferred summaries. Check endpoint permissions
and every traversed edge; a query filter cannot confer authority.

## Freshness, branches and maintenance

Branch names are labels, not applicability proofs. Bind facts to source anchors,
content and extraction configuration. Separate simultaneous worktrees and dirty
snapshots; reusing unchanged extraction is permitted only inside authorized
scope with matching content/config identities.

An edit removes old evidence from *current* queries before publishing its
replacement. Dependency changes may require re-resolving unchanged consumers;
renames, deletions, configuration changes and negative lookups are invalidation
inputs, not just modified file hashes. New snapshots become current atomically;
a crash cannot expose mixed-generation paths.

Classify remembered experience as project-wide, anchor-dependent or historical.
Preserve branch-independent preferences. Revalidate dependent anchors and
observed test receipts; when applicability is uncertain, label/withhold rather
than presenting the claim as current. A matching branch name is insufficient.
Source validation is repeated at final context delivery to handle intervening
edits. Explicit historical queries remain possible without automatic injection.

## Storage, compatibility and user controls

Reuse AtMem's authority/storage boundary with additive migration and encrypted
projections. Cover graph metadata, file manifests, caches, extraction spools,
worker logs, bundles and backups; never silently fall back to plaintext. Apply
canonical deletion/permission epochs before delivery, then verify physical
cleanup of registered derived representations. Restore cannot resurrect deleted
evidence. Required cryptographic profile claims need installed-artifact proof.

Preserve existing memory APIs and disabled-Code behavior. Indexing is an explicit
project opt-in with readable local/remote settings. Enabled maintenance can run
in the background within configured budgets. No shadow mode. `disable` continues
to mean stop automatic capture/injection; it does not erase memory or uninstall
hooks. Explicit indexing and exploration remain separately controlled. No
automatic execution of repository code is introduced.

The dashboard must show indexing progress/errors, language coverage, snapshot
and worktree, freshness, component/source inspection, paths, diffs, query receipts
and scoped clear. CLI has matching controls. Preserve existing host-specific
qualification; a graph query working over MCP does not qualify automatic hooks.
Base memory stays usable without the optional worker on macOS, Windows and Linux.

## Memory Explorer: transparency as a first-class outcome

Provide one discoverable entry point for project memories and repository
knowledge, with clearly labelled record kinds rather than separate opaque stores.
Default to a readable list/cards and detail panel. Offer timeline, source tree
and bounded relationship views as complementary navigation, not a mandatory
full-repository graph. Plain-language explanations must be built from recorded
provenance and decisions, not invented model reasoning.

- **Find and browse:** keyword search always works without a hosted model;
  optional semantic search is labelled. Browse without knowing the right query.
  Filter by project, profile, agent, source/file/component, type, time, lifecycle
  and snapshot/worktree applicability. Show effective scope and active filters,
  counts within authorized scope, stable pagination and useful empty/error states.
- **Understand a record:** show readable content, original authorized source
  excerpt/location, creator or extractor, timestamps, extraction assurance,
  freshness and applicability, related memories/code objects, and revision or
  supersession history. Distinguish observed structure, remembered assertion,
  heuristic inference and external-provider content. Unavailable evidence is
  labelled unavailable; IDs and hashes supplement rather than replace content.
- **Explain storage and use:** answer "Why is this remembered?", "Where does it
  apply?", "What replaced it?", "Which agent used it?" and "Why was it withheld?"
  using formation, applicability and delivery receipts. Distinguish prepared,
  submitted, acknowledged and model-observed context; lack of a receipt is unknown,
  not proof that a memory was never used. Retained intake decisions may be
  inspected separately without making rejected content ordinary recall candidates.
- **Follow connections:** navigate memory to source, source to symbols, symbols
  to dependencies/tests and back to relevant engineering experience. Each step
  retains scope, filters and back-navigation. Explain relation types in ordinary
  language and show supporting anchors, coverage and unresolved links.
- **Act safely:** correct/supersede a memory, inspect changes, re-index stale
  sources, or forget/clear an exact selection from the same view. Preview affected
  records and descendants before destructive actions; show confirmed, pending or
  failed cleanup. Never imply canonical source code was edited by correcting a
  derived record, or that remote data was deleted without provider confirmation.
- **Make it accessible:** keyboard navigation, visible focus, readable contrast,
  status labels not conveyed by colour alone, and equivalent list-based access
  to relationships. CLI supports search, inspect, history, related records and
  receipt inspection through the same authorized service and stable record IDs.

Authorization and privileged disclosure apply to snippets, counts, previews,
relationships and exports as well as detail pages. No cross-scope information or
protected secret is exposed to make browsing more convenient. Exploration uses
server-side bounded queries; it must not load the whole database into the browser.

### Required user journeys and usability gates

Before redesign, record the current branch's task completion, time, interactions
and failures on the same permissioned dataset and hardware. Test five journeys:
find a remembered decision; inspect its source and applicability; follow a code
relationship to an associated memory; explain a particular turn's supplied or
withheld context; and preview/complete a scoped correction or deletion. Use at
least five representative users in a formative study, counterbalance old/new
interface order and retain per-task results. Do not claim statistical population
benefit from this small study.

Proposed acceptance targets, to be frozen before testing: at least 90% aggregate
unassisted task completion, no journey below 80%, and at least 30% lower median
completion time than the current interface for journeys both support. New-only
journeys report absolute completion/time, not a fabricated relative improvement.
Report errors and p95 search/detail latency at a declared representative record
count, not just a successful demo. No wrong-scope disclosure or unintended
deletion is acceptable. Small studies are product usability evidence, not a
coding-quality benchmark. Automated browser/CLI/accessibility checks supplement
these tests but cannot establish that users find the interface easier.

## Dependency-ordered implementation phases

| Phase | Work | Exit evidence |
| --- | --- | --- |
| CK0 | Freeze expansion requirements/tasks, capability register and baseline manifests; pin incorporation sources and audit Enola | Explicit supported capability cells, license/build/storage decisions and preserved current Code tests |
| CK1 | Snapshot contracts and isolated extractor vertical slice using public fixture repositories | Deterministic repeated output, provenance, resource limits, secret/path/egress tests and real extractor on each claimed platform |
| CK2 | Typed admission, encrypted projections and incremental maintenance | Migration, scope, malformed facts, outbox/retry/crash, edit/rename/delete, consumer re-resolution and atomic-generation tests |
| CK3 | Six structural query operations | Exact expected paths and bounds, forbidden intermediate-node denial, unresolved states and no-LLM/no-embedding execution |
| CK4 | Governed coding-attempt formation, graph-independent applicability and unified context planner | Authentic disjoint formation/recall/withhold diagnostics for experience-only and combined modes, shared budget, no duplicate packing and final-delivery race checks |
| CK5 | Unified Memory Explorer, CLI/dashboard/MCP, background jobs and portable bundles | Search/browse/source/history/use/relationship/action journeys, accessibility, cancellation/restart, encrypted export/import/deletion and unchanged host disable/restore semantics |
| CK6 | Qualification, usability study and comparative evidence preparation | Baseline-relative exploration targets, per-language/platform capability report, installed artifacts, regressions and frozen matched evaluation protocol |

Start with Python as the already implemented structural baseline, then add
languages only as their extractor/platform cells pass. Endpoint/resource/test
relationships are mandatory coverage tracks, not optional promises deferred
indefinitely; completion for each cell requires actual discovery tests. If a
framework or language is unsupported, report it and keep that cell incomplete.

Pending core requirements are now FR-017–FR-028 / SC-008–SC-013 in Spec 042 and
T043–T060 in its canonical task inventory. CK0 verifies their contracts/register
before implementation. This supplements rather than silently redefines the
historical FR-011 graph gate; it does not amend the constitution, authorize paid
evaluation, select a release version or reopen historical phase 9 execution.

### Requirement/task and pilot dependency crosswalk

| Phase | Canonical tasks | Requirements | Click readiness |
| --- | --- | --- | --- |
| CK0 | T043–T044 | FR-017, FR-027 | Pinned contracts/lineage; no capability yet |
| CK1 | T045–T046 | FR-018 | Rich extraction prerequisite for C/D |
| CK2 | T047 | FR-019 | Coherent projections for C/D |
| CK3 | T052–T053 | FR-020 | Relevant structural queries for C/D |
| CK4 | T048–T051, T054 | FR-021–FR-023, FR-028 | T048–T051 required by B/D; T054 combined mode D |
| CK5 | T055–T056, T058 | FR-024–FR-026 | Operator inspection/lifecycle; not a substitute for capture |
| CK6 | T057, T059–T060 | FR-025, FR-027–FR-028 | Installed qualification and versioned readiness receipt |

Task dependencies, not numeric CK phase labels alone, govern execution. B does
not wait for structural query work: its formation/applicability tasks depend on
the shared contracts and existing authority. T060 can issue explicit partial
receipts after B's gates; it cannot close missing C/D, parity or usability gates.

## Verification and measurable benefit

Use synthetic fixtures only for deterministic plumbing and adversarial safety
tests. Use authentic repositories for extraction coverage and precision; audit
examples of missing/incorrect edges separately from passing graph mechanics.

Freeze matched task histories, commits, models, budgets and executable graders
before outcome evaluation. Compare native tools/no AtMem, current Code memory,
current syntax index, richer structure only, structure plus experience, a strong
repository-map control, and the pinned upstream code workflow in an isolated
benchmark environment. Report unresolved/withheld cases, not just successful
answers. No target fixes, future source or hidden tests enter memory/context.

Record task success and harm, total tokens/cost, cold/warm p50/p95 latency,
index/update time and resources, graph precision/coverage, stale context,
capture/delivery failures and raw receipts. Larger context or higher abstention
cannot hide regressions. Historical benchmark limitations and VibeMemBench
artifact-availability gates remain in force. No percentage improvement or
upstream parity is claimed until the corresponding measured gates pass.

## Definition of done

The user can index an authorized repository, inspect its typed source-linked
structure, run all six bounded query types, receive combined current knowledge
and applicable experience through an already qualified agent, change branches
or worktrees without cross-state confusion, and update/export/import/clear the
knowledge through AtMem. Tests prove the claimed language/platform combinations.
Copying a loader, renaming upstream code or returning an AST list is insufficient.
The Memory Explorer journeys and usability gates must also pass; a functioning
graph or unchanged search screen alone does not complete the transparency goal.
