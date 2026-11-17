# Release evidence — AtMem 2.3.15b2

Status: release candidate under validation; not yet published.
Branch: `feat/measured-memory-adaptation`; public PR#38.
Implementation/pilot source: `a5b1bd9`; beta preparation: `b26731b`.
AtMem 2.3.15b2 / bridge2.3.15-beta.2; unchanged AtBot 0.1.1 / AtFlows 0.1.8.
Stable remains2.3.14. Website update requires separate owner merge/deployment.

## Applicable coverage

| Surface | Change / gate |
|---|---|
| Core memory, authority, context | No behavior/schema change; Python/native regressions and invariants required. |
| Experimental study | New owner-only SDK/CLI;17 encrypted-boundary/tool/runner tests passed locally. |
| Model/benchmark | One preregistered public database pilot completed:497 calls,USD 0.07761425; revision failed, no learning claim. No new DolphinBench run. |
| Evidence/privacy | Existing scoped encrypted feedback ledger and format 4; exact exchanges retained; owner-only inspection. |
| AtBot/AtFlows | Pins unchanged;21 AtBot tests passed. No companion tag required. |
| OpenClaw | Version alignment only; local typecheck/build/test/smoke all passed. Hosted matrix pending; latest2026.11.5 declaration parser/fixture reviewed separately. |
| Docs/website | Public manifest72 pages validated; governed tool inventory passed. Separate private source-pin PR pending public main. |
| Package | Wheel/sdist built, twine checks passed, wheel rebuilt from sdist. |
| Clean installation | Native arm64 fresh environment: dependency check, CLI/wheel, delegated context, HMAC transport and encrypted round-trip smoke passed. |
| Persisted upgrades | Local persisted upgrades from 2.3.14 and 2.3.15b1 passed; CI matrix expanded to include both. No new canonical schema migration. |

## Local environment limitations (not hidden passes)
The first broad local Python run was interrupted after3 failures,703 passes,
62 skips and 40 fixture errors. The independently installed optional DolphinBench
source imported missing`tiktoken`; that dependency was then installed. The failures
also included an absent historical wheel at `/Volumes/MEM/...` and two sandboxed
Rosetta child-process failures from the x86_64 Conda test interpreter. A fail-fast
corrected-environment attempt was stopped to avoid repeating unrelated external
benchmark fixtures. The applicable package suite excludes`tests/benchmarking`;
its result and hosted full-source Python gates are recorded below when complete.
No test was rewritten to turn these environment failures into a pass. The clean
installed-artifact checks used native arm64 Python 3.12 to avoid the Rosetta issue.

## Study transport qualification
One protocol-only request was refused with HTTP404 because strict route matching
included unsupported`temperature`. No benchmark question was sent. Its conservative
unknown reservation was USD 0.0005773; actual billing is unavailable. Metadata
inspection identified supported parameters, then one corrected protocol request
succeeded on OpenAI/GPT-6 Luna:47 tokens,USD 0.0000111. The fixed supported settings
were committed before the preregistered pilot; no model/provider fallback or final
case rerun occurred.

## Pending completion
- Final real-pilot result, honest limitation/negative findings and raw receipt pins.
- Applicable local Python and hosted PR checks, persisted-upgrade gates.
- Public main merge, exact annotated beta tag, publication workflow and registry/install verification.
- Private website PR (owner review pending; no merge/deployment).

## Private website preview
Isolated private worktree preserves the existing author and SSH remote. Stable
install target remains2.3.14; preview metadata updates to2.3.15b2. Claim registry
review found no existing production claim changed by this experiment; no learning
or performance marketing claim was added. Review-mode import/build/all gates/docs
tests and 84 browser tests passed. Final immutable main pin and publishable import
remain pending public merge. No private merge or deployment performed.

## Applicable local Python result
The core suite finished with 4014 passes,86 skips,2 expected failures and3
environment failures. Both archive failures used an external TMPDIR for keys
that their existing export contract requires to stay internal; both passed when
rerun with internal temporary keys. The optional Cognee differential encountered
a stale directory without Git objects; the exact pinned upstream commit was
recovered and its independent original-method differential passed. No product
code or assertions were changed for these failures. Full hosted checks on the
final commit remain required.

## Finished pilot

Manifest8ebf796ccce5c511feb421164c46e3249f2dda2f8339c165a13ebd66e699f558;
At pilot completion, source a5b1bd9 matched both frozen implementation-file digests.
All 80 final condition trials completed; primary strict counts:no-memory7/20,
transcript 5/20,generic 6/20,revised 5/20. Upstream parser counts9/20,7/20,7/20,6/20.
Validation both 0/5, tie retained generic. This is a failed intervention; no further
candidate/model campaign was run. Exact raw content-free metrics and limitations
are checked into Spec 052; the full Home stays encrypted on external MEM0.

## Python 3.10 hosted correction
The existing real multiple-statement refusal test failed because Python3.10 uses
`sqlite3.Warning` instead of later versions' `ProgrammingError`. The adapter now
refuses either consistently. This is a post-pilot compatibility guard, not a
changed scorer or rerun; final hosted gates are repeated on the corrected source.

## Hosted macOS scheduling correction
Required jobs on `macos-latest` (currently macOS 26 ARM64) were canceled with
"The job was not acquired by Runner of type hosted even after multiple attempts"
and an explicit ARM64 capacity annotation. Pin CI, feedback contracts, installed
AtMemCode and publication to supported `macos-15` ARM64 instead. This changes the
image/pool, not architecture or assertions; every prior OS/Python matrix cell is
retained. The macOS feedback deadline becomes 30 minutes (matching Windows) after
a job timed out despite passing the test step, while Linux remains 15 minutes.
This cannot guarantee hosted capacity; new exact-commit runs must prove success
before tagging. No model calls, pilot reruns, package behavior or scorer changes.
