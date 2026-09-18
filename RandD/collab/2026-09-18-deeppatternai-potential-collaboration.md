# DeepPatternAI — potential collaboration

Date: 2026-09-18
Status: **Potential opportunity — owner to investigate; no outreach sent.**

## Summary

DeepPatternAI helps agents review and discipline their work. AtMem could complement this by preserving what happened and bringing verified lessons into future work.

The strongest first step is a small joint pilot: **one coding task, one review, one durable lesson**, rather than a broad platform partnership.

## Research scope

Source inspection of both public repositories alongside AtMem's current implementation. No DeepPatternAI installer or hooks were run, no hosted review was tested, and no integration was implemented.

Temporary checkouts: `/tmp/atmem-deeppattern-review.LxQhDl` (temporary research material, not a durable dependency).

| Repository | Inspected commit | Observed version |
|---|---|---|
| [Agent Quality Gates](https://github.com/deeppatternai/agent-quality-gates) | `e2486ae01e60a2a69dc9c44523f7b249bafb8044` | `0.14.23` |
| [Decision Engine](https://github.com/deeppatternai/decision-engine) | `6c420a032638a60c628e734f2f0f62e7b03a0afa` | `0.2.91` |

Both public repositories identify an MIT license. Decision Engine's hosted implementation is not included in its public client source; hosted access was described as invite-only. Public licensing does not establish hosted-service rights or terms.

## What they have

### Agent Quality Gates (AQG)

A workflow-discipline toolkit with skills, lifecycle hooks, deterministic gate scripts and a CI adapter. Capabilities include review routing, test-quality checks, decision logs, session handoffs, memory hygiene and completion-evidence checks.

AQG already has persistent decisions and cross-session handoffs. Do not pitch it as lacking memory or evidence. Host coverage varies: an available adapter does not imply every lifecycle hook is supported.

Its memory-hygiene implementation checks metadata, superseded references and re-verification age. Its closeout checker explicitly describes a discipline check, not an adversarial security boundary.

Sources:

- [AQG README at inspected revision](https://github.com/deeppatternai/agent-quality-gates/blob/e2486ae01e60a2a69dc9c44523f7b249bafb8044/README.md)
- [Memory hygiene](https://github.com/deeppatternai/agent-quality-gates/tree/e2486ae01e60a2a69dc9c44523f7b249bafb8044/skills/aqg-memory-hygiene)
- [Closeout checker](https://github.com/deeppatternai/agent-quality-gates/blob/e2486ae01e60a2a69dc9c44523f7b249bafb8044/scripts/check_evidence_closeout.py)

### Decision Engine (DE)

A client for hosted multi-model reviews of code, plans and decisions. It is a potential review service, not a replacement memory engine. Its stated approach separates panel advice from final adjudication.

The hosted orchestration, prompts and model-selection implementation are not public. Review quality and claimed model independence were not empirically verified in this research.

The inspected client sends `X-Request-ID`, tracks request diagnostics and supports audit IDs. Its request diagnostics include payload digests rather than full submitted content. These are useful correlation points for a future AtMem adapter.

Sources:

- [DE README at inspected revision](https://github.com/deeppatternai/decision-engine/blob/6c420a032638a60c628e734f2f0f62e7b03a0afa/README.md)
- [Client transport and diagnostics](https://github.com/deeppatternai/decision-engine/blob/6c420a032638a60c628e734f2f0f62e7b03a0afa/installer/shim.py)

## Mutual value — proposed, not implemented

| Common ground | AtMem gains | DeepPatternAI gains |
|---|---|---|
| Review-linked evidence | Structured findings and adjudications explaining why a decision changed. | An optional retained record connecting a review to the original request, tool activity and subsequent observed result. |
| Lessons across sessions | Memory candidates from accepted findings and verified fixes. | Retrieval of relevant previous mistakes and decisions without manually assembling every handoff. |
| Memory maintenance | Explicit staleness and re-verification practices that could inform maintenance proposals. | Scoped retrieval, lifecycle controls and evidence links. |
| Agent integrations | Lessons from their lifecycle adapters and partial-support matrix. | A possible common evidence destination across supported agents, through adapters we would build and test. |

AtMem's inspected evidence service has capture, reconstruction, access checks and export surfaces. AtBot's documented role is to propose and rank; AtMem remains authorization and storage authority. These are building blocks, not proof of an existing DeepPatternAI integration.

Local reference files: `atmem/evidence/service.py`, `packages/atbot/README.md`, `docs/context-provider-adapters.md`.

## Recommended pilot

1. AQG identifies a review checkpoint.
2. The agent sends an explicitly approved artifact to Decision Engine.
3. DE returns findings; the developer or agent records which were accepted or rejected and why.
4. A new AtMem adapter records the submitted artifact, returned findings, adjudication and observed test results under one correlated run.
5. A verified, accepted lesson becomes a scoped memory candidate for the next relevant task.

Retain the actual exchanged content according to AtMem's configured capture mode and access controls, not just correlation IDs. Link evidence to repository, commit, task and review identifiers.

**The adapter does not exist yet.** MCP connectivity alone does not provide AtMem's delegated-provider authentication, delivery verification or evidence semantics. Start with review/evidence integration; do not force a review engine into a memory-provider contract without a clear need.

## Boundaries and risks

- **Repository truth stays in the repository.** Link engineering memories to commits and source evidence, and recheck applicability. AtMem should not become a competing source of project truth.
- **Review agreement is not proof.** Separate reviewer opinion, human/agent adjudication and observed test results. Capturing a claim does not establish that an external event occurred.
- **Keep hosted reviews off ordinary retrieval paths.** Use selected checkpoints and measure latency, cost and data leaving the machine.
- **AtBot may propose lessons; AtMem authorizes storage.** Do not automatically promote every panel finding into trusted memory.
- **Respect intentional redaction and capture boundaries.** An integration must explicitly agree what content may be retained or sent to hosted models; it should not silently expand collection.
- **No performance or quality claims yet.** This was source inspection, not an end-to-end integration or benchmark.

## Pilot evaluation

- Evidence completeness: can the authorized investigator reconstruct what was submitted, returned, adjudicated and tested?
- Correlation correctness: do request, audit, run and commit references remain correct across retries and failures?
- Useful versus rejected findings, including false positives.
- Review latency and cost per checkpoint.
- Whether scoped retrieval of accepted lessons reduces repeat mistakes on a predefined evaluation set.
- Failure behavior: unavailable service, partial response, denied capture/export, stale lesson and duplicate submission.

## Questions for the founders

- Is there a stable review/result contract and an approved integration path for hosted DE?
- Can findings, adjudications and completion events be exported with stable audit/request IDs?
- What are hosted data retention, model-provider egress and pricing terms?
- Which host and AQG checkpoint would make the smallest useful joint pilot?
- How should AtMem complement repository-authoritative memory and existing handoffs?
- Would they prefer an optional AQG evidence sink, an MCP wrapper or a jointly maintained adapter?

## Suggested outreach

> Hi—I'm building AtMem, a governed memory and evidence layer for agents. I've been looking through Agent Quality Gates and the Decision Engine client, particularly your evidence closeout, adjudication and memory-hygiene work.
>
> I see a concrete integration opportunity: connect an AQG checkpoint and DE review to an AtMem record of the submitted artifact, findings, accepted/rejected decisions and observed verification results. Then make verified lessons retrievable in later sessions, while keeping the repository authoritative.
>
> You already have decision logs and handoffs; I'm interested in complementing those with scoped memory and retained execution evidence. Would you be open to a small joint pilot around one coding workflow?

## Owner follow-up

- [ ] Review this opportunity and choose whether to contact the founders.
- [ ] Confirm current product/API availability and hosted terms.
- [ ] Agree one pilot workflow and measurable acceptance criteria.
- [ ] Specify the adapter and trust boundaries before implementation.
- [ ] Run the pilot and document results before announcing a partnership or integration.
