# Windows repository source-control qualification

This advances the multi-repository benchmark harness, not AtMem's measured
token benefit. No new coding-model calls or new repair scores occur here.
The first actual pair remains 4/8 targets each, with AtMem using 30.45% more
total input; the 20%/50% goal is not achieved.

## Current task state

| Original selected task | Parent target checks | Reference target checks | Regressions each | Source assembly and public export |
|---|---:|---:|---:|---|
| Marshmallow-1229 | 0/8 | 8/8 | 61/61 | previously verified; 76 public files |
| Marshmallow-1810 | 0/1 | 1/1 | 111/111 | verified; 88 public files, 768,607 bytes |
| Requests-1327 | 0/1 | 1/1 | 31/31 | v2 verified; 116 public files, 1,246,717 bytes |
| Astroid-934 | 0/1 | 1/1 | 312/312 | verified; 206 public files, 1,584,911 bytes |
| Astroid-1616 | 0/1 | 1/1 | 10/10 | verified; 276 public files, 2,050,771 bytes |
| Requests-4356 | collection error, targets missing | 111/115 | none declared | remains unqualified; retained separately |

The new assembly controls require every expected parent target to fail,
every reference target to pass, full regressions in both phases, no skips,
source-only policy compliance and byte-verified assembled trees. Task/base,
parser and source/test roots are pinned operator metadata; no model selects
them. Root and nested Astroid package tests are protected. The original
single-task validation default remains restricted, with generic controls
requiring an explicit operator profile.

Each new export is checked against the exact public base commit/tree, modes,
Git blob identities and the independently captured tracked-source fingerprint.
Only tracked regular public files enter the solver export: no future history,
untracked image runtime files, private test/gold patches, hints or evaluator
materials. Existing file/total limits and source checks remain enforced.

## Requests-1327 cache boundary

V1's two controls stopped at the 40 MB snapshot cap. Read-only metadata
inspection found 2,996 untracked `.eggs` dependency-cache files totaling
52,268,531 bytes, plus smaller build/metadata/cache files. Nothing was deleted.
The retained V1 failures are not changed to successes.

Explicit `selected-six-v2` evaluator projection excludes only top-level `.eggs/`
after checking the complete base Git listing and refusing any overlap with
tracked source. The cache remains untouched in the image. Default capture and
the earlier profile still include this root. No arbitrary ignore patterns,
solver-selectable roots or source/test exclusion is added. Other image files
remain captured and assembled byte-for-byte; the 40 MB cap is unchanged.
Source-only mutation rules still reject out-of-scope candidate changes.

V2 reproduces 0/1 versus 1/1 target passes and 31/31 regressions, with exact
assembly checks. The export contains precisely the 116 tracked public files,
not the dependency cache or other untracked image files.

## Evidence and remaining gates

Protocols:

- `specs/042-atmem-code/windows-selected-source-boundary-v1.md`
- `specs/042-atmem-code/windows-requests1327-source-v2.md`

Protected evidence runs:

- `external-windows-selected-source-boundary-v1-20261018`
- `external-windows-requests1327-source-v2-20261018`

Full controller streams are retained as ordered bounded chunks with digests
and receipt links, rather than omitted to fit one event. Recovery checks
reconstruct the full streams and compare parsed controllers with retained
results; this is retention verification, not independent replication.
Raw source/control outputs and failed attempts remain in the protected vault.

The combined replay/MCP/packing suite passes **324 checks in 26.83 s**. No
remote CI, package release or owner configuration change is claimed.

Next gates: bind the neutral public-test/proposal adapters to each pinned task
and image-runtime projection; qualify common test access and actual candidate
grading; then freeze the matched native/pack-only/pack-plus-tools cohort with
explicit environment attrition. The original six selected identities remain
listed; Requests-4356 must not disappear from accounting or be counted as a
failed agent attempt. No multi-repository benefit or confirmation run has yet
completed. T062/T077 remain open.

## Configured public-proposal and runtime adapters

The existing proposal/public-test workers now accept only operator-pinned task
settings embedded in their bootstraps. Model-input schemas remain unchanged.
Settings bind the exact selected task/base, authorized source/protected-test
roots, import layout, runtime projection and exact image-only artifact hashes.
Unknown/changed image artifacts are refused; source snapshots do not gain
access to private evaluator fields. Defaults remain the original first task.
Requests-1327 may select its exact root public `test_requests.py`, with that
task-specific default; other tasks cannot select arbitrary root Python files.

All eight actual Windows proposal controls pass:

| Task | Unchanged proposal targets | Reference proposal targets | Regressions each |
|---|---:|---:|---:|
| Marshmallow-1810 | 0/1 | 1/1 | 111/111 |
| Requests-1327 | 0/1 | 1/1 | 31/31 |
| Astroid-934 | 0/1 | 1/1 | 312/312 |
| Astroid-1616 | 0/1 | 1/1 | 10/10 |

These traverse the same public proposal decoder, exact Git membership/mode/
blob checks, frozen-source assembler and pinned upstream grader intended for
actual model patches. Image-only runtime bytes are preserved and no unused
gold patch is written into proposal workers. Reference candidates are built
from qualified snapshot differences over verified public source, not by
forwarding unchanged untracked image files. No skips, controller/worker failures
or new model calls. Raw streams remain in bounded protected chunks.

Four additional public-runtime plumbing probes pass, one per new task. Each
checks that its package imports from the submitted `/work` candidate (or
`/work/src` for Marshmallow), that `/testbed/.git` has been removed and that
the private evaluator directory is absent. Candidate digests match exactly;
full output is retained. These are explicitly authored harness fixtures, not
upstream test results, training records or repair scores. They do not claim
all public tests or every MCP host integration has been exercised.

Protocols: `windows-selected-proposal-controls-v1.md` and
`windows-selected-public-runtime-v1.md` in Spec 042. Evidence:
`external-windows-selected-proposals-v1-20261018` and
`external-windows-selected-public-runtime-v1-20261018`.
The full replay/MCP/packing suite passes **329 checks in 27.39 s**. No remote CI
or release claim. Next is matched host/staging and cohort accounting, followed
by actual native/pack-only/pack-plus-tools repairs. Independent confirmation
and the token/quality goal remain unachieved.
