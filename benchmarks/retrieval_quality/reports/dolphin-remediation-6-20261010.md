# DolphinBench six-case remediation diagnostic

Date: 2026-10-10

Claim: bounded development diagnostic, not an official or full-benchmark score.

Protocol:
`benchmarks/retrieval_quality/protocols/dolphinbench-remediation-6-v1.json`

## Retained pre-change evidence

The first valid model-backed run on this frozen subset scored 2/6 tasks and
9/23 checks for AtMem. The corresponding rows in the original matched Mem0 run
scored 0/6 tasks and 2/23 checks. The historical AtMem rows scored 2/6 and
11/23. Two passing controls (`alex:082`, `morgan:103`) remained the regression
floor; four cases exposed evidence-delivery or reader-use defects.

## Evaluator-blind product diagnosis

| Case | Earliest observed defect | Product-neutral correction |
|---|---|---|
| `alex:026` | The required temporal and polarity evidence was present but scattered behind unrelated production-window history. | Nominate the request's exact dated subject independently and reserve it before general history. |
| `morgan:063` | The ownership statement was present but not operationally prominent. | Nominate the explicit approval subject independently and reserve its exact source range. |
| `morgan:138` | The integration address was present, but the usual copy recipient's exact address was omitted. | Follow a source-observed recipient name through bounded indexes to a verbatim identifier-bearing range. |
| `riley:126` | Accountability evidence was present, but the role relation and adjacent exact person name were split across source clauses. | Preserve a bounded named neighbour beside a pronoun-based role relation. |

No benchmark answer, expected tool argument, grader result, load-bearing fact
identifier, or evaluator manifest enters planning, retrieval, packing, or the
agent context. The new nominations are derived only from request text and
canonically retained source evidence.

## No-model gates

- Synthetic identity, recipient, role-neighbour, temporal-facet and regression
  tests pass.
- On the frozen encrypted product checkpoints, the Pinecone task now receives
  both exact email addresses; the annual-review task receives the CEO relation,
  its adjacent exact name, and the accountability/measurement evidence; the
  hiring-sequence owner is placed at the front; and the January 8 replay facet
  is independently nominated.
- The relevant context-engine, governance, contract, official-adapter and
  protocol suites pass 148/148.

The model-backed six-case rerun and fresh removal/restored controls remain
required before this correction can advance to a fresh matched 30-task run.
