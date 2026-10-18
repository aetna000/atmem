# Windows benchmark worker qualification

The owner explicitly authorized Windows benchmark execution on 2026-10-18.
No Mac cleanup, move or deletion was performed for this migration.

## Observed environment and setup

- Existing Ubuntu 24.04.1 WSL2, native x86_64, kernel
  `6.18.54.1-microsoft-standard-WSL2`, systemd.
- 12 logical CPUs; approximately 31 GiB RAM and 8 GiB swap, initially unused.
- Windows physical free space observed at about 278 GiB. WSL's sparse virtual
  disk reported approximately 944 GiB free; that is not physical capacity.
- Installed Ubuntu `docker.io` and its required dependencies inside WSL;
  daemon reports Docker 29.1.3 x86_64. No Windows Docker Desktop installation,
  owner application configuration changes or household credential copies.
- Downloaded and verified the same immutable first-task amd64 image:
  `swebench/sweb.eval.x86_64.marshmallow-code_1776_marshmallow-1229@sha256:3ea6d8d3b8ad25509c6058af273c8f7e1703c5584cae8516d16c02639d5253b6`.

## Actual public-test execution

Protected run: `external-windows-public-base-v1-20261018`.

The request reuses the verified 76-file public export from
`external-solver-source-v1-20261017`. The actual container worker bootstrap
digest was checked against retained `external-public-tests-v1-20261017`
before dispatch. Mac v1's resource stop remains retained, not overwritten.

The existing controller body is reused with only its free-space expression
changed to the minimum available space on WSL `/tmp` and physical `/mnt/c`.
The threshold remains 8 GiB. Exact controller source, transport, container
command, public request and raw returned streams are retained in encrypted
AtMem evidence. Evidence keys remain on the Mac; no vault copy was required.

Container limits remain one CPU, 1 GiB RAM, 128 PIDs, no external network,
no host mounts, dropped capabilities and no-new-privileges. Execution uses
the cached digest-pinned image. Public tests run on unchanged public source
in `/work`, without forwarding private evaluator material or Git history.

Observed result: **908 passed, one warning, 1.80 seconds** reported by pytest;
controller elapsed **3.1827342219999935 seconds**, exit zero, no reported
worker/controller failure or output truncation. The worker reports removal
of the image's original Git object store. Solver calls: **zero**.

This qualifies unchanged public-test execution only. It does not establish
Windows solver sandbox isolation, model tool exposure, complete token capture,
hidden-grader migration, AtMem benefit or independent transfer confirmation.
Native versus AtMem comparisons must share this Windows environment; do not
pool these timings with earlier Mac/amd64-emulation runs. The 50%/20% goal
remains unachieved.

## Subsequent source/grader and shell controls

`external-windows-source-boundary-v1-20261018` qualifies both phases against
the retained Mac worker bootstrap and same digest-pinned image. Parent:
0/8 target passes, 8/8 target failures, 61/61 regression passes. Reference
submitted through the assembly boundary: 8/8 target passes, 61/61 regression
passes. No skips, reported controller failure or cleanup failure. Controller
elapsed 3.707s and 2.668s respectively. This is evaluator qualification, not
an agent-produced repair. Private evaluator inputs remain outside solver
workspaces; transfer uses SSH and anonymous controller files in WSL RAM.

A dedicated Linux CLI 0.162.1 was installed under
`/home/jt/atmem-benchmark-runtime-20261018`, without replacing the existing
Windows CLI. Native Linux executable SHA-256:
`628e35487d888a28f0427fc37501da529dd3d81fcbad7a2c3421c1e8670d92e1`.

`external-windows-shell-isolation-v1-20261018` read the public marker and
denied two existing private canaries, then its probe stopped on socket
creation `PermissionError` before attempting connection. V2 explicitly
handles that denial and places TMPDIR separately from CODEX_HOME. Permissions
were not relaxed. `external-windows-shell-isolation-v2-20261018` passes the
real workspace-read, private-open denial and network-denial checks. Neither
shell control invokes a model; these are not host/model-consumption proofs.

The first native discovery preparation rejected an auth-file layout
assumption before inference. V2 requires the isolated CLI's own `login status`
to confirm ChatGPT subscription authentication, rather than inferring it from
an optional JSON field. Its prompt, model, caps, public source and permissions
are unchanged. Normal Windows user configuration is not edited. Only the
specific existing CLI auth file is temporarily copied into a private WSL RAM
profile, an actual sandbox read-denial check is required before inference,
and that credential copy is unlinked in the controller's `finally` block.
Credential bytes are never sent to the Mac evidence vault or MEM. This
clarifies the earlier setup statement: no household credentials were copied
for Docker installation; the subsequent inference diagnostic uses this one
bounded, temporary CLI credential copy.

## Installed AtMem and actual client qualification

The native read-only turn completed under
`external-windows-native-discovery-v2-20261018`: exit zero, no stop reason,
five tool calls, 15,537ms; host-reported input 88,405 tokens, including 78,208
cached tokens, output 596 tokens. The source-backed answer traces Schema.dump,
its helper and Field.serialize. Post-turn capture found no live workspace
writers, no changes/deletions to the original 76 public files and no remaining
temporary CLI credential copy. One additional file was sandbox-generated:
`.solver-tmp/codex-bwrap-synthetic-mount-targets-1000/lock`.

This diagnostic also exposed missing `rg` in the Linux native-tool PATH. It
was installed before scoring, together with the venv and SQLCipher build
dependencies needed for the isolated product installation. The diagnostic is
not a fair control for benefit inference. Before scored trials, tool scratch
must live in its own explicitly writable, isolated directory outside source;
do not retrospectively exempt the lock from a scored proposal or silently
alter original source identity.

`external-windows-product-build-v1-20261018` built and installed the current
product source in a dedicated venv. All installed Python module bytes match
the retained source manifest. Wheel SHA-256:
`bfadd313e398c6cf3507c4da941fe8bfb220c3cf27f71867b80f8cef0f6ecfc4`.
Package version metadata remains 2.3.8; this is an isolated modified-source
preview, not the published 2.3.8 artifact or a release.

`external-windows-extractor-build-v1-20261018` successfully built the existing
audited recipe for native amd64. Exact local image:
`sha256:62e15650d96e24eb4c5adce548ee711425e4a91f1a87ab9f9a8772a78ed724f3`.
The first post-build inspection had malformed transport argv; its failure
is retained. A corrected read-only inspection verified image identity without
rebuilding. No model outcome affected dependency or source selection.

`external-windows-product-index-v1-20261018` uses the installed product's
existing ProductLane/CodeRuntime, encrypted household, CodeKnowledge and
ExtractionWorker, not a new graph engine. The public source is reconstructed
into a one-commit local Git snapshot with no upstream history; its identity
and original authentic base identity are distinguished in retained evidence.
The resulting generation has 440 objects and 998 relations; exclusions are
explicit (four ignored configuration/hidden files, 33 unsupported-extension
files, two secret-screen exclusions). Indexing took 1,754ms and context
preparation 901ms. The prepared context is 3,594 bytes under a 4,096-byte
budget. Changed source is withheld; exact restoration restores currentness.
These are one-instance setup observations, not a performance benchmark.

`external-windows-mcp-discovery-v1-20261018` completed normally with real Luna-low
calls to code_context and code_source, two tools, 12,239ms, host-reported input
53,001 tokens including 46,976 cached tokens, output 502 tokens. Both returned
source responses independently match the frozen indexed source bytes using
the existing source_observations verifier. Before inference, the actual shell
barrier denies the temporary CLI auth, encrypted product database and product
key file. Tool scratch is separate from the source root. The model was
explicitly instructed to use MCP for this wiring diagnostic: **do not compute
or claim savings against the earlier native diagnostic**. Prompts and native
tool availability were not matched; neither run repairs an issue.

Remaining next execution work: candidate-proposal-to-private-grader integration
(the qualified existing worker still accepts fixed diagnostic phases only),
prospective matched Windows manifests and the repository-disjoint comparisons.
Normal completed-turn usage is observed; interrupted-turn completeness is
still unproven. No missing receipts may be imputed or failed rows dropped.
The token/quality goal remains open.

## Actual proposal-to-grader integration

The evaluator-only `solver_proposal_worker.py` now accepts a bounded public
candidate through an exact private/public role envelope. It reuses the public
decoder, existing source policy, assembly/tree installer and pinned upstream
grader. Public base membership, modes and Git blob bytes are checked. Candidate
test edits are ignored in favour of frozen tests; out-of-scope changes and
image-only runtime collisions are refused. The unused reference patch is not
written into the evaluator filesystem. This is not an adversarial anti-cheating
guarantee for arbitrary code inspecting its private test process.

The first Windows control stopped in the SSH wrapper before container execution:
the wrapper and reused controller both attempted to consume stdin JSON. Its
failure remains under `external-windows-solver-proposal-control-v1-20261018`.
The shared Windows transport now decodes once, with three regression checks;
it retains the original controller logic, both 8 GiB space checks (WSL and
physical Windows volume), output/time limits, cleanup and RAM-only spooling.

The explicit transport-corrected continuation
`external-windows-solver-proposal-control-v2-20261018` verifies the unchanged
worker bootstrap and qualifies both proposals:

| Evaluator control, not model repair | Target passes | Regression passes | Prior assembled bytes match |
| --- | ---: | ---: | --- |
| Unchanged public proposal | 0/8 | 61/61 | Yes |
| Evaluator-only reference proposal | 8/8 | 61/61 | Yes |

No skips, reported controller/worker/cleanup failures or solver calls in those
controls. Both exact assembled digests match their earlier qualified controls.
The public worker bootstrap also remains byte-identical after sharing its
module-construction helper. The focused proposal/public/source-boundary checks
pass 41 cases; the Windows transport/proposal group passes 15 (overlapping).
Both new test files are included in the CI definition; no remote CI run claimed.

Combined replay/MCP/packing regression suite after these additions:
**290 passed in 35.81s**. Windows inspection confirms no remaining benchmark
containers after the two controls. This does not close the remaining model
comparison or cross-repository gates below.

Agent repair attempts still need the matched prospective manifest, public-test
access usable in both arms, stopped-workspace capture and usage binding. The
other preselected task environments remain unqualified. No model repair score,
token benefit, completed T077 or completed optimization goal is claimed here.

## Common public-test access for all arms

The benchmark-only common run_public_tests tool now reuses AtMem's MCP transport
and full protected evidence service. It tests a submitted text diff against the
verified public base, not an assumed live agent worktree. The final private
grader will still receive the actual stopped workspace. No concurrent live-tree
capture or relaxation of the stopped-source capture precondition is introduced.
Malformed/out-of-scope paths, binary/symlink/submodule and rename/copy patches
are rejected. No model can select a host path, image, socket or private grader.

`external-windows-public-patch-control-v1-20261018` actually executes unchanged
source and an explicitly hand-authored, comment-only binding probe in the real
public repository. Both pass the public tests with no worker/controller failure;
their complete tested candidates match the intended bytes and their digests
differ. This marker is a plumbing fixture, not training or performance data.

`external-windows-common-tests-mcp-control-v1-20261018` verifies real stdio replies
1–4 through the Windows/WSL privileged broker from the ordinary WSL user. The
registered tool executes the unchanged public tests (exit zero) and rejects
a caller-supplied root with JSON-RPC -32602. Only run_public_tests is advertised;
no generic execution or memory-mutating tools. Docker groups and owner CLI
configuration are unchanged. The full raw result and tested candidate, not
just the displayed tail, are captured through AtMem evidence. Authorized API
inspection recovers seven full events, including the refused request/response;
the actual service reports encrypted/full protection. These recovered events
and raw transport streams are themselves retained in the Mac evidence vault.

`external-windows-common-tests-native-barrier-v1-20261018` stopped because the
namespace hid the real operator preset as ENOENT instead of returning EACCES.
The external protected inspection proves the host preset exists. V2 accepts
either denial form, without changing permissions, and passes: source marker
is readable, operator preset is inaccessible, and the Windows root-interoperability
executable cannot start from the native sandbox. This is a check of the tested
direct broker path, not a universal WSL escape guarantee. Zero model calls.

`external-windows-common-tests-clean-env-v1-20261018` verifies broker startup
and tool listing under the same cleared environment pattern as the solver
launcher, without inherited WSL/provider variables. No model call or test rerun
is needed for that startup check. Native and AtMem trials must receive the same
common public-test interface; only the AtMem arm receives structural context
and optional code-retrieval tools. The common transport is benchmark scaffolding,
not AtMem memory/structure in the native arm.

The expanded combined replay/MCP/packing suite passes **304 checks in 25.25s**;
the new bridge tests are included in the CI definition (not remotely executed).
Actual model/patch/counter binding and matched repair manifests remain open.
Do not treat these controls as a token-saving result or close T062/T077.

## First actual repair pair completed

The subsequent frozen Windows integration pair now has complete native and
AtMem usage, stopped candidate captures, actual private grades and recovered
common-test evidence. Both pass 4/8 issue checks and 61/61 regressions; neither
solves the issue. Native uses 219,942 total input tokens, AtMem 286,923
(30.4539378563% more). AtMem completes zero Code MCP calls. Two pre-inference
ownership failures and their explicit corrections remain retained separately
from the two actual model attempts. No owner files moved/deleted.

See [the complete comparison](2026-10-18-first-windows-repair-comparison.md)
for latency components, usage, source binding and limits. This supersedes the
earlier pending-first-pair statements, not the remaining multi-repository and
confirmation gates. T062/T077 stay open; no token-saving goal achieved.

## Remaining fixed task images staged on Windows

All five other preselected images were pulled by their previously recorded
immutable amd64 identities, with at most two concurrent pulls. Each then passed
the existing constrained shell/isolated-Python control and an image identity/
architecture check. Physical Windows storage and WSL storage both retain the
8 GiB minimum; logs spool in RAM. No task replacement, task setup/test scripts,
new coding-model calls or Mac cleanup was involved. Each newly generated
runtime-control container was checked absent after cleanup; cached images stay
on Windows for the next stage.

| Task | Pull | Constrained interpreter control |
|---|---|---|
| marshmallow-code__marshmallow-1810 | passed | passed |
| psf__requests-1327 | passed | passed |
| psf__requests-4356 | passed | passed |
| pylint-dev__astroid-934 | passed | passed |
| pylint-dev__astroid-1616 | passed | passed |

Evidence: `external-windows-remaining-images-v1-20261018`, retaining prospective
jobs, every pull output and every runtime result. These are interpreter/image
controls only: parent/reference grading and neutral source/solver adapters
still need qualification on these five tasks before the broader repair batch.

## Remaining task parent/reference controls

The grader now binds each preselected instance to its exact base and upstream
parser (Marshmallow, Requests or Astroid). Original single-task public-proposal
validation remains restricted by default. The full replay/MCP/packing suite
passes **311 checks in 26.33 s**, including identity/base and parser rejection
checks. Spec Kit inventory and tracked whitespace checks pass.

The prospective `windows-remaining-reference-controls-v1.md` control executes
ten fresh parent/reference containers on Windows, with no model calls. Four
tasks qualify; one stops before tests. No task is replaced or failure dropped.

| Task | Parent target checks | Reference target checks | Parent/reference regressions | Control |
|---|---:|---:|---:|---|
| marshmallow-code__marshmallow-1810 | 0/1 | 1/1 | 111/111 each | passed |
| psf__requests-1327 | 0/1 | 1/1 | 31/31 each | passed |
| psf__requests-4356 | not executed | not executed | not executed | source-file bound stop |
| pylint-dev__astroid-934 | 0/1 | 1/1 | 312/312 each | passed |
| pylint-dev__astroid-1616 | 0/1 | 1/1 | 10/10 each | passed |

The four qualified parents have actual target failures, references resolve
fully, and regressions have no skips. Requests-4356's two workers exit 1 at
`tracked_base`, not at grading: a subsequent read-only metadata diagnostic
identifies `ext/requests-logo.ai`, a regular tracked 2,189,478-byte asset, as
exceeding the existing 1,000,000-byte per-file bound. It is not a failed agent
repair, parser failure, missing source, or corrupt image. V1 remains terminal
and unqualified. No size guard was changed or silent retry made. Supporting
larger immutable assets requires an explicit source-boundary change and new
recorded controls, not dropping this file or selecting a replacement task.

Evidence run: `external-windows-remaining-reference-v1-20261018`, retaining the
worker source and prospective controller jobs, pinned private materials,
all ten raw results and the source-metadata diagnostic. Combined with the
previous first-task controls, five of six task environments now have positive
parent/reference evidence. Neutral public source/export, candidate assembly
and solver/public-test access still need qualification beyond the first task.
No new AtMem repair efficacy result or goal completion is claimed.

## Explicit asset profile correction and Requests-4356 v2

The new `windows-asset-boundary-v2.md` prospectively permits recognized ordinary
assets up to 4 MB, keeping the 1 MB code/text cap, 40 MB total, path/mode/Git
verification, no-follow/race checks and source-only mutation policy. The shared
capture, snapshot validator, public decoder and public export agree with the
standalone evaluator. Local fixtures verify exact multi-megabyte asset capture,
oversized and disguised-source refusal, unchanged aggregate bound and rejection
of asset changes. No asset is dropped from a snapshot or made executable source.
V1's two pre-test stops remain retained rather than relabeled successful.

V2 on the same immutable Requests-4356 image passes tracked-source verification
but **does not qualify the task**. The parent collects only one parsed error:
`ImportError` for `InvalidProxyURL`; it has zero observed target test failures,
so the 115 missing target statuses are not treated as legitimate failing tests.
The reference yields 111/115 target passes and four failures (the connect/total
connect-timeout checks), with no declared regression checks. Neither relaxing
network isolation nor deleting those tests is authorized by this control.
The worker script exit code is zero but the pinned grader reports partial,
not full, resolution; a zero controller exit is not a qualification pass.

Evidence: `external-windows-requests4356-asset-v2-20261018`, preserving the new
policy/source identity, both full outputs and actual grades. No model calls,
test replacement or outcome-driven task replacement. Five of the original six
tasks still have positive parent/reference evidence; Requests-4356 remains an
explicit environment attrition row, not a failed solver or silently omitted
denominator. Public-source/assembly/solver qualification on the other four new
tasks remains the next executable work; broader cohort execution is still open.
