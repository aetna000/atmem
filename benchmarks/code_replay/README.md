# Click replay tools and isolated reduced pilot

The original read-only CLI implements metadata contracts and answer-blind
selection. Separate explicit reduced-pilot modules now provide historical
qualification, installed-product integration and authorized reporting. See
[Spec 043](../../specs/043-click-historical-replay/spec.md).

From the repository's development environment:

```sh
python -m benchmarks.code_replay.cli validate protocol /path/to/protocol.json
python -m benchmarks.code_replay.cli select /path/to/discovery.json
python -m benchmarks.code_replay.cli preflight /path/to/protocol.json
```

`validate` checks closed versioned schemas and returns a canonical digest. It
does not establish that referenced source/test/price/qualification artifacts are
genuine. `select` accepts `atmem-click-discovery-input-v1` metadata with
`anchor_commit` and validated `candidates`; retains every supplied exclusion;
selects the latest five eligible mainline changes, replayed chronologically;
and cannot widen the 100-entry horizon. Eligibility remains evaluator-declared
until task preparation/qualification verifies the evidence. Contract fixtures
remain plumbing, not Click evidence. The actual frozen historical package is
an external benchmark artifact, not a fixture.

The original `preflight` deliberately returns blocked for its broader normal-host
claim. Referencing a digest or adding a `ready` flag cannot enable dispatch.
There is no `run` command in that read-only CLI. These commands do not modify
agent trust, owner configuration or databases.

Inputs are metadata-only files bounded to 2 MB. Do not put raw conversations,
tool output or credentials in them. Operational evidence belongs in AtMem's
authorized encrypted service, not a plaintext result file. JSON output contains
metadata/digests and fixed blocker codes, not a transcript archive.

Exit codes: `0` metadata valid / selection complete; `1` invalid/unreadable input;
`2` insufficient eligible candidates or readiness blocked. `--help` lists commands.
Initial unit verification is local; installed-artifact and OS qualification remain
separate pending work, as does the full T017 onboarding/CI deliverable.

## Explicit reduced C/D integration

`freeze.py` recovers pre-solution reports, retains them protected, validates the
complete selection ledger and grades each parent once and reference twice with
the full frozen suite. The behavioral adaptation and literal `/tmp` exclusion
are recorded before target solving; they are not outcome-based test removal.
No target inference occurs during qualification.

`pilot.py` is a distinct, explicitly selected benchmark integration, not a way to
enable unqualified normal Codex hooks. It requires `--subscription-only`,
`--allow-harness-integration`, an exact `--freeze-sha256`, the installed wheel
matching every bundled product file, the existing authentic experience probe,
per-run sandbox read-denial checks and current rich structural preparation.
It uses installed CodeRuntime/CodeReceipts/CodeKnowledge/CodeExperience. No
replacement classifier, oracle lessons, model-selected database identities or
hidden grade feedback is introduced. An existing start marker prevents silently
repeating a partially executed pilot. Original v1 dispatch remains blocked.

Workspaces have one sanitized Git commit, no remote/future objects, offline
tools, private volatile CLI homes, fresh agent sessions and separate C/D lanes.
Each lane keeps its worktree path across authentic tree transitions; old source
workspaces are moved recoverably outside the next solver's read boundary.
The 20-run schedule is serial C/D then D/C across two repetitions. It is not
twenty independent historical tasks and not full carryover balancing.

The provider/model is the existing subscription's recorded `gpt-6-luna` alias;
there is no immutable model-weight pin or observed billing feed. No API key or
GPU is used. Wall, tool-event and output termination is instrumented; token use
is checked after a turn and cannot be presented as a hard provider-side cap.

Run evidence is encrypted through the existing EvidenceService. Submitted CLI
input is distinct from independently observed model input. The streams do not
include every system/model boundary, so complete black-box reconstruction is
not claimed. `report.py --include-memories` performs authorized stdout inspection;
the default persisted report contains only comparison metadata. Optional
`--archive-root` writes ML-KEM/AES-GCM/ML-DSA recipient-encrypted archives and
verifies exact event round trips. `--key-root` must remain off MEM. Do not lose
those private keys or copy them alongside the external archives.

MEM is used only for benchmark sources, frozen manifests and protected result
archives. Product development and installation stay on the internal disk.

## Fresh native/structure follow-up

`control.py` implements the separately requested ten-attempt A/C comparison in
[structure-control-v3.md](../../specs/043-click-historical-replay/structure-control-v3.md).
It reuses the frozen authentic task/grader definitions, never the previous
solver sessions. A receives no additional context and instantiates no memory
lane; C uses fresh installed-product structural preparation with experience off.
Normal source/search/Git/test tools remain available in both. Native Xcode or
Command Line Tools Git is copied and hash-pinned, without reading owner config.

The freeze operation takes `--source` (old task package) and `--frozen` (new,
exclusive output). Execution requires the new `--freeze-sha256`, all explicit
isolated paths and `--subscription-only`; frozen harness and binary hashes must
match. Do not use the source-tree interpreter: preimport AtMem from the qualified
installed wheel before adding this harness to `sys.path`. No retry/resume option
exists; interrupted attempts must remain visible rather than overwritten.

`control_report.py` requires exactly ten unique terminal results, distinguishes
functional passes from all-budget passes, and can recipient-encrypt all events
with `--archive-root` and internal-only `--key-root`. `--recover-only` reads those
archives and keys without opening the vault or any solver files. Reports never
pool these corrected-tool follow-up results with the earlier C/D runs. The
initial pre-inference Git-path rejection is retained as preflight attrition.

## Bounded structural efficiency loop

`efficiency.py` provides `freeze`, `run`, `inspect` and evidence-only `recover`
for three tuning candidates and one new-task confirmation cohort. See
[the loop protocol](../../specs/043-click-historical-replay/structure-improvement-loop.md)
and `RandD/2026-10-17-structural-efficiency-loop.md`. Each cohort freezes a new
installed wheel and harness/runtime/task hashes, starts ten matched sessions
and refuses an existing start marker. Every solve failure remains in results.
Both arms retain native tools and the same prompt/limits; C uses source-backed
product structural context, never experience or target patches.

Tuning requires five functional/policy passes and at least the native score,
then 50% total-input-token saving or the owner's 20% fallback. Missing usage
blocks a token win. Integer threshold arithmetic accepts exact 20%/50% bounds.
Cached input is included, not added twice; output/uncached usage and service
latency remain separate. These gates select candidates, not a population claim.

`confirmation.py` qualifies five separately selected earlier Click tasks without
model calls: frozen upstream default tests must fail on the parent and pass
twice on the accepted reference. Qualification failures are retained and excluded
before solving. The final candidate is frozen before its one confirmation run;
the result cannot become another tuning round. This is same-repository transfer,
not repository-disjoint or publication-level confirmation. Exact declared events
remain encrypted and export/recovery use the existing protected service.
