# Click: actual upstream Cognee versus AtMem structure versus native

Completed 2026-10-18. One fixed historical Click issue, three fresh subscription
Luna-low attempts. The previous AtMem optimization loop remains paused; this
was a separately requested short competitor integration diagnostic.

## Result

Both structural integrations passed the frozen default test suite. Native left
three failing collision cases. Neither structural integration reduced total
input tokens against the fresh native attempt. This does not reveal a unique
Cognee correctness benefit missing from AtMem on this task.

| Measure | Native tools | Upstream Cognee CODE | Current AtMem structure |
| --- | ---: | ---: | ---: |
| Frozen suite passes | 1,865 | 1,868 | 1,868 |
| Frozen suite failures | 3 | 0 | 0 |
| Solver seconds | 48.947 | 59.921 | 41.863 |
| Total input tokens, including cached | 351,555 | 406,075 | 435,973 |
| Cached input tokens, subset of input | 310,272 | 379,648 | 382,592 |
| Uncached input tokens | 41,283 | 26,427 | 53,381 |
| Output tokens | 2,867 | 3,987 | 2,684 |
| Total input change versus native | — | +15.51% | +24.01% |
| Completed graph-tool calls | 0 | 2 | 1 |
| All counted tool events | 17 | 15 | 13 |
| Measured source/session setup seconds | 2.597 | 1.036 | 1.069 |
| Measured indexing seconds | 0 | 38.149 | 3.861 |
| Measured initial context-planning seconds | 0 | 0 | 2.558 |
| Normal terminal usage receipt | Yes | Yes | Yes |

Cognee used **6.86% fewer total input tokens than AtMem**; AtMem's solver was
**30.14% faster than Cognee's**. A single attempt per arm does not establish a
repeatable speed, efficiency or quality advantage. Cached tokens are not added
to input again. Billing and remaining subscription quota are unknown.

Indexing timings reflect these concrete harness paths, not a pure backend
comparison: Cognee starts a new SDK process; AtMem is invoked in the already
imported operator process. Installation, positive-control queries, evidence
retention and grading are outside solver time. Do not call the sum a complete
end-to-end or warm-service user latency.

## Exact task and controls

- First chronological task from the previously qualified five-task package:
  Click `b67832c`, parent `8c1a0a7abbc1c36f70d1f65f3604acc46c5ce6ab`.
  Issue: user parameters named `help` must coexist with automatic help, custom
  help names must work, and user-defined `--help` remains value-taking.
- Native failures: `test_reported_help_collision[argument]`, `[option]`,
  `[custom]`. Both provider attempts passed those cases and the other frozen
  default-suite checks.
- All arms: same source-only parent, requirements, Python/test runtime, native
  tools, subscription `gpt-6-luna`, low effort, 180 seconds, 24 counted tool
  events; 500,000 input-plus-output tokens audited after completion. All three
  completed normally and stayed under these execution thresholds.
- Fresh native → Cognee → AtMem serial order; one session per arm. No retries,
  tuning, experience, API/GPU calls, future Git objects or grader access.
  All three models were terminal before any candidate was privately graded.
- Each suite reports 25 skips and 31,001 deselections: upstream non-stress
  selection plus the already frozen literal-`/tmp` exclusion. Deselections are
  not executed tests. Frozen graders, including the previously documented
  behavioral adaptation for this issue, were unchanged.

## Actual upstream integration

Cognee 1.6.4, commit `f154b32a9e544dac73e7ddf2010327cf9988edcd`;
Enola CLI 0.4.26; Ladybug 0.19.0; LanceDB 0.39.0. Full installed SDK, native
Enola extraction, persistent graph and public `cognee.search(SearchType.CODE)`
were used. Not AtMem's vendored query helpers or an in-memory graph substitute.
After execution, all **2,663 upstream Python files** matched their installed
counterparts; upstream checkout was clean. The complete package list is
retained in protected evidence.

The upstream example's graph-only pipeline ran with `index_vectors=False` and
`skip_connection_test=True`; no LLM or embedding model was required. Caching
and dataset isolation remained on. Telemetry, tracing and automatic feedback
were disabled; the worker received an explicit key-free environment and a
separate benchmark home, not the owner's configuration.

A small benchmark-only read-only MCP transport forwards the upstream typed
`code_search` operations to the public SDK, without repacking its graph results.
It is **not** the complete upstream Cognee MCP server. A fresh process recovered
the indexed graph and queried real help-option symbols before solver dispatch.

Cognee's solver actually used:

1. `query_facts`, query `help_option`: three relevant symbols, source locations
   and relationships, including the command help methods and decorator.
2. `explore`, query `src/click/core.Command.get_help_option`: six nodes and six
   traversed edges, connecting the command, help methods and decorator.

Both calls completed without tool errors. The solver also inspected native
source and ran tests. No claim that graph access alone caused its passing patch.

AtMem used an independently installed current-branch wheel, with every bundled
product file verified against the wheel. Its packing implementation is the
unchanged literal-anchor candidate (`2d8b53e65f4b3c06628e191bb083ba95064f9fd51d5578c915ba424d68938a97`).
Wheel SHA-256:
`879f8cb7bdd49e914b52a364fb9f365ca0e2ace04d9e309f79ca3593f9be8df8`.
Metadata remains 2.3.8 for this private preview; this is not the public stable
2.3.8 artifact and no release or owner installation was changed.

AtMem provided its existing 4,096-byte automatic initial context and Code MCP
tools. The solver made one successful `code_context` request for help-option
collision evidence; that returned current implementations, relationships and
an existing parent-tree test reference. Cognee supplied graph navigation rather
than an invented AtMem-style automatic pack. This compares the specified
integrations, not graph engines with identical presentation and delivery.

## Harness artifact finding — original flag retained

The generic source-only patch collector flagged Cognee's seven `.enola` files
as `out_of_scope_patch`, even though the indexer, not the agent, created them.
Consequently the **original** Cognee row has `functional_pass=false` and
`budget_pass=false`, while its unchanged grader has `exit_code=0` and
`passed=true`. Do not silently turn that raw composite row into a pass.

The separate post-run artifact audit verified that all seven expected files
have both filesystem change time and modification time before the frozen
pre-dispatch record, and that no unexpected non-source/non-test paths were
changed. SHA-256 identities and timestamps are retained. The files were
unchanged setup artifacts, not unauthorized agent edits. The table above
therefore reports actual **test-suite outcomes**, not the raw composite policy
gate. No candidate was rerun or regraded. A future protocol should explicitly
inventory generated extraction artifacts before dispatch or place them outside
the candidate workspace.

## Interpretation

The short diagnostic establishes a working upstream comparison path. Cognee
delivered real structural evidence and produced a passing candidate. AtMem did
too, and was faster in this solver attempt, while Cognee used fewer input
tokens than AtMem. Native used the fewest total input tokens but missed the
three required collision cases. There is no token-saving win over native here.

The task is reused and public, with one stochastic attempt per arm, fixed order
and different provider delivery interfaces. These observations cannot settle
whether either integration generally helps, whether Cognee is superior, or
whether AtMem missed a particular upstream mechanism. No new AtMem tuning or
large study was started on the strength of this result.

## Retained evidence and checks

- Protocol: `specs/043-click-historical-replay/cognee-short-comparison.md`.
- Encrypted run: `click-cognee-short-20261018-v1`, internal benchmark home
  `cognee-short-20261018/vault`.
- Recipient-encrypted archive on MEM:
  `/Volumes/MEM/AtMem-Code-Replay-20261017/protected-cognee-short-20261018/click-cognee-short-20261018-v1.encrypted.json`.
- Private keys remain internal, in `keys-cognee-short-20261018`, not on MEM.
- Fresh-process, archive-only recovery: 17 events, 3 original model starts,
  3 complete attempts, 3 grades, 1 completed comparison; artifact audit verified.
- Archive SHA-256:
  `e07c2c0d3547aebb0b941b3f76d57b790e4b70b89bd0fb434c6773b5b02ad39b`.
- Harness controls: 63 tests passed (new transport contracts plus existing
  runner and replay contracts). These unit tests are not task-performance data.
- All benchmark model and worker processes are terminal. No full 19-task run,
  product retuning, commit, push, release or unrelated cleanup was performed.
