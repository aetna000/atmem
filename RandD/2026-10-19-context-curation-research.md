# Context curation for AtMem Code

AtMem should offer ranked evidence discovery before source or experience details.
Experience remains visible as a bounded index; its full content is fetched only
when the coding agent selects it. The first implementation should need neither
a new model nor training. Learned output pruning and prompt-history masking are
separate, optional extensions.

This proposal targets `feature/atmem-code-2.3.9`, not stable 2.3.8 or the Laya
branch. It does not change release status or claim new benchmark results.

## Current evidence and implementation gaps

The latest five-task screen solved 5/5 tasks in both arms. Native input totaled
96,527 tokens versus 142,326 with automatic AtMem context, with median measured
context plus agent time of 46.77 versus 80.02 seconds. These are reused
engineering tasks, not an independent confirmation set. Fewer workspace calls
(24 versus 22) did not produce lower input consumption. See
[the completed screen](2026-10-19-full-query-context-correction.md).

On those recorded totals, removing 32.2% of current AtMem input would merely
reach native parity. Beating native input by 20% would require removing 45.7%
of current AtMem input. These calculations describe that run, not forecasts.

The existing product has useful foundations:

* `atmem/knowledge/code/mcp.py` already offers compact symbol search, bounded
  source retrieval, eight structural operations and an opt-in compact tool.
* `atmem/knowledge/code/packing.py` already ranks source evidence lexically,
  uses structural hints and fits excerpts to a UTF-8 byte budget. This is not
  a model-token budget or a separately queryable ranked discovery index.
* `atmem/code/experience_view.py:9` retrieves experiences with an additional
  case-insensitive substring filter. Its response includes observation text,
  anchors and execution evidence, rather than an index-only projection. It
  captures current source before constructing that response.
* `atmem/code/context.py:53` recalls memories and appends full record content
  into the automatic package. `atmem/code/hook.py` can return that package to
  the host. An index-first policy must change this path too, not only MCP.
* Existing source, lifecycle, scope, authorization and delivery checks should
  be reused. Prepared or stream-written receipts do not establish that an
  agent still has evidence in its active context.

## What the four approaches contribute

### Aider supplies a ranked navigation map

Aider derives definitions and references, builds a weighted file graph and uses
personalized PageRank influenced by files and identifiers in the conversation.
It renders selected definitions into a budgeted repository map. The map helps
the agent choose which files need deeper inspection; Aider supplies it with
change requests. Its implementation uses token counting or estimation when
fitting the map, rather than equating bytes with tokens.
[Repository map](https://aider.chat/docs/repomap.html),
[ranking and fitting implementation](https://github.com/Aider-AI/aider/blob/main/aider/repomap.py).

For AtMem, adapt the ranking idea to the existing graph, without installing
Aider as a second agent or duplicating repository extraction. Combine lexical
matches, explicitly mentioned paths/symbols and bounded graph proximity. Add
diversity so a highly connected utility does not occupy the whole result page.
Evaluate graph ranking against the existing lexical ranker; centrality alone
does not establish relevance.

Unlike Aider's automatic map, AtMem's default should be an on-demand code index.
Only the bounded experience index is eligible for automatic presentation.

### Claude-Mem separates an index from details

Claude-Mem documents progressive disclosure: compact observation metadata and
estimated retrieval costs first, then selected details, surrounding timeline
and original tool evidence. Session-start context can contain an index rather
than full histories. Its token examples illustrate the design; they are not
controlled whole-task coding benchmarks.
[Progressive disclosure design](https://github.com/thedotmack/claude-mem/blob/main/docs/public/progressive-disclosure.mdx).

AtMem should add a dedicated experience-index projection and exact authorized
fetch-by-ID. The index contains identity, bounded title, observed outcome,
age/revision, applicability status and estimated detail cost. It excludes full
observations, commands, stdout and stderr. A timeline is an optional bounded
request, not an automatic expansion of every hit.

Titles initially come from bounded existing intent text and observed outcomes.
Any later generated title is a derived summary linked to its source, not new
evidence. Index metadata must pass authorization and secret screening too.

### SWE-Pruner filters new code observations against a current goal

SWE-Pruner wraps reading tools with an optional goal question and selects code
lines using a trained Qwen3-Reranker-0.6B based skimmer. Its reported SWE-bench
Verified results are 353/500 to 351/500 solved with 23.1% fewer tokens for
Sonnet 4.5, and 277/500 to 274/500 with 38.3% fewer for GLM-4.6. These are
small solve-rate decreases, not universal performance improvements. The paper
describes teacher-generated queries and labels and focuses its implementation
on Python repositories.
[Paper and results](https://arxiv.org/html/2601.16746v1).

The released installation documents model downloads and a Flash Attention /
CUDA dependency. A later SWE-Pruner Pro approach adds backbone-specific pruning
heads, making it a different deployment proposition from portable MCP.
[Installation](https://github.com/Ayanami1314/swe-pruner/blob/public/swe-pruner/README.md),
[Pro implementation](https://github.com/Ayanami1314/swe-pruner-pro).

AtMem should first adopt the explicit goal contract, not a mandatory neural
dependency: the agent states its immediate information need; AtMem selects
bounded source windows and preserves exact line locations. Do not silently
rewrite native shell/read tools. An optional external pruner can later process
authorized AtMem source responses, with model revision, latency, retained
ranges and an exact full-source fallback recorded. Do not prune edit payloads
or treat omitted code as nonexistent.

Using the pretrained skimmer would include its existing generated-supervision
provenance. This proposal neither trains a model nor creates synthetic data;
the first implementation avoids that dependency entirely.

### Observation masking limits old output replay

The masking implementation replaces older environment observations with
placeholders while retaining the surrounding action/history structure. The
paper's main rolling window is ten turns. In its Qwen3-Coder configuration,
raw-agent solve rate is 53.4%, masking 54.8%, summarization 53.8%; masking costs
$0.61 versus raw $1.29 per instance. Another configuration loses solve rate,
so the method needs host/model-specific evaluation. The earlier chat comparison
incorrectly called 53.8% the raw baseline.
[Paper Table 1](https://arxiv.org/html/2508.21433v1),
[history processor](https://github.com/JetBrains-Research/the-complexity-trap/blob/main/sweagent/agent/history_processors.py).

AtMem can preserve authorized outputs and serve retrieval handles. Only a host
that controls prompt assembly can replace already-delivered output in later
prompts. Standard MCP alone cannot mask arbitrary native tool history.

Expose masking as unsupported unless a host integration demonstrates that
capability. Where available, keep a configurable recent window, preserve
system/user instructions and protocol-valid tool call/result pairs, and replace
older eligible output bodies with explicit, retrievable handles. Preserve
active constraints and unresolved errors through explicit retention policy.
Retained full evidence follows existing secret, storage and retention policies;
masking is not permission to archive everything indefinitely.

## Proposed architecture

Keep the existing store, graph and authority services. Add a presentation and
retrieval policy layer rather than another memory database.

1. A qualified session or task hook may present a small experience index. It
   never adds full experience details or raw execution output automatically.
2. The coding agent requests discovery when it needs code or past experience.
   AtMem searches authorized projections and returns a ranked, bounded index.
3. The agent selects identifiers and optionally a current goal question.
   AtMem rechecks authority and freshness, then returns only selected evidence.
4. A session ledger records presentation, delivery and explicit acknowledgments
   separately. Repeated unchanged evidence can be referenced instead of resent
   when the host confirms it remains available, or the agent opts into references.
5. Optional host integration can mask older retained tool output. Without it,
   AtMem confines optimization to its own responses.

Suggested additive operations on the existing compact `code_query` interface:

| Operation | Inputs | Output |
| --- | --- | --- |
| discover | query, code/experience/both, bounded limit, budget | Ranked IDs, short labels, source locations and estimated fetch costs |
| fetch | selected IDs, optional goal, budget | Authorized exact excerpts or experience details with provenance |
| changes | delivered evidence IDs and prior versions | Changed or withheld references and bounded updated evidence |

These are proposed operations, not current public commands. Raw execution
inspection retains its existing separate privileged boundary.

The experience index can be displayed to humans as a table and delivered to
models as compact JSON or text. Each row should expose:

* Opaque ID, kind and bounded title.
* Observed outcome, without promoting successful execution to a verified fix.
* Source revision/age and applicability: checked, stale, historical or unchecked.
* Short match signals such as identifier overlap or a referenced source path.
* Estimated detail tokens, estimator identity and an exact fetch reference.

Use a configurable aggregate index budget and a small row limit. Initial
experimental settings can be 256 estimated tokens and three rows, not a promise
that every tokenizer fits those values. Show a short availability/search hint
when no useful row exists. Never fill a quota with irrelevant history. Emit only
new or changed rows during a session unless explicitly requested or after
compaction. Full history remains discoverable by search.

## Ranking and duplicate handling

Build a scope-filtered SQLite search projection using FTS5 when available,
with a deterministic fallback for SQLite builds without it. Preserve the exact
source of truth and bind projection generations to it. Search must improve on
whole-query substring matching without introducing a new model requirement.

Rank code and experience separately before combining a bounded result page.
For code, test lexical matches plus personalized graph proximity. For experience,
test matching intent, affected paths/symbols, observed outcome and applicability.
Historical or failed attempts can be relevant, but must remain labeled as such.
Deduplicate overlapping spans or repeated experience references without merging
different claims or concealing contradictory outcomes. Ranking scores are not
calibrated probabilities and should not be presented as confidence in truth.

A delivery-ledger key needs subject/project/profile, host session, context
epoch, evidence ID and evidence version. Process restarts, explicit refetches and
compaction must allow full retrieval again. Native reads are unknown unless a
qualified adapter reports them. Never infer that a stream-written response is
still in the model's prompt. Avoid automatically suppressing an unchanged read
on that assumption.

## Freshness and latency

AtMem currently recaptures repository state for current graph and experience
checks. An index-only response should avoid constructing full experience details
and validating every matching receipt. It still must authorize and validate
lifecycle at delivery. If applicability has not been checked, mark it unchecked;
do not copy a previous applicable label and pretend it is current.

Benchmark projection queries, source checks, graph loading and serialization
separately. Reuse immutable snapshot computations only within a verified
generation. Watchers may help invalidate caches but cannot be the sole proof
that source is unchanged. A model-token estimator supplements, not replaces,
the existing UTF-8 byte safety ceiling.

## Implementation order

| Phase | Change | Completion evidence |
| --- | --- | --- |
| 1 | Experience index and authorized fetch; explicit index-only automatic policy | No experience bodies or raw output in hook/index responses; scopes and lifecycle enforced |
| 2 | Queryable ranked code index and goal-directed expansion | Exact source references; lexical versus graph-ranking ablation; bounded responses |
| 3 | Session evidence ledger and context epochs | Changed-source, compaction, restart, explicit refetch and cross-scope controls |
| 4 | Qualify host-specific history masking in an open harness | Actual before/after model prompts, valid tool pairing and recoverable evidence |
| 5 | Optional pretrained pruner service | License/weights review, installation isolation and measured net benefit |

Phases 1 to 3 require no GPU, fine-tuning, generated training corpus or new paid
provider. Phase 4 cannot be advertised uniformly across coding CLIs. Phase 5
must remain optional so the base install does not inherit Torch/CUDA requirements.

## Benchmark design

Use the existing five inspected tasks only for engineering. Freeze candidate,
ranking parameters, budgets and task-selection rules before evaluating new
tasks. Keep the official grader, same model and equal solver budgets. Report
all selected attempts, preparation failures and missing usage receipts.

First compare native, existing automatic content, and index-first AtMem. On
engineering tasks, isolate code indexing from experience indexing so gains or
overhead can be attributed. Add ledger, masking and learned pruning one at a
time rather than bundling every mechanism into a single candidate.

Use two complementary workloads:

* Cold issue resolution measures code discovery against competent native tools.
* Chronological project sessions measure whether genuine prior attempts and
  decisions avoid rediscovery. Only experience actually observed before the
  target task is eligible; no target solution, hidden test or future commit
  can seed memory. Include unrelated and stale history to test rejection.

For each arm measure full input and output usage, provider cache categories,
actual charge when available, total task time, index/setup time separately,
retrieval/pruning time and official solve rate. Token savings are not equivalent
to cost savings when caching differs. Do not add overlapping usage categories.
Keep auxiliary model/service costs in the comparison. Record context epochs,
index deliveries, detail fetches, full-source fallbacks and repeated source-span
delivery; fewer tool calls alone are not sufficient.

Report paired task differences and confidence intervals, clustered by task or
repository as appropriate. A small all-pass sample cannot establish equal
solve rates. Predeclare the acceptable quality margin and sample size before a
confirmation run. The user-facing efficiency target remains at least 20% less
complete input than native, with no observed solved-task regression in the
engineering gate and a sufficiently powered quality assessment before a broad
claim. If only a specific workload benefits, report that scope.

## Reuse and licensing

The inspected Aider and Claude-Mem root licenses are Apache-2.0; SWE-Pruner's
public branch and the masking research repository have MIT root licenses.
Pin exact revisions, inventory copied files and preserve required attribution
before incorporating implementation. Root code licenses do not establish
rights to every model weight, dataset or transitive dependency. The proposed
first phases can adapt these algorithms to existing AtMem services without
shipping any upstream runtime or model.
[Aider license](https://github.com/Aider-AI/aider/blob/main/LICENSE.txt),
[Claude-Mem license](https://github.com/thedotmack/claude-mem/blob/main/LICENSE),
[SWE-Pruner license](https://github.com/Ayanami1314/swe-pruner/blob/public/LICENSE),
[masking implementation license](https://github.com/JetBrains-Research/the-complexity-trap/blob/main/LICENSE).

## Decision

Implement index-first experience and ranked code discovery first, retaining the
existing authority boundary. Add explicit goal-directed fetch and a trustworthy
delivery ledger next. Treat masking as a qualified host capability and neural
pruning as an optional measured extension. This directly addresses duplicate
exploration and prompt growth without restarting the storage-model project.
