# From agent memory to accountable information use

Date: 28 September 2026 (Australia/Sydney)

Status: Research and product direction from our discussion. Proposed capabilities
below are not an approved implementation plan, a release commitment, or measured
results. Current capabilities are bounded by the cited documentation and tests.

Source: IBM Technology, Jeff Crume, **“AI Is Exposing Your Data: An AI Security
Problem You Can't See,”** published 27 September 2026.
[Video](https://www.youtube.com/watch?v=kyJ1vd7yEPc).
This note uses the video's available English captions; the publisher discloses
AI involvement in its transcript and metadata. The analysis and proposed AtMem
direction are ours, not an IBM endorsement or an independent security assessment.

Related direction:
[Enterprise context governance roadmap](2026-09-09-enterprise-context-governance-roadmap.md).

## What we learned from the video

Sensitive data moves through prompts, retrieval, models, tools, and other agents.
It also changes form: tracking an original document alone misses summaries and
other derivatives. Crume argues for connected visibility into sources,
transformations, destinations, and authorization. He distinguishes application
activity from employee activity such as uploads and copy/paste; neither view
alone covers the system. Investigation needs evidence connecting those views.

Useful anchors:

- [1:52–4:09](https://www.youtube.com/watch?v=kyJ1vd7yEPc&t=112s): data movement through the AI architecture.
- [5:30–6:05](https://www.youtube.com/watch?v=kyJ1vd7yEPc&t=330s): tracking transformed information.
- [7:05–7:55](https://www.youtube.com/watch?v=kyJ1vd7yEPc&t=425s): lineage, shared policies, and risk visibility.
- [8:00–9:15](https://www.youtube.com/watch?v=kyJ1vd7yEPc&t=480s): complementary discovery perspectives.

Our interpretation: persistent memory makes these problems last across sessions.
A disclosure risk can survive the original interaction inside a saved summary,
preference, or procedure and become relevant much later.

## What AtMem can contribute now

AtMem provides a starting point for controlling and explaining the reuse of
remembered information within connected runtimes. Its evidence does not cover
every application, endpoint, or destination an organization uses.

| Need | Documented AtMem foundation | Boundary of the claim |
| --- | --- | --- |
| Identify the source of recalled information | Canonical records, source references, lifecycle state, and audit investigation | Missing historical provenance remains missing; source attribution does not prove truth. |
| Limit reuse to the intended context | Candidate checks against canonical scope, status, digest, exclusions, sensitivity, and generation | Requires the application to use the governed path; unrelated file or network access is outside it. |
| Preserve distrust through derivation | Explicitly linked derived records inherit direct-parent taint | Tested trust propagation does not establish general confidentiality tracking through arbitrary paraphrases. |
| Explain model and tool activity | Black Box lifecycle hooks, context disposition, and protected evidence when enabled | Runtime coverage varies; host observations do not prove downstream provider behavior or real-world outcomes. |
| Withdraw stored information | Superseded/tombstoned records are excluded from ordinary recall; supported deletion cascades return receipts | This cannot undo past outputs or external actions, or prove deletion from undeclared copies and backups. |
| Recover from uncertain tool outcomes | Opt-in continuity can reuse receipts, query a supported destination, retry with valid destination-enforced idempotency, or stop | It is not universal exactly-once execution, and cannot retract already disclosed data. |

Sources: [data and privacy behavior](../README.md#data-privacy-and-recovery),
[audit investigation](../docs/audit-search.md),
[Black Box](../docs/agent-blackbox.md),
[integrity qualification](../docs/benchmarks/memory-integrity.md),
[continuity](../docs/continuity.md), and
[production threat model](../docs/security/production-threat-model.md).

The 2.3.6 integrity qualification reported 400 PASS and 300 NOT_REPRESENTABLE
trials out of 700. Its direct-parent taint and canonical secret-retention results
are useful starting evidence, but they do not measure general data disclosure
across models and tools. The Category D target-matching correction and its
upstream review status are disclosed in the qualification document. These results
must not be presented as proof of the broader proposal below.

## What AtMem could become

**A local-first layer that controls how agent memory is reused, preserves the
restrictions attached to its sources, and records evidence of permitted use.**

This gives the existing enterprise context-governance direction a concrete
research focus: information restrictions must survive transformation and time.
Native memory and connected providers could both participate, with their
different authority and evidence boundaries made explicit.

An operator should eventually be able to ask:

- Which sources contributed to this context package or remembered procedure?
- Who was permitted to use those sources, for what purpose and destination?
- Which transformations and policy decisions allowed the delivered content?
- Which known derivatives need review after a correction or revocation?
- What evidence exists, and where does coverage end?

This would complement endpoint discovery, enterprise classification, identity,
and network controls. Those integrations are necessary to cover paths outside
AtMem, including employee copy/paste and uninstrumented tools.

## A concrete target workflow

Consider a company assistant that reads a confidential acquisition document,
creates a summary, saves facts, and later drafts a public announcement.

The proposed workflow is:

1. **Register source policy.** Bind the source version to an authenticated owner,
   classification, permitted purposes, and destinations. Record who supplied
   those attributes and whether they are authoritative or merely predicted.
2. **Record derivation.** Link extracted facts and summaries to their inputs and
   transformations. A model-generated summary does not silently acquire broader
   permissions than its sources.
3. **Authorize disclosure.** Check policy before information leaves through a
   retrieval query, embedding service, model request, tool argument, or handoff
   to another agent. A local memory database alone cannot enforce this.
4. **Permit a bounded transformation.** Redaction or approved aggregation may
   produce a releasable derivative. That decision needs explicit authority and
   evidence; a model's assertion that text is harmless is insufficient.
5. **Bind the delivered package.** Record the destination, applicable policy
   version, content digest, source versions, and observed delivery. Modification
   creates a new package; an old signature cannot attest to different bytes.
6. **Handle source changes.** On correction or revocation, invalidate affected
   grants and known derivatives for future use, then selectively recompute or
   review them. Separately identify past disclosures that cannot be recalled.

These are proposed requirements, not existing end-to-end guarantees. A signed
provider response establishes its binding; it does not by itself establish
independent enterprise authorization. This distinction is already raised in
the [enterprise roadmap](2026-09-09-enterprise-context-governance-roadmap.md#2-explicit-authority-model).

## The research problem worth pursuing

Candidate thesis direction:

> How can agent memory preserve and enforce information-use restrictions through
> transformation, while retaining useful knowledge and supporting selective
> correction and revocation?

The difficult part is selective propagation. A summary containing acquisition
details should retain restrictions. An approved aggregate may reveal nothing
that policy prohibits. Restricting every descendant indefinitely can prevent
legitimate work; forgetting dependencies can expose protected information.

Keep three concepts distinct:

| Concept | Question |
| --- | --- |
| Integrity and authority | Should this information be trusted or treated as permission? |
| Confidentiality and permitted use | May this information be disclosed here, to this recipient, for this purpose? |
| Lifecycle and revision | Is it still current and permitted, and what must change when it is withdrawn? |

Hypothesis: explicit derivation tracking, conservative policy propagation, and
authorized selective recomputation can improve the balance between task utility
and unauthorized disclosure compared with flat retrieval, unconstrained summary
memory, and blanket suppression of all descendants. This requires experiments;
we should not assume AtMem will outperform simpler baselines.

Information-flow control, provenance, access control, declassification, and
revocation have substantial prior literature. The video motivates an application
problem; it does not establish novelty. A thesis contribution must be located
precisely against both that literature and recent agent-memory research.

## A first evaluation we can build

Use synthetic company documents containing controlled confidential facts and
public facts. Run multi-session tasks that require useful summaries, updates,
and external communications. Start with one instrumented runtime and explicitly
enumerated stores and destinations.

| Scenario | What to inspect |
| --- | --- |
| Repeated summarization and paraphrasing | Whether protected meaning survives while its restrictions disappear |
| Mixed public and confidential sources | Whether allowed information remains usable without releasing protected facts |
| Cross-agent handoff | Whether the receiving agent's actual authority is checked |
| Permission revoked after a summary is saved | Whether cached packages and known descendants remain usable afterward |
| Source corrected | Whether affected beliefs change without destroying unrelated knowledge |
| Provider or model switched from local to hosted | Whether disclosure policy is reevaluated before transmission |
| Retrieval query or embedding request | Whether sensitive content escapes before result admission |
| Restart with stale context | Whether persisted packages are revalidated against current policy |
| Deletion requested | Which declared stores are cleared, retained under policy, or outside coverage |

Measure unauthorized disclosure, false blocking of legitimate tasks, task
completion, known-dependency coverage, revocation latency, revision cost, token
use, and runtime overhead. Record both allowed and denied cases so that blocking
everything cannot score as success. Use matched models and budgets, repeat runs,
and report uncertainty rather than a single favorable trajectory.

Ground truth should combine controlled source dependencies and policy labels
with inspection of actual intercepted outbound payloads. Exact secret matching
alone will miss paraphrased disclosure; include human-reviewed semantic cases
and report that judging limitation. Ground truth is bounded by the synthetic
task design, not a proof of complete real-world lineage.

No new experiment was run for this note.

## A feasible two-year sequence

| Period | Research deliverable |
| --- | --- |
| Months 1–6 | Review relevant prior work, define the threat model and policy semantics, instrument a narrow workflow, and establish baselines. |
| Months 7–12 | Implement explicit derivation and disclosure checks; evaluate summaries, mixed-source context, and permitted release. |
| Months 13–18 | Add selective correction and revocation across sessions; evaluate cached packages, handoffs, and useful knowledge preservation. |
| Months 19–24 | Replicate across a second runtime or task domain, run adversarial tests and ablations, publish reproducible evidence, and write the thesis. |

Expansion should follow demonstrated usefulness and measured coverage. Broad
enterprise discovery, every jurisdiction's compliance regime, and arbitrary
provider deletion are outside this initial research scope.

## Claims and design choices to keep honest

- Local storage does not imply local inference, embeddings, or tool execution.
- A hash or signature establishes a particular integrity relationship; it does
  not prove semantic safety, complete lineage, or truthful source content.
- The Black Box is itself a sensitive store. Minimize retained content where
  possible and define access, encryption, retention, and export behavior.
- Withdrawing future access cannot undo information already received by a
  person, model provider, or external tool.
- Compliance evidence can support an assessment. It is not automatic legal
  compliance or certification.
- The video's suggestion that chatbot uploads automatically become public is
  too broad. Product terms and settings determine processing and training use;
  training use and public availability are different claims. For example,
  [Anthropic's policy](https://www.anthropic.com/legal/privacy) distinguishes
  consumer choices and separately governed business offerings.

Suggested future positioning, conditional on implementing and validating the
proposal:

> AtMem helps agents remember useful information while preserving who may use
> it, where it may go, and what must change when its source is corrected or
> withdrawn.
