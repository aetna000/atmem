# Source-location hints for structural nomination

The completed layout/reference diagnostics reproduce all nineteen CD1 packs
and preserve the negative 9.317165272% score. Five combined packs change, but
some roots remain unrelated. A concrete missing capability is that an explicit
source URL with a line anchor is not used to nominate the referenced symbol.
The original Pylint-7277 issue provides such a link; the current lexical root
is elsewhere. That observation motivates a general navigation capability,
not a task-name rule or a measured causal claim.

## Scope and boundaries

Parse at most eight HTTP(S) URL hints with fragments `#L<line>` or
`#L<start>-L<end>` (also permit `-<end>`). Never fetch or resolve a URL. Reject
credentials, backslashes, NULs, traversal components, malformed/reversed ranges
and lines beyond the verified current file. Match a decoded URL path only to
existing authorized source paths by exact suffix, choosing the longest match;
do not guess by basename. No new file, scope or source object is authorized.

Use the hint only to nominate existing syntax-bound CodeSymbol candidates whose
source span contains the entire hinted range. Prefer the innermost matching
symbol over an enclosing class. Unmatched or unsupported hints leave ordinary
nomination available; never invent an executable definition for a file fact.
The URL/revision is an untrusted query hint, not proof of current source state.
Final excerpts and receipts use the actual authorized current source identity,
with all existing source/freshness/budget/governance checks and omission labels.

## Verification and execution boundary

Capture the complete preceding layout/reference source chain before editing.
Only the hint helper, its binding, a candidate nomination field and lexical
priority branch may change. Test nested symbols, exact/ambiguous paths,
percent-encoding, source bounds, unsupported hints, credentials and traversal;
prove no network or query-code execution and preserve all existing gates.

Extend the recorded diagnostic runner by explicit profile rather than creating
another experiment-specific execution stack. Use bounded stdin transport for
large reader programs, never shell interpolation or oversized argument strings.
Require all nineteen original packs to reproduce from the saved CD1 packer,
record every combined counterfactual/ranking, and preserve all failures. Static
results are reused-data diagnosis only. A separately installed preview and
prospective paired model protocol remain required before claiming any measured
token or task improvement. Untouched confirmation remains required for T062.
