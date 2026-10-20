# Completed two-repeat structural confirmation

Both frozen repetitions completed and their encrypted MEM archives independently
recover all 28 actual model streams with original-vault access denied. Five
task clusters, not ten independent tasks. The same fixed Claude CLI/model,
official grader and cold-source boundary apply. This is a small engineering
study, not a full SWE-bench score or experience-memory evaluation.

| All scheduled attempts | Native | AtMem | Cognee |
| --- | ---: | ---: | ---: |
| Scheduled | 10 | 10 | 10 |
| Fully solved | 10 | 10 | 8 |
| Preparation failures | 0 | 0 | 2 |
| Complete model usage receipts | 10 | 10 | 8 |

Cognee's two SymPy preparations exceeded the fixed deadline before inference;
these are availability failures, not wrong model answers. Its runnable cases
all pass. Actual graph content uptake: one AtMem source call across both
repetitions, zero Cognee content calls. This cannot establish a retrieved-graph
benefit or explain aggregate differences causally.

Identical four runnable tasks in both repeats, eight paired attempts per arm:

| Metric | Native | AtMem | Cognee |
| --- | ---: | ---: | ---: |
| Fully solved | 8/8 | 8/8 | 8/8 |
| Complete input tokens | 103,065 | 178,321 | 115,087 |
| Output tokens | 10,727 | 10,861 | 9,781 |
| Median solver seconds | 30.40 | 36.13 | 38.83 |
| Median measured setup + solver seconds | 49.54 | 116.98 | 377.37 |

AtMem matches runnable repair quality, but uses more input than both controls.
Its setup-inclusive time is lower than Cognee's, not native's. The superiority
and >=20% token-saving goals are not met.

Separately compare native/AtMem on all five tasks and both repeats, including
SymPy: both solve 10/10, with 161,853 versus 523,105 complete input tokens and
34.41 versus 51.56 median solver seconds. Do not hide this by reporting only
the four-task three-provider intersection. Both repetitions and their
variation remain in `2026-10-19-swebench-confirmation-summary.json`.

Scored AtMem wheel remains
`1314dc5a309cd19c7ac0e7704a4cc5d18a77d4596cffbb2fef0c6ae549d2629d`.
Neither the later metadata reader nor compact tool interface was substituted.
All 28 streams reproduce exact usage/tool counts, actual CLI 2.1.281/model
claude-opus-5-5, with no test/dependency edits. The retained sources and
authority receipts, not a public projection alone, bind the completed study.

## Separate query-only performance controls

After both scored repetitions finished, persistent local WSL MCP processes
performed three identical architecture queries per provider on each of four
identical source snapshots. The first is a fresh-process request with OS caches
unflushed; the next two reuse that same process. No inference or indexing time
is included. Full responses are retained encrypted; all old/new AtMem outputs
are byte-identical for every query on all four snapshots.

| Median seconds | Scored AtMem | Separate metadata reader | Cognee |
| --- | ---: | ---: | ---: |
| First query | 13.877 | 12.202 | 7.234 |
| Subsequent queries | 13.881 | 12.001 | 0.201 |

The metadata fix improves this measured AtMem service workload by roughly
12–14%, not the roughly 50% pure-query-only change previously measured on Click.
Cognee is substantially faster when warm here. AtMem still performs its current
source and authority checks and reconstructs query state; no unsafe cache was
introduced to match the competitor's number. These measurements do not
establish which work is necessary or an exact causal decomposition.

Metadata reader wheel:
`28ba734377c6e55a1cc5698031a8be35bafe4e2c2e1677740dfa3b0234bb4eb8`.
Raw control root:
`/Users/javadtaghia/Library/Application Support/AtMem Benchmarks/swebench-warm-query-controls-20261019`.
Its query results are separate from all coding scores. A new compact-interface
screen is separately declared; old confirmation is not re-labelled as unexposed.
