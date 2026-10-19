# Automatic-source-context validation

Both arms solve all five fixed validation tasks under the official grader and
unchanged budgets. Automatic source context does **not** improve efficiency on
this cohort. All ten actual model attempts have complete successful usage
receipts; all five AtMem prompts receive actual current product source packs.

| Measure, identical five tasks | No memory | AtMem automatic context |
|---|---:|---:|
| Official fully resolved tasks | 5/5 | 5/5 |
| Complete total input tokens, including cache reads/writes | 72,192 | 141,912 |
| Total output tokens | 7,397 | 7,586 |
| Median solver-only seconds | 32.63 | 38.85 |
| Median indexed-workspace context + solver seconds | 32.63 | 62.80 |
| Median measured setup + solver seconds | 45.27 | 144.44 |
| Total indexing seconds | 0 | 215.73 |
| Delivered source-context cells | 0 | 5 |

The indexed-workspace subtotal includes the retained pre-model context stage,
including process startup/query/validation and capture overhead. It excludes
indexing, workspace staging and preliminary transport controls. Full measured
setup includes those benchmark controls; neither number is a promised normal-
host hook latency. Official grading is evaluation work, not added solver time.

For example, scikit-learn's AtMem solver takes 20.96 seconds versus native's
30.61 seconds, but including its 20.59-second context stage yields 41.55 versus
30.61 seconds. Reporting only solver time would hide the added latency.

## Interpretation and profile selection

This profile supplies a bounded source pack through the actual installed MCP,
with the same single model-visible workspace tool as native. Delivery is not
proof that the model used the supplied evidence. It differs deliberately from
the original equal-optional-tool study and is not pooled with it.

The revised packer separately preserves exact bytes and reduces packing work;
[those installed controls](2026-10-19-code-packing-correction.md) are not a
coding-efficiency result. Original validation has already been inspected and
is not an untouched test set. No synthetic training data or model training is
involved in this study.

The [frozen selection receipt](2026-10-19-swebench-profile-selection.json) follows
the predeclared rule: equal five-task completion, then lower complete AtMem
input-token total, then measured setup-plus-solver time. It selects the original
optional-MCP profile (128,830 AtMem tokens) over automatic context (141,912).
Native controls also vary between the separate fresh runs; do not substitute
one run's native result into the other's paired comparison. Selection does not
establish benefit, especially since neither original graph is queried.

Confirmation retains the exact selected optional runtime, wheel
`1314dc5a309cd19c7ac0e7704a4cc5d18a77d4596cffbb2fef0c6ae549d2629d`,
not an unscored replacement with today's source checkout. The optimized
automatic candidate is separately pinned to
`c7b4fb0256cf32e4f06461ad0dbf0200ee46401998f94c65f47cb14178012baa`.
Two task-disjoint confirmation schedules, with reversed second-repetition arm
orders, are frozen before confirmation inference; no confirmation tuning.

## Post-run diagnostic, not a new tuning input

The retained Sphinx automatic attempt makes eight workspace calls versus five
for its fresh native control. Both search for `__all__`, inspect the relevant
implementation and run public tests. Its supplied pack includes related
`Documenter.filter_members` and accessor code, but does not supply the old line
1077 that the passing agent changes in `ModuleDocumenter`'s implementation.
The same exact-rendered-line check finds that Django line 101 and scikit-learn
line 113, each replaced by the passing agent, were not supplied either.

These are the three cases with removed/replaced old lines. The other two agent
patches are insertion-only and are not assigned a zero coverage rate. Related
context can still be useful without including a changed line, and delivered
lines do not prove model use. This is therefore a narrow diagnostic, not a new
retrieval-recall score or a proof of the model's internal cause. It identifies
a source-selection problem that indexing availability alone cannot solve.
The diagnostic is read-only, uses agent patches rather than reference patches,
and does not change training, packing, the selected runtime or confirmation.
Per-case locations are retained in `context-line-diagnostic.json` beside the
protected campaign. `receipt-audit.json` separately reconstructs all usage/tool
counts, confirms CLI 2.1.281 / `claude-opus-5-5`, and finds no test or dependency
configuration changes in these ten agent patches. Baseline HEAD preservation
is the recorded patch gate; this is not a claim that every transient Git ref
or temporary file is prohibited by the shell sandbox.

## Retention

Protected campaign:
`/Users/javadtaghia/Library/Application Support/AtMem Benchmarks/swebench-automatic-adjacency-validation-20261019`.
[Numerical projection](2026-10-19-swebench-automatic-adjacency-validation-live.json).
`timing-analysis.json` beside the campaign retains per-task context-inclusive
measurements. All six event runs and ten model streams are independently
recovered from encrypted MEM archives, with original-vault access denied:
`/Volumes/MEM/AtMem-SWEbench-Threeway-20261019/swebench-automatic-adjacency-validation-20261019`.
The earlier stopped automatic campaign and its one native attempt remain
separate, archived and unaltered. No model outcome is retried or omitted here.
