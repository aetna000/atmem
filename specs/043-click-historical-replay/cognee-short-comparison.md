# Short upstream Cognee comparison

Owner requested a short Click run before the proposed cross-repository study.
This replaces that study's immediate execution scope, not its previous results.

## Frozen scope

- One task: the first chronological task in the existing qualified Click
  package, `b67832c` (help-name collision). Selection is positional, not based
  on a new provider result. This task has already been inspected and scored.
- Three fresh, serial sessions: native, upstream Cognee, current AtMem structure.
  No experience, retries, tuning, hidden-test feedback, API or GPU dispatch.
- Same permitted parent source, requirements, subscription `gpt-6-luna`, low
  effort, 180-second and 24-tool limits. Token threshold 500,000 input + output
  is audited after completion, not provider-enforced. Preserve failed attempts.
- Freeze exact installed artifacts, harness, source, grader and prompt before
  the first scored dispatch. Evaluate all three patches only after dispatches
  are terminal. Use the existing frozen full-suite grader and exclusions.

## Providers

Cognee is upstream commit `f154b32a9e544dac73e7ddf2010327cf9988edcd`
(package 1.6.4), not AtMem's vendored helpers. Use its complete installed SDK,
Enola-backed `get_code_graph_tasks`, actual persistent graph backend, and
`cognee.search(SearchType.CODE)`. The official example uses
`skip_connection_test=True`, `index_vectors=False`: no LLM or embeddings are
needed for this deterministic route. Keep caching and dataset isolation on.
No claim about Cognee's other retrieval or conversational-memory routes.

A small read-only benchmark MCP transport exposes the upstream `code_search`
operation/arguments interface and calls that public SDK unchanged. It is not
the full upstream MCP server and must be named accordingly. Qualify a real
indexed-symbol query through the transport before scoring. Disable telemetry,
tracing and automatic feedback; supply no API keys or inherited owner config.

AtMem uses a new isolated installed wheel of the current branch, with the
existing literal-anchor packing implementation unchanged. Record the wheel
hash and verify installed bytes. Its existing automatic 4,096-byte focused
initial pack and read-only Code MCP tools remain enabled. Cognee provides its
native graph-query tool, not an invented AtMem-style task pack. This difference
is explicit: the experiment compares these concrete structural integrations,
not graph-engine quality with delivery held constant. Native retains normal
source/search/test tools, but neither provider's graph or context.

Graph results are pre-change structural evidence; current source wins after
edits. Source-only solver workspaces exclude future commits and private tests.
Do not index evaluator history, accepted patches or grader materials.

## Reporting

Show full-suite correctness, budget status, total/cached/uncached input,
output, observed graph-tool calls, solver seconds, cold indexing and context
setup separately. Missing usage is unknown, never zero. Raw requests, streams,
patches and grades belong in protected benchmark evidence. This single reused
task is an integration diagnostic, not independent confirmation, significance,
or a general claim about which product is better. Setup failure blocks a
provider comparison; it is not evidence of no user benefit.
