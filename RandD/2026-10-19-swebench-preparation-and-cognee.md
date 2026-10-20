# SWE-bench preparation repairs and real Cognee qualification

2026-10-19. Source branch `feature/atmem-code-2.3.9`; private preview,
not a published package or a new SWE-bench score.

## Result

The corrected installed AtMem candidate passes current-source context and actual
MCP context/architecture checks on **five public repository snapshots**. Actual
upstream Cognee also loads the same SymPy extraction and returns graph facts.
No new model-solving attempt was dispatched during these repairs. A new paired
no-memory/AtMem/Cognee solver comparison is still required to measure user benefit.

| Public snapshot | Admitted files | Writer facts | AtMem context bytes | Installed MCP checks |
|---|---:|---:|---:|---|
| SymPy, `sympy__sympy-17139` source | 1,544 | 25,338 | 3,761 | Pass |
| Sphinx, `sphinx-doc__sphinx-8595` source | 993 | 6,566 | 3,838 | Pass |
| Matplotlib, `matplotlib__matplotlib-24970` source | 1,565 | 14,363 | 3,880 | Pass |
| Django, `django__django-16229` source | 3,353 | 14,011 | 3,787 | Pass |
| scikit-learn, `scikit-learn__scikit-learn-12471` source | 931 | 10,362 | 3,865 | Pass |

These are bounded preparation queries, not task-solving results or judgments that
the returned context is sufficient for the corresponding issue. SymPy revalidates
the exact encrypted retained worker artifacts before publishing; other final
checks reuse previously published generations. Their `index.status=unchanged`
means **not a cold extraction**, regardless of an early helper's mode label.
All checks use the same final installed candidate. The machine-readable
[receipt projection](2026-10-19-swebench-preparation-and-cognee.json) retains exact
snapshot IDs, receipt paths/hashes, source/query counts and runtime identity.

## What was wrong, and what changed

- The graph capture limit was 6 MB while the worker already accepted 24 MB.
  Graph indexing and freshness checks now consistently use 24 MB; strict
  execution capture defaults remain unchanged.
- The file guard counted unsupported assets before filtering. It now permits
  5,000 eligible source candidates with a separate 50,000-path discovery bound.
- Artifact/fact/insight, per-fact relation and graph-query limits were inconsistent.
  SymPy actually emits 214,645 relations across its writer facts, including a
  15,003-relation fact. Aggregate intake is now bounded at 500,000 relations;
  normalization produces 24,125 objects and 92,976 distinct relations here.
  Queries remain bounded separately and unqueryable generations are rejected
  before publication.
- Root-directory dependency rollups were incorrectly rejected as file paths.
  They retain their writer identity and must pass existing typed directory
  mapping; they are never invented source-file anchors.
- Mapping recomputed the full snapshot hash and split the same source file for
  each symbol. These invariant operations now happen once per mapping invocation.
- SymPy's complete logical generation is 105,037,873 bytes. A measured standard-
  library XZ fallback fits its lossless representation in approximately 14.7 MB,
  below the unchanged 16 MB physical-row limit. Decoding bounds dictionary/output
  memory and verifies identity binding, exact size, SHA-256, EOF and no trailing
  data. Original source and artifacts are not discarded. Logical generations
  remain capped at 256 MB; project bundles retain their independent 128 MB cap.
- Worker errors now surface fixed diagnostic categories rather than source-bearing
  stderr. Source authorization, secret screening, freshness and atomic publication
  remain in force.

The old approved worker does not silently change. The new wheel and explicitly
rebuilt offline worker are isolated from the original pilot runtime.

## Candidate identity and checks

- Wheel SHA-256:
  `1314dc5a309cd19c7ac0e7704a4cc5d18a77d4596cffbb2fef0c6ae549d2629d`.
- Installed Windows/WSL candidate: **346 package files matched the wheel**, zero
  mismatches. Metadata remains the private preview's 2.3.8 base version.
- Worker image:
  `sha256:9fed0943365daedd9ee3e2e08de8341c9b04b08c6309b1dc2c08aaaaf2abfdf1`.
- Worker was built offline from the existing pinned Enola image; extractor
  `0.4.26`, `v287`, not a new LLM extraction route.
- **358 affected tests passed** across knowledge, MCP, storage, product workflow,
  benchmark contracts and the Cognee probe. Whitespace/diff validation passed.
- No paid API fallback, GPU rental, package publication, owner-data movement or
  owner-data deletion occurred.

## Actual upstream Cognee

The probe uses the complete installed Cognee **1.6.4** SDK at clean source commit
`f154b32a9e544dac73e7ddf2010327cf9988edcd`; all **2,663 Python source files**
matched its installed package. It uses the supported
`get_code_graph_tasks(repo_path, snapshot_dir=..., index_vectors=False)` pipeline,
the real persistent backend and `cognee.search(SearchType.CODE)`.

The input is the verified public SymPy source/extraction snapshot, not a reference
solution, hidden tests, owner memory or AtMem's incorporated query implementation.
The CODE route needs neither embedding inference nor an LLM API key.

Cognee loaded the graph and returned three facts from a reported matching set of
23,698. The first **benchmark probe** incorrectly expected `nodes` instead of the
SDK's `search_result.facts`; its failed summary is retained. The corrected probe
requeries the same already-loaded graph, does not repeat ingestion, and returns
the identical response hash:
`a7410302bf64df06c46eff5aa0ffc1d94933a6098a8719bd76edcaf3e9280599`.
This was not a Cognee failure or a best-of-several solver selection.

Cognee preparation runs on Mac while these AtMem checks run on Windows/WSL.
Their preparation/query times are therefore **not** a controlled latency
comparison. No Cognee SWE-bench task score is claimed.

## Original pilot remains unchanged

| Original partial pilot | No memory | AtMem structure |
|---|---:|---:|
| Valid graded model attempts | 13 | 3 |
| Solved graded attempts | 12 | 3 |
| Product preparation failures | 0 | 10 |
| Environment-unavailable cases | 1 | 1 |
| Model-initiated AtMem calls | — | 0 |

Only three tasks have runnable paired results, and both configurations solve all
three. The operational preparation failures are real, but they are not ten wrong
model answers. The planned 30-task pilot stopped at the Windows disk reserve.
Its protected histories and result files were not rewritten using the new build.

The [earlier single-Click comparison](2026-10-18-claude-click-head-to-head.md)
also remains unchanged: all three providers solve the task; both graph integrations
use more input than no memory. It does not establish a general advantage.

## Next loop and current gate

The owner requested an outcome-oriented three-provider loop. The
[correction protocol](../specs/042-atmem-code/swebench-preparation-corrections-20261019.md)
sets separate validation and confirmation, fixed agent/tasks/budgets, retained
failures, and explicit delivery/hardware configuration. Aim for no lost completions
with materially lower input (20% is a useful target), and report both cold and
warm latency. Do not repeat until a favourable result or tune against confirmation.

The original runner exposed optional tools but did not inject AtMem context.
A new, separately frozen `--context-delivery automatic` mode now validates and
includes the real product source pack in the retained model prompt. It records
delivered bytes independently of voluntary tool calls, and pins the installed
wheel/interpreter/worker. Unit tests reject changed frozen manifests, invalid
source packs and unknown provider arms; an unwired Cognee arm cannot silently
run as no memory.

The actual three-way solver integration and confirmation remain open. Windows
free space reached the **48 GiB safety reserve**, limiting further staging. The
owner subsequently approved cleanup of unneeded previous AtMem runs. Fifteen
obsolete PyVista Docker images were removed: seven AtMem-labelled derived builds
and eight digest-pinned upstream caches from the stopped earlier experiment.
Image identities, build history for derived images and deletion results are
retained in `cleanup-pyvista-20261019T160340.json` and
`cleanup-upstream-pyvista-20261019T160445.json` under the Windows/WSL benchmark
root. All benchmark evidence, project files, current SWE-bench task images and
the pinned extractor are retained. Upstream images can be pulled again by their
recorded digests; derived images require rebuilding, not an undelete operation.

The second cleanup freed 29.8 GiB inside WSL. Windows host free space had risen
to about 50 GiB at its completion; virtual-disk reclamation does not necessarily
track Linux free space immediately. Online trim was used, without stopping WSL
or compacting its virtual disk. The 48 GiB dispatch guard remains unchanged.
The 15 benchmark contract/probe tests pass after cleanup. A preparation pass or
cleanup is not substituted for the requested comparison table, and no new solver
result is claimed here.
