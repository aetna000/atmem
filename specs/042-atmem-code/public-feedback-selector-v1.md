# Registered public-test selector repair

Prospective benchmark-only correction after the complete negative CD2 result.
It does not change the frozen CD2 worker, results, private tests or product.
T099's archive-only audit reads all 38 traces and all 39 public-test calls.
Nineteen calls are rejected during request validation. Seventeen pass source
paths rather than public test paths and must remain rejected. Two calls, both
Xarray-3812 arms, pass xarray/tests/test_options.py: a legitimate descendant of
the registered xarray/tests root that the validator wrongly rejects.

## Required behavior

Treat each operator-registered public-test directory as a directory, not just
the specially named tests directory. Accept canonical relative descendants and
existing supported pytest node selectors. An explicitly registered .py file
remains exact-only, with optional node selectors, never a directory prefix.
Use path-component ancestry, not string-prefix matching. Keep absolute paths,
traversal, backslashes, noncanonical paths, unsafe node IDs, source paths outside
the registered roots, unknown options and all existing budgets rejected.

No source-to-test remapping, implicit patch generation, dependency install,
patch-parser loosening, private-test access, score reclassification, model rerun
or old-worker replacement. The seventeen source-path mistakes are not bugs to
accept. Malformed submitted diffs, collection errors and timeouts remain visible
limitations. No claim this defect caused the quality gap: the two affected
requests belong to the same neither-passing pair, not the discordant pairs.

## Verification and future use

Exercise nested roots with unrelated fixture names, root/file exact matches,
node IDs, sibling-prefix escapes, traversal and file-as-directory rejection;
retain existing command/scope/budget gates. Reuse the same validator function
in host and sandbox worker bootstrap. The complete repaired source must be
frozen in any future public-test worker and qualified with unchanged-source and
actual-candidate controls before another matched study. Historical sources are
retained byte for byte in protected records and are never overwritten remotely.

AtMem relevance work remains required. This repair alone cannot satisfy the
structural-context token/quality objective or authorize fresh confirmation.
