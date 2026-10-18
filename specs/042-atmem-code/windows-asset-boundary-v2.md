# Explicit bounded-asset profile and Requests-4356 control v2

V1 remains recorded as two pre-test source-bound stops. A read-only metadata
diagnostic found one ordinary tracked design asset, `ext/requests-logo.ai`, of
2,189,478 bytes. This is an environment/resource qualification issue, not a
model repair outcome. No task or test replacement is permitted.

Before another control, update the shared snapshot capture/decoder/export
resource profile and standalone evaluator consistently: recognized repository
asset suffixes `.ai`, `.png`, `.jpg`, `.jpeg`, `.gif`, `.ico`, `.pdf`, `.woff`,
`.woff2` may contain up to 4,000,000 bytes per regular file. All other files,
including Python and text, retain the 1,000,000-byte limit. Total snapshot
remains 40,000,000 bytes, with existing count/depth/path/no-follow/mutation
checks. The asset is retained byte-for-byte, not dropped, summarized or turned
into an unverified reference. Git blob/mode/membership verification still
applies. Executable source roots/extensions and protected tests do not change;
changing an asset remains an out-of-scope proposal violation.

This is an explicit new resource profile, not a claim that V1 passed unchanged.
It does not increase the model token/context budget, Docker limits, authority,
network access, source-code allowance or solver privileges. Tests must cover
exact large-asset capture, oversized-asset refusal, unchanged source cap,
source/public decoder agreement and attempted asset mutation refusal.

Run the same pinned Requests-4356 image/base, upstream script, tests and reference
patch once each for parent/reference under a new evidence run. Retain both
attempts, all output and failures; no model calls or favorable-outcome retries.
Keep other tasks' original controls and the first actual repair pair separate.
Parent/reference success alone does not qualify public-source/solver access or
establish an AtMem performance benefit.
