# Typed symbol ownership and observed query aliases

Bounded corrections following T087/T088. These affect nomination of source
evidence, not canonical memory, execution authorization or graph truth.

## T089: only symbols own syntax definitions

An arbitrary file/module/reference fact at line 1 must not become a function or
class merely because the source begins with one. Bind Python syntax definitions
only for `CodeSymbol` facts. Other fact types remain available in the graph and
may provide correctly labelled source anchors, but are not executable roots or
method inventories. Only actual symbol facts receive explicit-symbol name
weight. Validate the complete authorized generation before filtering, as before.

This corrects a reproduced case where a filename mentioned in a query promotes
an unrelated documentation example as a class. It is a type invariant, not a
repository, issue or test-path exclusion. Test both truthful non-symbol anchors
and unchanged symbol definitions, source integrity, scope and byte limits.

## T090: aliases are location hints, not runtime guarantees

Recognize explicit, unambiguous Python import aliases in the query's Python/
unlabelled fenced code, doctest prompts, or a standalone parseable Python query.
Use only observed top-level import statements; never execute query code. A
qualified reference through an alias may nominate the corresponding module/
package namespace, and a directly imported renamed symbol may nominate its
original spelling. Preserve ordinary reference extraction.

Do not hardcode common package abbreviations, infer imports from prose, resolve
dynamic imports, or use a conflicting/rebound alias. Conservative unresolved
cases keep the normal lexical/native fallback. Alias-derived nominations do
not prove re-export availability, runtime calls or developer intent. Every
emitted source byte retains the same authorization and freshness checks.

Keep the frozen v3 installation and failed-target comparison unchanged. These
corrections use the now-reused cohort for diagnosis. Static pack improvements
are not token savings; require separately installed, frozen matched model runs
and fresh confirmation before satisfying the unchanged 50%/20% goal.
