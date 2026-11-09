# Verified-memory feedback: frozen baseline protocol (Spec 050)

Status: contract preflight implemented; no efficacy evaluation performed. This
protocol does not authorize a scored DolphinBench run, model calls or training.

## User outcome and comparisons

The outcome is a correctly completed requested action, including every required
fact in the exact write that reaches its destination. Retrieval, exposure, a
successful read, a host success report and an LLM judgement are separate evidence.

Compare three unchanged configurations against byte-identical task inputs:

1. Native host, with native memory and no AtMem intervention.
2. AtMem 2.3.14 at `1f5c72e0d98dd57a5fba2f836123dd54741db892`,
   with the existing context and action guards unchanged and feedback disabled.
3. That same AtMem configuration and memory snapshot with one explicitly named
   candidate profile or rule revision. Hold the memory snapshot fixed.

Pin the host commit, installed package artifact, configuration, memory snapshot,
reader, independent verifier and tool schemas in the approved evaluation
manifest. Baseline observations start `not_run`; a configuration manifest cannot
assert that a real baseline succeeded. Changing the baseline requires review.
Restore simulated destination state between paired arms. Never replay a real
user's write to establish a baseline.

## Initial bounded corpus

`tests/fixtures/feedback/contract-corpus.json` contains six synthetic contract
scenario definitions. `baseline-manifest.json` freezes their bytes by SHA-256,
task/action/check inventory, chronological cutoffs, seed and episode-based
development/validation/test partitions. These scenarios exercise wiring only:
read plus write, absent required fact, delivered-but-not-applied constraint,
missing write, refusal and disputed readback. They are not measured outcomes,
realistic workloads, a powered sample or untouched held-out evidence. They
must never support claims of production quality, performance or improvement.

`atmem.feedback.baseline.validate_baseline` rejects missing baselines/checks,
future evidence, cross-partition episode/paraphrase reuse, changed gates,
changed memory, unbounded resources, forged result/approval fields and model
or host assertions presented as independent verification. It does no I/O and
cannot authorize spending, qualification, activation or claims.

Before any efficacy run, an owner-approved manifest must separately identify a
legitimate licensed corpus, immutable revision and bytes, untouched episode and
chronology splits, power/sample-size calculation, exact baseline artifacts,
independent verifier authority, hardware, budgets and permitted egress. Previously
inspected items are diagnostic. LoCoMo, LongMemEval and BEAM must be included
where applicable to a production retrieval claim under Constitution VIII.
Missing corpus, power, permissions or independent verification means
`inconclusive`; a synthetic fallback cannot replace them.

## Verification and denominators

Each required action binds one tool/schema and one invocation with all mechanical
and judged checks. Partial calls cannot be combined. Store exact authorized
arguments, returned result and destination readback through the encrypted evidence
store. A registered scoped readback verifier must be independent of the acting
model/host. Distinguish capture, delivery, reported success, verified effect,
disputed evidence and unknown. An unexecuted write stays incomplete.

Report verified full-task success over all scheduled eligible tasks; coverage
over all eligible answerable tasks; wrong answers over independently assessed
answers; relevant evidence over assessed delivered evidence; false denials over
legitimate covered calls; missing-required-fact writes over assessed writes that
require the fact. Display numerator/denominator, unknowns, abstentions, verifier
tier, regressions, scope and version. Zero denominators are undefined. Use paired
95% uncertainty clustered by episode. Split missing-fact failures by whether
the evidence was delivered; do not infer retrieval failure from output alone.

## Immutable acceptance gates

| Gate | Required evidence |
|---|---|
| SC-001 | Zero unauthorized admissions, disclosures or promotions in scoped, tamper, stale-source, duplicate/retry and injection cases. |
| SC-002 | Reconstruct a complete read/write/correction/activation/revocation journey from only a restored encrypted store after fixture host destruction. Missing capture remains unknown. |
| SC-003 | Paired episode-clustered 95% CI lower bound for verified full-task improvement strictly above zero; coverage loss at most 2 percentage points; no new authority violation. Underpowered evidence is inconclusive. |
| SC-004 | No escaped forbidden calls in the pinned Hermes hostile matrix; exact approval binding; legitimate calls succeed; shadow has no real side effects. Held-out false denial at most 1%, with counts and uncertainty. |
| SC-005 | Identical disabled-mode regression outcomes; active retrieval p95 overhead at most 20%; deterministic rule p95 at most 10 ms with 1,000 applicable rules. Remote verification time reported separately. |
| SC-006 | Real encrypted-store journey, published-store upgrades, crashes/retries, rollback and dependent deletion on Python 3.10–3.13 and Linux/macOS/Windows. |
| SC-007 | Dashboard/CLI/API count and state parity, keyboard/browser acceptance, scope non-disclosure and consent/source-verifiable export exclusions. |

Qualification expires after seven days at most and immediately on a relevant
source/policy/verifier/compiler/adapter change. A report cannot modify thresholds
after seeing results. Record p50/p95, throughput, errors/refusals, resources and
every failed or inconclusive attempt. These gates do not imply universal safety.

## Cost and stop rules

Default: USD 0, zero model calls, zero tokens. The contract fixture permits six
tasks, 30 seconds and 1 MiB of output. No execution is started by a preflight.
Each separately approved efficacy manifest must have finite monetary, token,
task, wall-clock and disk ceilings. Stop at the first exhausted limit or failed
authority gate. No more than three candidate evaluations per failure hypothesis;
then reassess. A failed held-out corpus cannot be retuned and reused as untouched.

Keep raw results and content-free cost summaries. Protect semantic artifacts in
the existing encrypted evidence store, never plaintext temporary experiment logs.
Do not expand to a large campaign because a synthetic fixture passes.

## Reproducible preflight

Run the focused offline validation with:

```sh
python -m pytest -q tests/test_feedback_baseline.py
```

The tests verify the manifest and rejection paths. They neither run models nor
measure efficacy or advertise an installed host as enforcing policy.
