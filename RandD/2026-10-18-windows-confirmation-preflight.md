# Windows confirmation preflight

Status: metadata selection complete; image/runtime qualification in progress;
zero confirmation solver attempts. T062/T077/T079 and the overall goal remain
open. This does not replace or enlarge the completed validation result.

The prospective candidate and analysis lock is
`specs/042-atmem-code/windows-confirmation-v1.md`. It keeps the validation
tools-arm artifact, model, context/guidance and caps unchanged. The selected
20 issues are repository-disjoint from validation; no hidden grades informed
selection. The original validation's partial-correctness harm remains explicit.

## Frozen selection

Four identities per repository: pydicom, SQLFluff, pvlib, pytest and Sphinx.
Catalog revision/tree match the existing plan. Fixed confirmation seed and
identity-only sorting preserve all candidate orderings before metadata fetch.
All 20 metadata/blob checks pass. Selection SHA-256:
`8d1c769642903a84419231543ec1bff37d3b5dc1727d6760117a7cb252711d9f`.
Public metadata is retained on MEM under
`AtMem-Code-Replay-20261017/cross-repository-confirmation-preflight-v1`.

Base/parser/source-policy bindings are separate from the original six-task
validation manifest. Public test layouts are operator-bound and still need
actual source/import/runtime qualification. No model can select a parser,
source root or private test set. Strict parent/reference controls require
every declared parent target observed failing, every reference target passing,
all declared regressions passing and no skips; missing statuses cannot qualify.

## Image observations and unresolved work

All 20 declared registry names were checked. Sixteen descriptors resolve and
are digest/size/platform verified against retained raw manifests. Four tags
return denied/unauthorized and do not resolve under the additional standard
image names checked either:

- `sqlfluff__sqlfluff-4084`
- `sqlfluff__sqlfluff-3436`
- `sqlfluff__sqlfluff-4041`
- `pytest-dev__pytest-5227`

No task is replaced, no owner credential is requested/changed and no result is
imputed. Original failures remain in the protected evidence. Pinned upstream
Dockerfiles remain available as a possible same-task build route; no build is
claimed here. Networked environment construction, if undertaken, is separate
from the network-disabled solver and private grading workers. It needs retained
recipe/tool/base-image identities, bounded resources and full source/reference
controls; merely producing an image does not qualify a task.

The Windows Docker installation has the legacy builder and no installed buildx
plugin. Apt reports `docker-buildx` candidate `0.30.1-0ubuntu1~24.04.1`.
The inspected [official Docker container-driver documentation](https://docs.docker.com/build/builders/drivers/docker-container/)
describes dedicated BuildKit builders and memory/CPU limits. This is feasibility
research, not a claim that the package or builder has been installed or started.

The first seven available images have completed isolated native-amd64 shell/
Python runtime execution successfully. The original controller incorrectly
labels them false because it expects Docker image `Id` to equal only the
configuration digest. Actual Docker 29 output supplies the registry manifest
digest, already verified separately. The corrected interpreter validates the
raw transport equals the stored result and accepts only either exact verified
manifest or config identity, together with exact platform/interpreter output.
Tests reject unknown IDs and altered raw/parsed metadata. Original false flags
are preserved; an explicit interpretation-correction event must be recorded
before parent/reference qualification. No image/control/solver retry is used
to repair the analysis error, and no product/model bytes change.

Image/runtime evidence is isolated in a new protected AtMem vault under the
internal benchmark root `confirmation-v1`, vault identity `confirmation-v1`.
Run: `external-windows-confirmation-images-v1-20261018`; additional read-only
name checks use `external-windows-confirmation-alternate-images-v1-20261018`.
Keys remain internal. This avoids accumulating unrelated historical cohorts
in the same evidence vault while preserving the same encrypted/full/audited
AtMem boundary; it is not reduced capture.

## Verification and next steps

67 focused local fixture checks pass after the source-layout and image-ID
interpretation corrections. An earlier broader 135-check source/solver suite
passes; remote CI is not claimed. CI now explicitly includes accounting,
evidence-recovery and confirmation fixtures.

The earlier validation's public-test vault recovery has completed all 30 cases,
including exact outputs and available Code audit chains. The completion event
is retained in the original V2 cohort vault. Independent export/recovery still
needs its own verification; successful Windows-to-Mac recovery alone is not an
independent archive test.

Next: finish the live image checks, resolve or explicitly retain the four
same-task environment gaps, record corrected runtime interpretation, run pinned
parent/reference/source/public-proposal controls, freeze actual paired order
and execute only qualified, bounded native/candidate attempts. Preserve the
original 80-slot design and its failures; do not silently substitute a smaller
successful pool or claim confirmation complete from setup checks.

Subsequent checkpoint: image checks are terminal. All 16 accessible images have
successful native runtime output and verified image identity under the recorded
interpretation correction. Original false config-ID-only flags remain retained.
The parent/reference driver has started for those 16 original tasks, with zero
solver calls; the four inaccessible tasks remain explicit gaps. 102 related
local checks pass. The full V2 validation evidence snapshot has 587 events,
819,903,624 canonical JSON bytes and 292,538,962 zlib bytes at inspection, too
large for a single existing 48 MB encrypted-export payload. Export must segment
and authenticate the full snapshot, not truncate it or raise the event limit.

Further checkpoint: all 32 parent/reference controls on the 16 accessible images
are terminal. Only the three pytest tasks qualify. No confirmation solver has
run. A separate read-only, network-disabled source diagnostic explains the
remaining classes without executing repository code or repeating tests:

- Pydicom includes a 2,725,654-byte generated Python dictionary and, in older
  snapshots, DICOM fixtures over the current file bounds. This is not solved by
  treating source code as an image asset or silently trimming data.
- pvlib snapshots contain 66–71 MB of tracked files, including large weather,
  CSV/HDF5 and notebook data. Their individual Git blobs match; existing file
  and aggregate snapshot limits reject them.
- SQLFluff-1763 contains a tracked test-fixture symlink, unsupported by the
  current regular-file-only source boundary.
- Sphinx images contain changed `tox.ini` and, for older cases, `setup.py`.
  The pinned Dockerfile recipes explicitly perform these environment-compatibility
  edits. The source guard correctly detects mismatch with the declared Git base.
  Do not falsely label those working-tree bytes pristine or remove the check.

These require explicit source/runtime projection or normalization design and
qualification, not new task selection or a blanket guard increase. The diagnostic
run is `external-windows-confirmation-source-diagnostic-v1-20261018`; inspect its
terminal state separately from the already terminal reference controls.

The full Windows validation archive is now independently recovered from MEM:
26 protected segments, exact original snapshot digest, 587 events and 180
receipt-verified streams. See the validation cohort report for the path, digest,
key-custody and assurance boundaries. No source was moved or deleted.

## Terminal diagnostic and next candidate

The read-only diagnostic records 15/16 results, then its remaining SSH transport
times out at 205 seconds. No tests or models are retried. Process inspection
finds the exact remaining loader blocked in `anon_pipe_read` on stdin, without
children or a benchmark container. Its pidfd-bound cleanup terminates only that
verified loader and deletes no files. The terminal failure and incomplete
diagnostic capture are recorded, not relabelled as a completed 16-case result.
The missing diagnostic is pytest-9780, whose independent parent/reference
controls had already passed; no missing diagnostic result is invented.

A separate length-framed operator transport is implemented without changing
the old frozen `command()` or completed cohorts. Its Windows control completes
with stdin deliberately still open (exit 0, exact response, about 0.191 seconds),
with zero containers/tests/models. This directly tests the EOF dependency;
it does not backfill any historical missing usage. Evidence run:
`external-windows-confirmation-framed-transport-v1-20261018`.

T080 starts a separately identified robustness candidate, reusing the existing
CodeGraph concept of explicit per-file-budget omissions in the rich projection.
It never reads oversized content, raises neither the per-file nor aggregate
cap, preserves symlink/race refusal and reports omission counts. Cache reuse,
currentness and atomic publication check changed file-budget omission counts;
ordinary ignored hidden files retain their established behavior. Tests caught
and corrected both cache/coverage and hidden-file interactions. 180 related
checks pass before the final additive metadata check. This is not an installed
artifact or performance result. The frozen preview and its outcomes remain
unchanged. A new product build requires independent installed qualification and
a new unexposed pool; the exposed preflight cannot silently become untouched
confirmation for the changed candidate. T062/T077/T079/T080 remain open.
