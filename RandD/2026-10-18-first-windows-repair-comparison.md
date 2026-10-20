# First Windows repair comparison

This is one authentic issue integration pair, not a multi-repository result or
independent confirmation. The 20%/50% total-input reduction goal remains unmet.

## Matched results

Task: `marshmallow-code__marshmallow-1229`. Both arms start from the same
reconstructed source-only Git commit
`c1e7b95a735e8af5bdbfa6bab1e932b2373f0420`, based on upstream
`456bacbbead4fa30a1a82892c9446ac9efb8055b`. Execution uses Windows Ubuntu WSL2,
the same pinned Luna-low subscription CLI, public-test interface, issue,
resource limits and private grader. Frozen order: AtMem, then native.

| Measurement | Native tools | AtMem structure + optional Code MCP |
|---|---:|---:|
| Fully solved issues | 0/1 | 0/1 |
| Issue-specific checks passed | 4/8 | 4/8 |
| Regression checks passed | 61/61 | 61/61 |
| Total input tokens | 219,942 | 286,923 |
| Cached input tokens (included above) | 190,848 | 267,392 |
| Uncached input tokens | 29,094 | 19,531 |
| Output tokens | 1,210 | 1,496 |
| Solver time | 30.525 s | 28.588 s |
| Cold structural indexing | — | 1.764 s |
| Initial context preparation | — | 0.889 s |
| Initial structural context bytes | 0 | 3,243 |
| Tool calls | 12 | 11 |
| Completed Code MCP calls | 0 | 0 |
| Common public-test calls | 1 | 1 |
| Native command output bytes | 29,419 | 48,664 |
| Private grading controller time | 2.687 s | 3.421 s |

AtMem used **30.4539378563% more total input tokens**. Lower uncached input is
not the requested total-input saving. Solver time alone was 1.937 s lower;
adding the measured cold index and initial context costs gives 31.241 s for
AtMem versus 30.525 s native. These are component sums, not instrumented
wall-clock end-to-end latency, and exclude staging and grading. A single
sequential pair cannot establish a latency advantage.

## Observable behavior

Both patches change only `src/marshmallow/schema.py`, unwrapping a single List
container when applying nested options. Both remain incomplete under the
private target tests. Neither changes tests or other out-of-scope files.

The AtMem arm still performed broad native searches and source reads; its
command output was 19,245 bytes larger. No Code MCP retrieval was completed.
Prepared/written MCP protocol records establish exposure at the transport
boundary, not that the model used the tools or understood the initial pack.
The initial pack did not demonstrably replace exploration in this pair.
Inspection of the retained 3,243-byte initial pack shows that it omitted
`BaseSchema.__apply_nested_option`, the method both solvers eventually edited.
It included `Nested._nested_normalized_option`, several other helpers, class
registry lookup and a public test excerpt instead. This is a concrete
localization/coverage limitation on this issue, not evidence that all graph
retrieval fails. Adding this specific answer location after seeing the repair
would not establish generalization; broader frozen tasks must test any generic
selection improvement.
Tool-schema overhead, repeated context and source selection are hypotheses to
investigate, not separately established causes. Output bytes are not input
tokens. Do not tune against the hidden failed checks or repeat this issue
until it wins.

## Accounting and retained failures

Both actual repair attempts terminated normally and have complete CLI usage;
zero usage rows are missing. Stopped workspaces contain 76 captured files each,
with no observed remaining benchmark writers. Temporary authentication copies
are absent. Root-protected common-test evidence was recovered through the
authenticated AtMem API and retained with the raw model and grading records.

Two ownership-related setup failures preceded inference: a Git query after
ownership handoff, then an SQLite file whose parent directory was not writable
by the solver account. Both failures and the explicit pre-inference corrections
remain retained. They are not additional model attempts, successful repairs or
silent retries. No owner files were moved or deleted.

Authoritative encrypted evidence run:
`external-windows-first-repair-integration-v1-20261018`, including one
`external.first_repair_comparison` event, two actual model results, two captured
candidates, two private grades and two recovered public-test evidence streams.
Protocol: `specs/042-atmem-code/windows-first-repair-integration-v1.md`.

## Next decision

Keep this negative integration result separate from historical Click tuning.
The predeclared broader comparison still distinguishes native, pack-only V1
and pack-plus-MCP V2. It needs the other fixed task environments qualified
before a matched batch; different-repository confirmation remains unrun.
No candidate promotion, accepted token reduction, release or broad utility
claim follows from this pair. T062 and T077 remain open.

Local verification after recording the result: 304 replay/MCP/packing checks
passed in 26.44 s; tracked diff whitespace check passed. The Spec Kit inventory
check completed without error. These checks do not add benchmark observations.
