# Four-configuration normal-run qualification

Uses public tau2-bench task0 at commit
`b7ea9074c1cba482b30687fecdb5c8425fd6f619` (MIT). Exact model requests replay the
preserved native pilot; no paid API calls are made. All four configurations match
18 recorded requests, six native tool calls, conversation and final store state.
The AtMem configurations additionally verify six authoritative product operations
using an independent evaluator credential; the restricted worker cannot list
other workflows. Graph topology is identical across all four configurations.

Compressed arm records retain public conversation, native effect journal and
database snapshots. These are compatibility evidence, not a fresh agent score or
held-out improvement. The original native pilot's task reward remains zero.
Source and data provenance are in `summary.json`; generated artifacts are covered
by `SHA256SUMS.json`. README and upstream LICENSE are ancillary files.
