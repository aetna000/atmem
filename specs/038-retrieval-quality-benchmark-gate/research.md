# Retrieval Quality Research Basis

## Research question

What general memory mechanisms would allow AtMem to improve both compact
evidence question answering in LongMemEval-V2 and future tool action accuracy in
DolphinBench, without encoding benchmark answers or weakening AtMem's authority,
scope, lifecycle and evidence guarantees?

## Evidence reviewed

- AtMem LongMemEval-V2 development slice: 1/10 with governed retrieval versus
  2/10 without retrieval. AtMem frequently selected the correct application or
  trajectory but omitted the exact answer-bearing state or relation.
- LongMemEval-V2 paper and official implementation: five abilities across
  static state, dynamic state, workflow, gotcha and premise knowledge. Its
  AgentRunbook-R explicitly separates raw state slices, state-transition events
  and procedure/hint notes; AgentRunbook-C searches retained trajectories as
  files. Published results show the benefit of preserving more than flat
  semantic chunks.
- DolphinBench paper and official run evidence: the benchmark grades 600 tool
  actions depending on buried personal or organizational rules. The best
  official configuration at review time is Mem0 + Hermes + GPT-5.6 Luna at
  424/600, USD 96.21 and 37.7 seconds median task latency; the matched built-in
  memory scores 394/600.
- Mem0 paper: dynamic fact extraction and consolidation are core mechanisms,
  with a graph variant providing additional relational retrieval.
- HippoRAG 2: associative graph retrieval can improve multi-hop evidence
  discovery, but graph proximity remains nomination rather than proof.
- Ground-truth-preserving memory research: retained episodes reduce the risk of
  lossy extraction; adaptive retrieval and context formatting can contribute as
  much as ingestion changes.
- Supermemory Company Brain commit
  `d76cc1c9cc4fbddaf95f3a560edcaa04001c4dee`: explicit shared/personal/private
  memory containers, requester-derived read scope, deterministic source
  documents, purpose-specific memory tools, keyset pagination and a short
  setup journey. Its retrieval result remains primarily memory/chunk plus a
  combined relevance score, so it is a useful product-integration reference,
  not a substitute for typed support and sufficiency.
- Hindsight commit `ccfe85b4851957ac2adf88b4a9ddf9668b2882f1`:
  separate world facts, experiences, evidence-backed observations and mental
  models; parallel semantic, keyword, graph and temporal nomination; isolated
  banks; token budgets; and optional raw chunks/source facts. Its evidence
  linkage, retrieval budgets and simple retain/recall surface are useful
  patterns. AtMem must not copy model-owned authority, globally scored evidence
  as proof, or background belief rewriting without governed admission.

Primary references:

- https://arxiv.org/abs/2605.12493
- https://github.com/xiaowu0162/LongMemEval-V2
- https://arxiv.org/abs/2609.24971
- https://github.com/mem0ai/dolphinbench
- https://arxiv.org/abs/2504.19413
- https://arxiv.org/abs/2502.14802
- https://arxiv.org/abs/2604.04853
- https://github.com/supermemoryai/company-brain/tree/d76cc1c9cc4fbddaf95f3a560edcaa04001c4dee
- https://github.com/vectorize-io/hindsight/tree/ccfe85b4851957ac2adf88b4a9ddf9668b2882f1

## Diagnosis

### 1. Formation is the first bottleneck

The existing benchmark adapter converts trajectories into bounded text records.
When the record omits a resulting priority, a field label, a negative state or
the order connecting two steps, no later ranker can recover it. Increasing top-k
mostly adds more near-topic text and reader cost.

### 2. A universal memory shape is insufficient

These information needs have different minimal sufficient structures:

| Need | Required memory structure |
| --- | --- |
| Static state | entity + attribute + exact value + validity |
| Dynamic state | before + action + after + event time |
| Procedure | ordered steps + preconditions + branches + completion |
| Gotcha | trigger + failed approach + observed failure + working exception |
| Premise | proposition + applicability/negation + evidence |
| Personal rule | subject + condition + required/prohibited action + validity |

A flat chunk may contain these fields, but it does not make their relationship
stable or retrievable.

### 3. Candidate relevance and answer sufficiency are different decisions

Semantic, lexical, graph, recency, frequency and importance signals can nominate
useful candidates. They do not prove that a candidate answers the requested
relation. AtMem's existing bounded age/residence checks demonstrate the idea but
cannot scale as a list of hand-written attributes. Sufficiency must operate over
typed slots and linked source evidence.

### 4. Evidence neighborhoods matter

The useful answer may be in an adjacent UI state, the next action, a previous
failed attempt or a condition stated before a rule. Ranking independent chunks
discards that topology. Expansion must follow recorded source adjacency and
typed relations under strict budgets, not unrestricted similarity.

### 5. Context is an optimization problem, not just top-k

The reader needs complementary evidence: label plus value, action plus outcome,
rule plus condition, or steps in order. Packing four high-scoring paraphrases is
worse than selecting a lower-ranked complementary record. The packing objective
must cover required evidence slots, conflicts and provenance within a token
budget.

### 6. End-task scores need stage-level diagnosis

LongMemEval can fail because formation lost the answer, retrieval missed it,
packing obscured it, or the fixed reader failed. DolphinBench can additionally
fail because the agent ignored correct memory or chose the wrong tool. The paper
must report these stages separately rather than attributing every task failure
to retrieval.

### 7. The first experimental adapter is not yet an inert benchmark rig

The development fork's `memory_modules/atmem.py` currently creates fixed-size
text chunks, filters accessibility-tree lines, accesses stores/indexes directly
and labels trajectory content as a user message. That is useful evidence about
the plumbing experiment but violates the product-API boundary in this spec and
can remove exact answer-bearing state before AtMem sees it. The production
adapter must become a lossless mapper into `episode-ingest-v1`; all formation,
indexing, retrieval and packing belong to installed AtMem product code.

### 8. The current hybrid collector has a known scale blocker

The present `atmem/retrieve/hybrid.py` loads all authorized records, constructs
an in-memory FTS table for every query and refuses corpora above 10,000 records
or 8 MiB. Typed formation increases record count, so persistent exact/FTS
nomination and bounded canonical reloads are a correctness prerequisite, not a
post-benchmark micro-optimization.

## Product provenance for the typed ontology

The seven public kinds are not runtime aliases for LongMemEval categories.
They arise from recurring product evidence in at least two ordinary domains:

| Kind | Personal/assistant example | Operational/workflow example |
| --- | --- | --- |
| Atomic fact | age or food preference | customer account identifier |
| Durable rule | dietary restriction | deployment channel policy |
| Environment state | selected local model | CRM record current status |
| State transition | preference correction | document upload before/after |
| Ordered procedure | recurring travel booking steps | release or provisioning runbook |
| Failure/gotcha | tool fails under a local setting | timeout after ambiguous external side effect |
| Premise/applicability | feature absent from a local install | rule applies only to production releases |

Fixture wording and runtime routing use these product concepts. Benchmark
ability labels, application names, question IDs and inspected answers are
forbidden from product code.

## Chosen theoretical model

Use a **ground-truth-preserving typed episodic memory**:

```text
immutable source episode
        |
        +--> typed proposals
               fact / rule / state / transition / procedure / gotcha / premise
        |
        +--> canonical admission and reconciliation
        |
query --> information need --> independent nominations
        --> source/graph/temporal neighborhood expansion
        --> sufficiency slots and contradiction check
        --> budgeted structured context
```

Raw source evidence and typed derived memory have different purposes. Source
evidence preserves truth and permits reconstruction. Typed memory makes the
relation retrievable. Neither substitutes for the other.

## Hypotheses

- **H1 Formation:** Typed state/transition/procedure/rule formation increases
  answer-bearing evidence coverage over fixed character chunks.
- **H2 Routing:** Information-need-aware retrieval outperforms one universal
  ranking profile under the same context budget.
- **H3 Neighborhood:** Bounded adjacency expansion improves dynamic, procedure
  and gotcha tasks more than increasing global top-k.
- **H4 Sufficiency:** Slot-based sufficiency reduces topical false positives and
  prevents incomplete direct-support context.
- **H5 Packing:** Complementarity-aware packing improves fixed-reader accuracy
  while using no more context tokens than score-only top-k.
- **H6 Governance:** Authority-first filtering and final revalidation can remain
  quality-neutral while preventing cross-persona, stale and revoked evidence.
- **H7 Efficiency:** Deterministic local nomination plus optional bounded
  intelligence can create a better accuracy/latency/cost point than agentic
  file search for common queries.

## Rejected primary strategies

### Increase top-k

Rejected as the main solution. It cannot recover missing structure, increases
reader tokens and can crowd out complementary evidence.

### Add more weighted ranking signals

Rejected without ablation. Scores such as importance, use frequency, planner or
critic opinion can amplify a malformed memory and are not authority or
sufficiency evidence.

### Summarize every history into prose

Rejected as the canonical representation. It is lossy for labels, numbers,
negation and order, and makes correction provenance difficult. Summaries may be
derived views with exact source links.

### Make a graph the authority

Rejected. Graph extraction can be incomplete or wrong. It is useful for
nomination and neighborhood traversal only; canonical evidence and lifecycle
remain authoritative.

### Use an LLM for every query

Rejected as the base path because it weakens local-first operation, increases
cost and latency, and complicates reproducibility. Optional intelligence may
classify, propose or rerank bounded authorized content.

### Repair answers inside benchmark adapters

Rejected categorically. It would measure the harness rather than AtMem and make
the feature unavailable to normal agents.

## Product lessons adopted from open source

### Adopt

- Make the common product surface small: form/retain, recall, explain and
  rollback. Advanced channel and sufficiency details remain inspectable without
  becoming mandatory setup concepts.
- Derive readable scope from the authenticated requester and show the active
  private/shared boundary before activation.
- Preserve deterministic source documents and stable source identifiers before
  derived formation.
- Expose purpose-specific retrieval affordances and descriptions so an agent
  knows when it needs a quick fact, a procedure, or a deeper evidence search.
- Use bounded parallel nomination, token budgets, cursor pagination and cached
  read models instead of whole-store UI reads.
- Keep source facts/chunks available behind the compact result when authorized,
  and identify explicitly when the source budget was truncated.

### Deliberately do not adopt

- A single combined relevance score as evidence that a question is answered.
- An LLM extraction or consolidation result writing directly to authoritative
  memory.
- Co-occurrence graph proximity as a typed relationship or causal claim.
- One implicit shared brain without AtMem's agent/workspace/subject boundary and
  explicit sharing policy.
- Product setup that requires a hosted memory service, provider API, external
  graph server, container runtime or benchmark repository.

These decisions leave room for a paper contribution while improving the daily
product: source-grounded typed units, loss receipts, sufficiency states and
action constraints are user-visible capabilities, not leaderboard-only code.

## Experiment logic

The causal ablation order is:

1. Current fixed chunks + current retrieval.
2. Typed formation + current retrieval.
3. Add information-need routing.
4. Add neighborhood expansion.
5. Add sufficiency checking.
6. Add complementarity-aware packing.
7. Add optional intelligence only if it improves a predeclared metric.

Each arm uses the same source corpus, authority state, context budget, reader,
judge and scorer. This order distinguishes improvements caused by better memory
objects from improvements caused by retrieval or reader prompting.

## Threats to validity

- Public benchmark labels can leak into design decisions; use frozen
  development/confirmation boundaries and reset confirmation after inspection.
- Model/provider aliases can change; pin provider, model identity and raw
  request evidence.
- DolphinBench varies harness and model; only matched pairs isolate memory.
- LongMemEval answer accuracy does not prove real action quality; DolphinBench
  supplies external validity.
- DolphinBench action accuracy does not isolate retrieval; retain memory-call
  evidence and stage outcomes.
- Optional LLM formation may introduce nondeterminism; preserve proposal bytes,
  model identity and repeated-trial policy.
- Benchmark workloads may reward patterns not representative of all customers;
  public claims must name their scope.
