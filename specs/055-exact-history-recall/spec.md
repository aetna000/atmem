# Spec 055 — Exact history recall benchmark

## Outcome

Measure whether AtMem can recover exact evidence from retained interaction
history after it leaves the working context. Use a summary with bounded literal
search as a simple comparator. Prototype a host-authorized search when a
matched baseline shows a recoverable miss or a material context-cost gap at
equivalent answer accuracy.

## Requirements

- **FR-001** Run the current native AtMem V3 `context-fast` path with its default
  engine against a fixed synthetic history. Keep a separate literal comparator
  on the same history, with the same query information and output byte ceiling.
- **FR-002** Separate development and held-out histories with pinned seeds.
  Include exact identifiers, individual log lines, current versus prior values,
  paraphrases, missing evidence, and an inaccessible scope. Grade evidence
  delivery with deterministic checks and report counts by cohort.
- **FR-003** Record source availability, whether the expected evidence reached
  the returned context, stale or forbidden text, recall calls, context bytes,
  and latency. Zero model calls and paid egress for the pilot. An evidence hit
  measures retrieval only. Report model answer quality and tokens separately in
  any later model-backed experiment.
- **FR-004** Keep candidate search read-only and explicit. Use authorized active
  canonical text, stable source ranges, live authorization and an audit receipt.
  Bound scanned input, search calls and output. Preserve existing defaults and
  fail closed on scope, deletion, live revocation and audit failure.
- **FR-005** Preserve the baseline result before evaluating a candidate. Compare
  the three arms on the same frozen cases. Extra calls and bytes count against
  the candidate's total. Record failures and resource regressions.

## Acceptance

1. A local command reproduces the development baseline with isolated synthetic
   data and a machine-readable report. Tests verify fixture identity, scope,
   grading and budgets.
2. An opt-in candidate recovers missed exact evidence or reduces context cost
   at equivalent answer accuracy. It discloses zero forbidden text. Test
   deletion and authorization changes independently before running the frozen
   holdout.
3. Label results as a synthetic retrieval diagnostic. Live compaction, deployed
   host behavior, full ContextBench reproduction and production claims require
   separate evaluation.
