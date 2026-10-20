# Complete-query retrieval correction

## Observed defect and bounded correction

The previous automatic benchmark adapter passed only the first 1000 UTF-8
bytes of each issue to retrieval. The solver still received the complete issue.
This is a lossy retrieval-input adapter, not proof that the graph or classifier
is wrong. AtMem's core context method already accepts a complete task; the
public Code MCP boundary is now additively raised to 4000 UTF-8 query bytes.
Search/graph query bounds, authority, source checks, graph algorithms, nomination
and the 4096-byte output budget are unchanged. The new adapter explicitly
selects complete input and refuses overlong requests instead of clipping them.
Its legacy default remains available for exact historical replay.

| Original validation issue | Full issue bytes | Previously omitted bytes | Prefix / full context bytes |
| --- | ---: | ---: | ---: |
| SymPy 17139 | 1,916 | 916 | 4,085 / 3,823 |
| Sphinx 8595 | 676 | 0 | 3,999 / 3,999 |
| Matplotlib 24970 | 1,758 | 758 | 3,809 / 3,809 |
| Django 16229 | 1,259 | 259 | 4,066 / 4,079 |
| scikit-learn 12471 | 2,145 | 1,145 | 3,996 / 3,715 |

All five **actual installed Windows/WSL MCP** prefix/full request pairs pass
current-source, byte-budget and content-hash checks. All old prefix outputs
match the original archived adjacency qualification hashes. Three full-query
outputs change; this is not evidence that they are better. No model, private
grade or generated training observation is used in qualification.

## Installation and integrity

Private wheel: `dist/atmem-code-full-query-20261019/atmem-2.3.8-py3-none-any.whl`.
SHA-256: `add4e1a14dce55c4ebd099f767d5cf4bca1d421d98250099cbb06e587f7ece48`.
Relative to the compact wheel, **only `atmem/knowledge/code/mcp.py` changes** in
the package, for the additive context-query bound. All 347 package files match
source and installed Mac bytes; Windows verifies all 347 against the wheel in
each actual qualification. Mac installs the existing eight-package Code extra.
Python 3.10 grammar and pinned licensed-import reproduction pass. Mac's twelve
installed handler/delivery-serialization controls pass; these are not twelve
independent host-client processes. No owner install, registry or release.

Qualification root:
`/Users/javadtaghia/Library/Application Support/AtMem Benchmarks/full-query-context-qualification-20261019`.
All six zero-model evidence runs independently recover from encrypted MEM
archives with original-vault access denied. Late-reference, multibyte, explicit
over-limit refusal, default replay, projection tamper and request/runtime binding
controls are included in **101 passing focused checks**.

## Completed fixed screen

Design: `specs/042-atmem-code/full-query-context-screen-20261019.md`.
The prospective ten-attempt screen uses all five previously inspected validation
tasks and fresh native/AtMem outcomes, with the unchanged official grader,
solver, budgets and alternating order. No new held-out claim, favorable subset
or reuse of model outcomes. Both model tool catalogs are workspace-only; AtMem
supplies its actual complete-query source pack automatically. This is benchmark
adapter delivery, not a newly qualified native host-hook path or proven model
use. Qualification projections are checked against their protected original
requests/responses before a model can launch.

Root:
`/Users/javadtaghia/Library/Application Support/AtMem Benchmarks/swebench-full-query-context-screen-20261019`.
Live projection: `2026-10-19-swebench-full-query-context-live.json`.
All ten attempts complete, with five official full passes per arm and complete
usage. Both model tool inventories are identical (workspace-only, 568 bytes of
compact-JSON definitions). Source context is supplied in all five AtMem prompts;
this establishes delivery, not that the model used it effectively.

| Metric | Native | Full-query AtMem |
| --- | ---: | ---: |
| Tasks fully solved | 5/5 | 5/5 |
| Complete input tokens | 96,527 | 142,326 |
| Output tokens | 8,674 | 8,810 |
| Median agent execution seconds | 46.77 | 40.92 |
| p95 agent execution seconds | 95.04 | 75.02 |
| Median indexed-workspace context + agent seconds | 46.77 | 80.02 |
| Median measured setup + agent seconds | 63.92 | 160.54 |
| Total indexing seconds | 0 | 215.61 |
| Workspace calls | 24 | 22 |
| Retained workspace text bytes | 17,528 | 19,652 |

The input-saving target **fails: 47.45% more input**. Every individual task uses
more input with AtMem. Agent-only median is 12.51% lower, but this does **not**
mean users wait less: adding measured context acquisition reverses that result,
even before indexing. The complete task screen does not demonstrate improved
end-to-end coding efficiency. Fewer workspace calls alone are not a token win;
the added context remains in subsequent model inputs, and tool-output volume
also differs. These observations are not an exact causal decomposition.

| Task | Native input | AtMem input | Native / AtMem agent seconds |
| --- | ---: | ---: | ---: |
| SymPy 17139 | 13,906 | 22,033 | 47.49 / 33.11 |
| Sphinx 8595 | 22,653 | 35,350 | 37.90 / 40.92 |
| Matplotlib 24970 | 22,874 | 33,708 | 46.77 / 53.99 |
| Django 16229 | 26,518 | 33,064 | 95.04 / 75.02 |
| scikit-learn 12471 | 10,576 | 18,171 | 28.40 / 27.79 |

All ten final model streams and grades independently recover from six encrypted
MEM runs, original-vault access denied. Actual model/CLI are claude-opus-5-5 /
2.1.281; no test or dependency files are modified. Broad verification after the
query change: **1,132 passed, one expected failure in 486.27 seconds**. Extra
transport and artifact helpers have their separate focused tests; these are
not added to the broad total as independent evidence.

### Explicit infrastructure stop and recovery

After native Django's complete model output/patch was captured, the next remote
job loader waited on stdin EOF and hit its 420-second SSH timeout. No evaluator
container was running at diagnosis. The original stopped snapshot independently
recovers eight model streams. The allowed transport-only repair uses newline
framing and explicit inherited stdin EOF; all evaluator/other helper sources
remain byte-identical. The official grade is recovered from the original patch,
using the original terminal expression. Only the two unstarted scikit-learn
cells then run. **No captured model is rerun.** Both locks, original stop,
recovery and final completion remain in the final archive; the stopped archive
is not overwritten. Three verified owned stale stdin readers were terminated;
no owner process or data file was removed.

The infrastructure stall is not counted as agent execution time. It is retained
and disclosed, not silently erased. See
`specs/042-atmem-code/stdin-transport-recovery-20261019.md` and the protected
`infrastructure.grade_recovery_*` receipts for the exact transport/source checks.

The previous compact screen remains a failed token-saving result (46.84% more
input) in `2026-10-19-compact-code-interface.md`; no prior result is replaced.
Neither experimental mode is promoted as an efficient default. The full-query
input fix remains valid, but the >=20% efficiency goal and broader SC-013 stay
unmet. This small reused-task screen cannot establish research superiority.

## Complete product artifacts, not just hashes

All twelve current private benchmark wheels (13,384,457 original bytes) are
retained as complete bytes in a separate encrypted evidence collection:
`/Volumes/MEM/AtMem-SWEbench-Threeway-20261019/swebench-product-artifacts-20261019`.
A fresh verifier recovers the inventory and every wheel from the archives,
checks original byte counts/SHA-256/ZIP integrity, and cannot open the original
vault or read original wheel files. Keys stay in the restricted local benchmark
directory. This is product-wheel recovery, not a complete offline Docker,
dependency, model or filesystem reconstruction. No publication or release.
