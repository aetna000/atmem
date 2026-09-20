# Governed Agent Memory with Structured Judgment: An AtMem–Jev Retrieval Study

## Abstract

Long-term memory can help an AI agent answer questions beyond its current conversation, but a relevant search result is not automatically current, authorized, or useful to the final answer. AtMem is an open-source memory and execution-evidence system that separates candidate discovery, answer support, authorization, and context delivery. We investigate whether Jev, TypeSafe's structured judgment model, improves the ordering of candidates that AtMem has already retrieved. In an exploratory evaluation of 1,986 LoCoMo questions, Jev reranking of AtMem's top ten candidates increased mean reciprocal rank at five (MRR@5) from 0.4259 to 0.5868 and Recall@1 from 0.3399 to 0.5423. Recall@10 remained 0.6495, consistent with reranking rather than finding new evidence. This study measures cited-evidence retrieval, not generated answer quality. Four upstream evidence-reference anomalies and remote-request latency limit the claim. The results motivate a full agent-level evaluation in which Jev's judgment remains subordinate to AtMem's memory authority.

## 1. Introduction

An agent asked “Which editor do I prefer?” may have several plausible memories: an early statement naming Vim, a later correction naming VS Code, and a project document mentioning both. Returning the first word match is inadequate. The system must determine which record answers the question, which source is current, whether the agent may access that record, and whether selected context reached the model.

AtMem addresses these questions as an **open-source, Apache 2.0-licensed memory control plane and Agent Black Box**. It integrates with OpenClaw, Pydantic AI, LangChain/LangGraph, and custom agent hosts. The host runs the agent and supplies identity and observed model/tool boundaries. AtMem stores canonical memory, governs its lifecycle, prepares context, and records evidence of supported exposure. AtBot, a separately packaged companion installed with AtMem, can propose or rank memory; AtMem retains authority over storage, correction, scope, and delivery [1]. The project's objective is useful long-term memory whose influence can be inspected and stopped for future runs, within the limits of what the connected host actually records.

This paper examines a narrow addition to that architecture: **Jev as a candidate reranker**. Jev is TypeSafe's externally provided model for structured judgments over application-defined options [2]. We test whether it can place cited evidence higher among AtMem's retrieved records. The measured outcome is evidence rank; whether the intervention improves the agent's final answer remains untested.

## 2. Why add a judgment model?

Retrieval has two distinct failure modes. A **candidate failure** occurs when the needed record never enters the search result. A **ranking failure** occurs when that record is present but appears below weaker candidates. There is also an independent **authority problem**: a relevant record may be expired, superseded, excluded, or outside the current agent's scope. Relevance cannot be interpreted as permission.

A reranker can address the second failure mode within a bounded candidate set. It cannot recover a missing candidate or establish that one is true and authorized. Our design therefore assigns Jev the judgment task while AtMem enforces governing rules. This preserves AtMem's separation of candidate generation, original-query support, authorization, and context construction [3].

The wider research goal is an agent that receives **useful, timely, attributable memory** without losing correction history, deletion, workspace isolation, or proof of delivery. Jev is one possible intelligence component for improving utility. It is neither AtMem's memory store nor the authority that permits context injection.

## 3. AtMem architecture

AtMem has four relevant layers. They remain separate in the product even when an experiment exercises only part of the system.

| Layer | Responsibility | Evidence |
|---|---|---|
| **Agent host** | Supplies agent/workspace identity; requests context; injects approved text; reports model and tool boundaries. | Integration contracts [1] |
| **Canonical memory** | Stores records, sources, trust, lifecycle, corrections, exclusions, and deletion state. | Memory and SQLite implementation [1, 4] |
| **Derived retrieval** | Nominates candidates from text, structured facts, optional semantic vectors, and selected graph paths. | Retrieval implementation [3–5] |
| **Decision and evidence** | Classifies original-query support, revalidates records, bounds context, and records supported exposure. | Retrieval and host contracts [1, 3] |

### 3.1 Write path and lifecycle

A candidate memory may come from an authenticated user turn or another admitted source. AtMem retains its relationship to source evidence and can quarantine untrusted observations. Updates supersede records rather than silently overwriting their history. Forgotten or excluded records leave ordinary recall, and derived indexes must follow lifecycle changes. A vector match cannot make a deleted canonical record valid again [1, 4].

AtMem can run locally without a hosted model. A persistent memory database has a rebuildable vector sidecar, but its default hashing profile is diagnostic rather than a production-quality semantic model. An operator can separately configure and verify a stronger embedding profile. AtBot can add interpretation or ranking through a configured local or hosted model. New agent integrations begin in shadow mode so their prospective behavior can be inspected before context injection is enabled [1, 5].

### 3.2 Read path and delivery

Native recall first gathers a bounded set of active candidates. SQLite FTS5 supplies full-text retrieval with BM25 scoring; structured fact-key matches and recent records supplement that search. Text relevance, trust, and recency contribute to native ordering. Graph recall is optional. A healthy production semantic index can independently nominate paraphrase matches in governed candidate paths. An opt-in reciprocal-rank-fusion strategy exists for research; it is not the established default [3–5].

Candidate nomination is distinct from deciding whether a memory answers the **original question**. AtMem distinguishes direct support, background context, and no useful memory. Direct support is the default class eligible for injection. Query expansion or high vector similarity alone cannot establish it. At context construction, AtMem rechecks selected record IDs against current canonical state and policy. The host injects context only when permitted and confirms the observed exposure [1, 3].

| Stage | Owner | Output |
|---|---|---|
| Candidate retrieval and scope checks | AtMem | Bounded IDs and candidate text |
| Relative usefulness judgment | Jev, when invoked | Scores over supplied IDs |
| Selection and final validation | AtMem | Eligible ordered IDs |
| Context construction and exposure | AtMem and the host | Bounded package and exposure evidence |

This is the point where Jev can help: AtMem may find the right record yet rank it below distractors.

## 4. Jev-assisted method

Jev accepts state and typed questions. Its **Choice** primitive evaluates application-defined alternatives and returns a structured answer with probabilities over them [2]. In the memory experiment, the state contains the question and candidate texts; the alternatives are candidate IDs. Jev's returned values determine an advisory order. AtMem accepts only IDs it supplied and retains final authorization and context checks [6].

The interface has three useful properties for this task. Its answer space is explicit and bounded, so an unknown record ID can be rejected. Its structured output avoids parsing a generated paragraph for identifiers. Its scores can be retained as inspectable ranking evidence. These are properties of the interface and integration design, not proof that Jev is universally accurate or fast enough for every live turn. The comparison pinned model identity to jev-1.13.0 [2, 6, 7].

Two limits follow directly. Jev cannot rerank a record that AtMem failed to retrieve. A Jev probability cannot establish truth, currentness, authorization, or the cause of a later agent answer. The isolated JEV-Lab was designed to demonstrate this advisory boundary with synthetic data [8].

## 5. Experimental setup

### 5.1 Dataset and conditions

We evaluated retrieval using a locally supplied **LoCoMo** file. LoCoMo contains long conversations and questions annotated with dialogue IDs for supporting evidence [9]. The reviewed run covered ten conversations and 1,986 questions. Its manifest pins the upstream source revision and exact dataset SHA-256 digest [7, 10].

Each dialogue turn was represented as a record through the real AtMem Memory engine. For each question, the adapter called native recall and retained the top ten candidates. The **baseline** kept AtMem's native order. The **Jev condition** used precisely those candidates and ordered their IDs by Jev's returned choice probabilities. The benchmark used in-memory databases with automatic vectors disabled. It therefore does not test the full deployed mix of semantic indexes, graph paths, AtBot, host injection, or answer generation [10].

Jev processed the comparison in 40 batched remote requests after explicit external-egress authorization. The run recorded zero Jev transport errors [6, 7]. The dataset contents were not checked into AtMem's repository.

### 5.2 Measures and claim controls

For a question whose first cited evidence appears at rank r, reciprocal rank at five is 1/r when r is at most 5 and zero otherwise. **MRR@5** averages this value over questions. Here, **Recall@k** is the fraction of questions with *at least one* cited evidence ID in the top k. It does not require every cited turn to be present. Evidence coverage separately measures the fraction of cited IDs in the returned list [11]. These are retrieval measures, not answer-accuracy measures.

The adapter retains per-question outputs and an auditable summary. Four upstream evidence-reference anomalies remained in the reviewed file. They were reported rather than silently repaired or excluded, leaving the claim status **exploratory** [7]. No confidence interval or significance test is reported. Although there are 1,986 questions, they are nested within only ten conversations.

## 6. Results

| Retrieval measure | AtMem native order | AtMem candidates reranked by Jev | Difference |
|---|---:|---:|---:|
| MRR@5 | 0.4259 | **0.5868** | +0.1609 |
| Recall@1 | 0.3399 | **0.5423** | +0.2024 |
| Recall@5 | 0.5760 | **0.6420** | +0.0660 |
| Recall@10 | 0.6495 | 0.6495 | 0 |

Jev placed cited evidence higher among AtMem's ten candidates. Recall@10 did not change because the reranker could not add candidates. The result supports a ranking improvement on the evaluated file; it does not demonstrate increased candidate coverage or better generated answers [7].

Remote requests introduced latency. Across 40 batches, recorded transport latency was approximately **3.32 seconds median** and **8.74 seconds at the 95th percentile per batch** [7]. These are batch measurements, not end-to-end agent-turn latency. A real deployment also needs an explicit policy for sending question and candidate text to the remote endpoint.

## 7. Discussion

The experiment supports a limited conclusion: structured judgment improved **evidence ordering after AtMem had already found the evidence**. It does not establish that Jev is the best reranker for every workload, that a remote call belongs on every interaction, or that an agent will answer more accurately when given the reordered context.

The separation of authority and judgment is central. A high score must not become an accidental permission grant. Likewise, if candidate discovery and judgment are conflated, an evaluation cannot tell whether an improvement came from finding new records or sorting existing ones. AtMem's layered design allows both questions to be measured separately [3, 8].

Three follow-up experiments are needed. First, establish a declared cleaning or exclusion protocol for the LoCoMo evidence anomalies. Second, evaluate held-out tasks with uncertainty estimates grouped by conversation rather than treating all questions as independent. Third, measure the complete agent path: candidate generation, optional Jev judgment, final AtMem validation, context delivery, answer generation, and independent answer scoring. That study should report withholding errors, latency, and external-service cost alongside answer quality.

AtMem's broader aim is to improve what agents remember **and** what they do with remembered information while preserving an inspectable authority and evidence boundary. Jev is promising as a constrained judgment component in that system. The present study establishes a reason to investigate that role further, not a claim that the full agent problem is solved.

## References

1. AtMem contributors. *AtMem project overview, architecture, and integration boundaries*. [Link](https://github.com/aetna000/atmem/blob/main/README.md) [Link](https://github.com/aetna000/atmem/blob/main/LICENSE)
2. TypeSafe AI. *Jev introduction and Choice primitive*. [Link](https://docs.typesafe.ai/introduction) [Link](https://docs.typesafe.ai/primitives/choice)
3. AtMem contributors. *Retrieval quality and semantic profiles*. [Link](https://github.com/aetna000/atmem/blob/main/docs/retrieval-quality.md)
4. AtMem contributors. *Memory authority and SQLite retrieval implementation*. [Link](https://github.com/aetna000/atmem/blob/main/atmem/memory.py) [Link](https://github.com/aetna000/atmem/blob/main/atmem/store/sqlite.py)
5. AtMem contributors. *Semantic setup and current implementation status*. [Link](https://github.com/aetna000/atmem/blob/main/docs/semantic-search.md) [Link](https://github.com/aetna000/atmem/blob/main/docs/current-status.md)
6. AtMem contributors. *Jev benchmark request and reranking implementation*. [Link](https://github.com/aetna000/atmem/blob/main/research/production_benchmarks/jev.py)
7. AtMem contributors. *LoCoMo and Jev benchmark review*, 19 September 2026. [Link](https://github.com/aetna000/atmem/blob/main/specs/035-production-memory-benchmarks/review.md)
8. AtMem contributors. *JEV-Lab: governed memory judgment experiment*. [Link](https://github.com/aetna000/atmem/blob/main/specs/034-jev-lab/spec.md)
9. Maharana, A., Lee, D.-H., Tulyakov, S., Bansal, M., Barbieri, F., and Fang, Y. *Evaluating Very Long-Term Conversational Memory of LLM Agents*. ACL 2024. [Link](https://aclanthology.org/2024.acl-long.747/) [Link](https://github.com/snap-research/locomo)
10. AtMem contributors. *LoCoMo adapter and dataset manifest*. [Link](https://github.com/aetna000/atmem/blob/main/research/production_benchmarks/locomo.py) [Link](https://github.com/aetna000/atmem/blob/main/research/production_benchmarks/manifests/locomo.json)
11. AtMem contributors. *Ranking metric definitions*. [Link](https://github.com/aetna000/atmem/blob/main/research/production_benchmarks/metrics.py)
