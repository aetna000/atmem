# Reference parity harness

This evaluator-only package binds AtMem comparisons to public source revisions,
frozen samples, and a neutral result contract. Reference source remains in
external checkouts and is never imported by AtMem runtime modules.

The two benchmarks are reported separately:

- LongMemEval-V2 compares AtMem with AgentRunbook-R and AgentRunbook-C on the
  same frozen 14-question development sample.
- DolphinBench compares AtMem with Mem0 on the same frozen 18-task development
  sample. A local open-source Mem0 result is labeled `mem0-oss`; it must not be
  presented as reproduction of the hosted leaderboard service.

The promotion target is parity first, then at least 10% relative improvement
over the strongest matched reference. Reports also show the absolute percentage
point delta. Results from different samples, model families, or incomplete runs
are not directly compared.

The neutral twelve-case reader-free corpus and evaluator are frozen in
`fixtures/minimal-evidence-v1.json`, `normalizer.py` and `runner.py`. The current
partial pre-change comparison is recorded in
`benchmarks/retrieval_quality/reports/context-engine-prechange-reader-free.md`.
Its Mem0 and AgentRunbook-R arms deliberately omit model-assisted formation;
they are implementation diagnostics, not published-score reproductions.

`benchmarks/retrieval_quality/baselines/reference-results-20260930.json`
separates matched development results from published leaderboard context. In
particular, the published Mem0 score on the same eighteen Dolphin tasks uses a
different agent model and hosted memory service; it is a diagnostic target, not
a claim of a controlled OSS reproduction.
