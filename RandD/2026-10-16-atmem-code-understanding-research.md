# AtMem Code: from shared notes to maintained engineering knowledge

> **Decision update, 2026-10-16:** the owner subsequently selected source-level
> incorporation and adaptation into an AtMem-owned implementation, rather than
> an external Cognee integration or concept-only implementation. The research
> below is retained as historical analysis; its optional-backend recommendation
> is superseded by the source-incorporation planning addendum in
> [spec 042's plan](../specs/042-atmem-code/plan.md#proposed-extension-source-incorporated-atmem-knowledge).

Date: 2026-10-16 (Australia/Sydney). Research and architecture proposal, not an
implementation, release commitment, benchmark result, or claim of superiority.
The current Code work remains on `feature/atmem-code-2.3.9`; main and the Laya
work are outside this proposal. This review does not authorize phase 9 execution.

## Recommendation

Use current Cognee as a replaceable, optional derived code/knowledge retrieval
backend. Do not fork its entire platform, replace AtMem's canonical store, or
add both Cognee and Graphiti by default. Evaluate a smaller direct-Enola path
alongside the Cognee path, because current Cognee already delegates code
extraction to Enola. Add LSP resolution only where it improves a task.

The proposed product wedge is **revision-aware, evidence-backed engineering
experience, delivered with current-code context to different agents**. An agent
should receive what applies now, why the team believes it, what evidence exists,
which previous attempts failed, and what remains uncertain. A graph and an
audit log alone do not establish that this is better than competing products.

Do not promise generic '10x intelligence'. Define a measurable workflow
improvement, compare with a well-configured current competitor, and retain the
option to conclude that the lightweight baseline is better.

## Research scope and immutable source inventory

Public repositories were cloned for read-only inspection under
`/tmp/atmem-code-research.yKNuul`. No competitor dependencies, binaries, model
weights or services were installed or executed. Papers were read through their
HTML architecture, evaluation, analysis and limitations sections. This is source
analysis, not a reproduced experiment. Current-main code is not automatically a
released package: the versions below are declarations in the inspected source.

| Project | Inspected commit | Main files inspected |
| --- | --- | --- |
| Serena | `2cb6cabc100539a1364bc243b543e664f0fa8f43` | `LICENSE`, `src/solidlsp/ls.py`, `src/serena/memories/memory_manager.py`, `memory_reference_analysis.py`, README |
| Aider | `5dc9490bb35f9729ef2c95d00a19ccd30c26339c` | `aider/repomap.py`, repo-map technical explanation |
| RepoGraph | `6c3977d87845993bf2c0359b4ac752278d7f3c45` | `repograph/construct_graph.py`, `graph_searcher.py`, paper |
| Cognee | `f154b32a9e544dac73e7ddf2010327cf9988edcd` | Source declares 1.6.4; remember/recall/search APIs, code extraction and retriever, temporal contradictions, improve config, deletion APIs, permissions, pyproject, code example |
| Graphiti | `aca369364226a666ca541b061ff2a1a54b80f2ff` | Source declares 0.31.0; `graphiti_core/edges.py`, `graphiti.py`, temporal helpers, README |
| ByteRover | `1052ac1a5dd0fde4da8693d4712064f7876c269c` | README, license, curation/context-tree source inventory, paper |
| Mem0 | `0724291bd864cf807e88ee8981c8226644e8fb42` | Source declares 2.2.1; `mem0/memory/main.py`, scope/filter and write/search paths, paper |

AtMem source checked: `atmem/code/{formation,graph,context,providers}.py`,
spec 042 and its benchmark protocol. Relative source paths above are within each
respective repository; they are not claims that the entire repository was read.

## What each reference teaches us

### Serena and Aider: current code before historical prose

Serena exposes symbol-oriented navigation backed by language servers and also
has persistent memory facilities. Its actual language/backend capabilities vary;
an LSP reference is not a universally complete call graph. Aider builds compact
repository maps from parsed definitions/references, uses graph ranking informed
by active/mentioned files and identifiers, and budgets the output. Its current
source caches parsed tags by file modification time. Neither should be reduced
to 'just keyword search'.

Use a parser-backed compact map for cheap coverage and on-demand symbol
resolution for precision. Do not build a new editor, refactoring engine or
language-server ecosystem to compete with their mature tooling.

Sources: [Serena](https://github.com/oraios/serena),
[Aider explanation](https://aider.chat/2023/10/22/repomap.html),
[Aider implementation](https://github.com/Aider-AI/aider/blob/5dc9490bb35f9729ef2c95d00a19ccd30c26339c/aider/repomap.py).

### RepoGraph: retrieve relationships, not only similar text

The paper studies repository graphs integrated with software-engineering
frameworks. Its implementation offers bounded neighborhood and traversal
operations. The useful lesson is to expand around relevant definitions and
references, then deliver selected evidence rather than a whole repository.
Published improvements belong to its evaluated models, tasks and integrations;
they are not expected AtMem gains. Syntax/name matching must not be represented
as compiler-confirmed identity or runtime behavior.

Source: [paper](https://arxiv.org/html/2410.14684v1),
[implementation](https://github.com/ozyyshr/RepoGraph).

### Cognee: a capable platform to reuse, not a straw-man baseline

Current source already exposes deterministic `SearchType.CODE` over an
Enola-derived graph: facts, architecture, paths, impact, insights and deltas.
The code route can avoid LLM and embedding calls. It records snapshot receipts,
updates stale graph material and caches dataset/database-specific graph views.
Cognee also has permissions, deletion, temporal and feedback mechanisms.

The 2025 paper studies configurable graph/LLM QA on small filtered train/holdout
sets; it does not evaluate this newer complete code stack. Its headline tuning
ratios are not evidence of current coding productivity or a weakness AtMem has
already surpassed. We must compare against current recommended code/recall
configurations, not that older paper's default conversational configuration.

Sources: [current code example](https://github.com/topoteretes/cognee/blob/f154b32a9e544dac73e7ddf2010327cf9988edcd/examples/guides/code_graph_example.py),
[code retriever](https://github.com/topoteretes/cognee/blob/f154b32a9e544dac73e7ddf2010327cf9988edcd/cognee/modules/retrieval/code_retriever.py),
[paper](https://arxiv.org/html/2505.24478v1).

### Graphiti: time is part of a fact's meaning

Graphiti distinguishes fact validity and recording/expiration metadata, tracks
source episodes and reconciles new relationships with prior ones. Reuse the
design principle that previous knowledge is not silently overwritten. However,
code applicability also depends on commits, worktrees, dirty files, build
configuration and platform: timestamps alone cannot establish current validity.
Do not add a second temporal graph service before the Cognee/AtMem boundary has
demonstrated a gap requiring it.

Sources: [Graphiti](https://github.com/getzep/graphiti),
[Zep paper](https://arxiv.org/html/2501.13956v1).

### ByteRover and Mem0: record shape and write semantics matter

ByteRover describes hierarchical curation, progressive retrieval and operational
feedback. Its paper also acknowledges write cost, cache-miss retrieval cost and
unisolated write-component contributions. These are design trade-offs, not
grounds to assume a graph is superior to a context tree.

Mem0's 2025 paper describes extraction and state-aware operation selection.
The inspected current source differs: its V3 path retrieves existing memories,
performs additive extraction, batches embeddings/persistence and hash-deduplicates.
Explicit update/delete APIs still exist. A source-pinned baseline must specify
which path it actually ran rather than attribute the old paper's pipeline to
every current installation.

Sources: [ByteRover paper](https://arxiv.org/html/2604.01599v1),
[ByteRover source](https://github.com/campfirein/byterover-cli),
[Mem0 paper](https://arxiv.org/html/2504.19413v1),
[current Mem0 write path](https://github.com/mem0ai/mem0/blob/0724291bd864cf807e88ee8981c8226644e8fb42/mem0/memory/main.py).

### VibeMemBench: helping execution is different from remembering

Its selected targets test memory interventions on executable repository tasks.
The paper distinguishes direct verified-experience injection from memory systems
that must ingest/retrieve history themselves. Many evaluated combinations do not
beat memory-off. Record-form degradation is a major diagnostic finding, but its
attribution has limited rater agreement; it is a hypothesis to test, not a proven
universal explanation. Reported solver tokens exclude memory-side computation.

The public linked README still says **Coming**, checked during this review.
Runnable targets, histories, graders and data terms were not available there.
Treat this as an evaluation protocol reference until artifacts are released.
Do not manufacture a 'VibeMemBench reproduction'.

Sources: [paper](https://arxiv.org/html/2609.23570v1),
[current release placeholder](https://raw.githubusercontent.com/AlibabaResearch/DAMO-ConvAI/main/VibeMemBench/README.md).

## What AtMem currently has—and lacks

Existing foundations: encrypted canonical storage, scoped project/profile/agent
memory, lifecycle/source metadata, portable encrypted bundles, local management,
bounded context packages, provider routing and a qualified subset of automatic
agent adapters. These are foundations, not proof of leadership.

Current limitations directly visible in source:

- `formation.py`: bounded English explicit-user-statement rules; tool outcomes
  are not automatically promoted to verified engineering experience.
- `graph.py`: Python AST definitions/imports and syntax-only call references;
  other accepted text languages are file-level entries. It is not a resolved
  multi-language semantic graph.
- `context.py`: whole-repository revision/dirty checks withhold source-dependent
  assertions. This is conservative but loses useful context after unrelated edits.
- `providers.py`: a governed delegated-context routing boundary exists, but it
  is not yet a generic symbol/evidence/experience query planner.
- Host qualification remains incomplete. MCP availability does not imply
  automatic capture or injection in all agents.

## Proposed architecture: one authority, several rebuildable views

1. **Code sources and manifests.** Git/worktree source remains authoritative for
   current implementation. Capture repository identity, commit, dirty-source
   digest, dependency lockfiles, parser/tool versions and per-file hashes. Store
   the manifest/source catalog in AtMem; do not duplicate every source file as a
   canonical personal-memory fact.
2. **Evidence ledger.** Record authorized user statements, diffs, CI/local test
   results and supported agent events with exact provenance. Only ingest sources
   actually exposed and authorized by that integration. Historical instructions
   and tool output are data, not current execution authority.
3. **Engineering claims and experiences.** AtMem owns attributed decisions,
   constraints, failed attempts, fix patterns and their lifecycle. Separate
   reported rationale, structural observations, hypotheses and bounded verified
   results. A commit message or 'fixed' utterance is not test attestation.
4. **Derived retrieval.** An optional Cognee worker indexes authorized immutable
   source snapshots and accepted knowledge projections. A direct Enola/lightweight
   map path competes as a lower-complexity implementation. LSP resolution enriches
   selected ambiguous symbols. Each backend returns structured evidence IDs,
   locations, relations and extraction provenance—not unrestricted generated
   memory mutations.
5. **Task context planner.** Combine lexical/symbol search, bounded graph
   expansion, relevant decisions and conditional experiences. Deduplicate across
   providers, prioritize under the agent's token budget, progressively disclose
   details, and explicitly return no memory when evidence is inadequate.
6. **Delivery and inspection.** A single versioned contract serves CLI, MCP/API,
   dashboard and qualified hooks. Explain what was included/withheld and why.
   Basic generic access and tested automatic integration are separate claims.

AtMem remains the authorization/lifecycle authority for its knowledge, not an
arbiter that makes Git source or a model-inferred explanation automatically true.
Optional review queues can stay off; scope, secret and source-validity checks do
not disappear when review is off. No Laya activation or model retraining is needed.

### Experience record: preserve the engineering lesson

A proposed record contains: observed symptom, relevant source anchors, reported
or established cause, attempted approaches, exact successful change reference,
applicability conditions, platform/dependency constraints, test command/result
and environment digest, verification revision, evidence IDs, contradictions and
supersession links. Keep fields absent when unsupported; never fill them with
invented explanations.

For example, an observed Windows-locking fix should carry its exact patch and
reproduction evidence. A later Mac-only refactor must not receive 'always use
this workaround' merely because both tasks contain 'locking'. The benefit is
reusing the applicable lesson without inheriting unrelated historical commands.

### Freshness: dependency-aware, not optimistic

Track file/symbol/config dependencies and relation assurance (syntax, resolver,
observed runtime). Detect renames, deletion, changed imports, dependency versions,
different worktrees and incompatible build options. A source hash unchanged is
evidence of unchanged text, not a proof of unchanged behavior through dependencies.
Distinguish `source_current` from `tests_verified_at_revision`; never imply tests
were rerun merely because a source dependency still matches. Unknown resolution
or failed revalidation produces an explicit qualification or withheld item.

## How to integrate current Cognee safely

Use the code API shape documented by the pinned source as a spike candidate:
`remember(authorized_snapshot, content_type="code")` followed by scoped
`search(query_type=SearchType.CODE, code_query=...)`. This is illustrative, not
an installed AtMem command or a guarantee that a stable release exposes every
inspected-main operation. Richer semantic retrieval stays an opt-in lane with
approved model/embedding configuration. Pin the release, Enola binary and schema.

Requirements before adding it to the product:

- **No default user/dataset fallback.** Map explicit AtMem subject/project/profile
  and snapshot to explicit Cognee user/dataset scope. Gate before indexing and
  retrieval; post-filtering cannot undo unauthorized data access or model egress.
- **No cross-scope graph expansion.** Every returned node, relation and evidence
  endpoint must remain authorized, not just the initial query seed. Cross-repo
  graph joins require explicit membership permissions.
- **No two semantic writers.** Cognee inference produces candidates or derived
  retrieval views. AtMem applies accepted changes once. Disable independent
  auto-improve/curation where it would bypass that boundary; test its configuration
  rather than relying on the word 'derived'.
- **Transactional outbox, not a distributed transaction claim.** Commit a scoped
  index event with canonical changes. Worker keys include source ID, version and
  operation; replay is idempotent. Acknowledge applied generations. Atomically
  publish coherent snapshots, reject mixed-generation results, and rebuild views.
- **Deletion and cache correctness.** Canonical tombstones immediately prevent
  delivery; invalidate result and provider caches by scope/permission epoch.
  Track provider deletion/rebuild completion separately. Old worker retries must
  not resurrect deleted records. Document backup retention and restore filtering.
- **Protect all copies.** SQLCipher does not encrypt Cognee's independent graph,
  vector files, snapshots, temporary files or logs. Use a proven protected-storage
  design or an explicit, accurately labelled derived-cache option; do not silently
  downgrade the existing encrypted-memory guarantee. Loopback alone is not auth.
- **Process and dependency isolation.** A separate optional worker environment
  avoids burdening the base install with the full graph/vector/model stack.
  Use explicit data paths and credential/egress allowlists, bounded queues and
  deadlines, limited read roots and no arbitrary user-supplied Cypher execution.
  Disable optional telemetry explicitly, clear inherited remote-client routing,
  and test network behavior; 'keyless code mode' is not a no-egress guarantee.
- **Fail safely.** If Cognee is unavailable, use the authorized lightweight path
  or return no supplemental context. Do not block ordinary coding indefinitely.

Cognee already implements several backend correctness mechanisms; the work here
is the **end-to-end AtMem contract**, not claiming those mechanisms are absent.
The reviewed source also offers unified `forget` and staged incremental updates;
test the supported, pinned scoped operation rather than using a deprecated
delete wrapper or globally pruning the provider. The adapter may need to remove
and rebuild one isolated derived dataset when item-level provenance cannot be
mapped safely. Do not promise a narrower deletion receipt than the backend proves.

## Reuse and licensing boundaries

Cognee and Enola declare Apache-2.0. Inspect exact release licenses, notices,
transitive packages and generated artifacts before redistribution; contribute
backend fixes upstream rather than maintaining a platform fork.

Current Serena is split: SolidLSP is MIT; the application is GPL-3.0-or-later.
Prefer an independently installed Serena integration or carefully scoped
SolidLSP reuse with its notices, rather than silently copying application code
into AtMem's Apache-licensed distribution. Process separation is an architectural
choice, not a substitute for reviewing distribution obligations. ByteRover's
Elastic-2.0 source is a design reference, not unrestricted reusable code.

Sources: [Serena license](https://github.com/oraios/serena/blob/2cb6cabc100539a1364bc243b543e664f0fa8f43/LICENSE),
[Cognee license](https://github.com/topoteretes/cognee/blob/f154b32a9e544dac73e7ddf2010327cf9988edcd/LICENSE),
[Enola](https://github.com/enola-labs/enola),
[ByteRover license](https://github.com/campfirein/byterover-cli/blob/1052ac1a5dd0fde4da8693d4712064f7876c269c/LICENSE).

## Make '10x' a falsifiable goal

Leadership should mean useful solved work per total budget, fewer harmful
memories and less developer re-explanation—not ten features in one installer.
No speed, quality or cost advantage has been measured in this review.

Potential hypotheses, to preregister individually rather than cherry-pick later:

| Hypothesis | Honest measurement |
| --- | --- |
| Tenfold fewer stale/inapplicable context deliveries | Error counts on matched change sequences, including abstention/coverage and uncertainty; do not report a ratio when the baseline is zero or nearly zero |
| Tenfold less recurring project re-explanation | Time/turns in a defined repeated multi-agent workflow; include setup and human review, and verify equal task quality |
| Tenfold cheaper specific repeated context operation | Equal-evidence warm queries versus tuned Cognee; report cold indexing, update, cache misses, hardware and amortized total cost separately |
| Better coding outcomes | Held-out paired executable task resolution, repeated seeds, negative transfer and regressions, not just retrieval or judge agreement |

Tenfold lower warm latency against a deterministic cached CODE route may be
unrealistic. If the data do not support it, publish the actual delta. Do not
convert a selected workflow ratio into '10x better than Cognee'.

## Staged plan and decision gates

**A — Reuse feasibility.** Compare standalone current Cognee CODE and direct Enola
on authorized public repositories. Verify structured output, revision identity,
incremental updates, rename/delete behavior, and Mac/Windows/Linux install burden.
Gate: keep Cognee only where it provides useful additional capabilities at an
acceptable measured cost. Test fixtures must not invoke examples' destructive
global prune calls against owner state.

**B — Authority-safe adapter.** Build/pin the optional worker contract, source-ID
mapping, outbox/generation checks, permission-before-query and deletion barrier.
Gate: adversarial scope tests, killed/restarted worker, index replay, stale cache,
concurrent updates, backup restore and unavailable provider cannot leak or revive
withheld knowledge. Encryption claims must cover actual persistent copies.

**C — Current-code context.** Add multi-language structure through the selected
backend, compact map fallback, progressive symbol expansion and dependency-aware
freshness. Gate: paired localization/context precision against strong native
rg/LSP and map controls; protect quality when the graph is incomplete.

**D — Conditional engineering experience.** Ingest real authorized prior work;
connect decision/failure/fix records to evidence with bounded verification states.
Gate: no unsupported cause/fix promotion, measurable preservation of useful repair
conditions, and correct handling of contradictory or failed attempts.

**E — Product integration.** A simple opt-in setup selects an available backend;
dashboard exposes memory, code map, evidence, freshness and per-agent capability
status. Complete supported host onboarding, enable/pause/restore and cross-agent
handoff. Gate: actual normal-user journeys, not fixture bypasses. Keep default
deterministic memory behavior compatible; do not introduce Laya silently.

**F — Comparative evaluation, separately authorized.** Freeze configurations after
a development phase. Include memory-off with strong ordinary tools, Aider map,
Serena, recommended Cognee CODE/appropriate semantic configuration, current AtMem,
enhanced AtMem without Cognee and enhanced AtMem with Cognee. Use the same solver,
repo state, budget, tool availability and history cutoff. Compare both delivered
context under a common harness and full product operation, clearly separated.
For the direct Cognee comparison, hold the Cognee/Enola extraction, index and
retriever configuration fixed and add AtMem's context shaping, applicability
checks and engineering experience in separate arms. Otherwise an improvement
cannot be attributed to AtMem rather than a different backend configuration.

Evaluate repository-held-out authentic tasks and chronological histories; test
labels, target fixes, hidden tests and future conversations stay evaluator-only.
An unfiltered issue cohort is required alongside any uplift-selected benchmark.
VibeMemBench runs wait for runnable licensed upstream artifacts. Do not use its
verified-experience injection as an AtMem retrieval score.

Primary outcome: paired executable resolution with repository/task-clustered
uncertainty and a preregistered practical margin. Also report harm where memory
turns a baseline success into failure, context coverage and abstention, wrong-scope
and stale deliveries, full ingestion/update/rerank/solver token and compute cost,
cold/warm p50/p95 latency, hardware and installation footprint. Ablate structure,
experience shape, freshness and gating separately. A local test receipt does not
establish causality or generalization by itself.

## Research contribution versus product differentiation

Graphs, provenance, temporal updates, compact maps, feedback and cross-agent MCP
are established ideas. Potential contribution: a precisely specified
revision-dependent engineering-experience contract, enforceable lifecycle across
derived providers, and evidence that this integration improves downstream work
without increased negative transfer. That contribution must be demonstrated,
not inferred from architecture diagrams or the number of reused libraries.

## Claude review and revisions

The read-only Claude CLI review **completed successfully** using the exact model
`claude-opus-5-5`, effort `medium`, only Read/Glob/Grep tools, no MCP servers and
no session persistence. The CLI reported canonical model `claude-opus-5-5`,
`is_error=false`, terminal status `completed`, no permission denials and no spawned
subagents. Reported elapsed time was about 193 seconds. This is a second-model
source review, not independent experimental reproduction or academic peer review.

Reviewer conclusions incorporated:

1. Current Cognee already covers many proposed generic features. Competing with
   an old paper/default configuration would make the comparison invalid.
2. Preserve an untrusted-derived-backend boundary and verify every returned
   evidence item against authorized canonical knowledge/source manifests. Index
   ownership is not proof of truth; scoped rehydration and deletion matter.
3. Make per-anchor applicability across branches/worktrees the specific gap to
   investigate, not temporal timestamps or provenance alone.
4. Attach revision/environment-scoped test evidence without promoting it to a
   universal engineering rule. Preserve reported versus observed distinctions.
5. Test structure extraction quality, including unresolved identities and node
   collapse, before relying on it for impact or current-source claims.
6. Use offline retrieval diagnostics before expensive agent runs. Run a small
   paired pilot to estimate variance before freezing the larger comparison.
7. A tenfold claim requires a named metric, uncertainty, noninferior task quality
   and bounded negative transfer—not a generic '10x understanding' headline.

The report consequently recommends a Cognee-versus-direct-Enola feasibility
gate, no default Graphiti service, explicit worker-egress/telemetry controls,
per-anchor freshness, a shared-backend ablation, and no changes to the already
agreed phase-9 execution deferral. No product code, current installation or
owner memory was changed by this research.
