# AtMem Code implementation and qualification

Date: 2026-10-15 (Australia/Sydney). Branch: `feature/atmem-code-2.3.9`.

The unblocked implementation work through phase 8 is built. The complete
five-host product is **not fully qualified**. Unchecked tasks below remain
open; configuration scaffolding and expected failures are not counted as
successful integrations. Phase 9 was not undertaken and no release is published.

## Phase status

| Phase | Completed work | Remaining gate |
| --- | --- | --- |
| 0 | Contracts, scope decisions, host inventory, benchmark protocol and roadmap | Outcome evaluation remains outside this request |
| 1 | Pre-write message/interpreted-fact/metadata secret boundary and persistence regression tests | Pattern detection is not universal secret recognition |
| 2 | Typed contracts, authenticated intake, idempotent queues, shared/private lanes, additive migrations and conservative formation | No general-purpose multilingual semantic extractor is claimed |
| 3 | Flavour onboarding, preview, reversible host configuration, pause/resume/restore, upgrade/concurrent-disable checks; Claude automatic prompt path | T015/T017/T018/T019: B01–B04 |
| 4 | Recall-before-capture, optional review, replay handling, bounded context, distinct delivery receipts, controlled real Codex→Claude handoff plus private-lane tests | T024: B04 normal two-host onboarding; T042: B05 full-fidelity evidence |
| 5 | Shared CLI/dashboard application, authenticated HTTP/CSRF/role checks, search/filter/source/correction/forget and exact clear preview | Remote-provider data is not claimed deleted by local clear |
| 6 | Native/tagged signed RAG/Mem0-provider routing, scoped egress, response validation, replay protection, fallback and UI/CLI settings | No live third-party provider's task-quality result is claimed |
| 7 | Optional encrypted Python syntax graph, file-level fallback, ignore/secret filters, source digests, edit/branch invalidation and bounded automatic nomination | T033: B06 task-level comparative evaluation |
| 8 | Signed PQ-encrypted project bundles, pinned signer, scope/FK/schema/secret validation, explicit clone rebind, derived-index rebuild and installed product journeys on three OSes | Automatic host qualification remains per host/OS, not inherited from portable-core tests |

## Blocker ledger

| ID / tasks | Evidence and blocker | Safe current behavior / closure |
| --- | --- | --- |
| B01 / T015 | Muse 1.4.7: an earlier echo hook ran but `PreLLMCall` omitted its canary; subsequent echo startup timed out. The isolated Meta-protocol probe timed out with zero model requests after 30 seconds. | Adapter/configuration code exists, but automatic activation is refused. Requires a functioning, independently observable installed Muse model-input boundary. `tests/test_code_muse.py` preserves these probes as explicit expected failures. |
| B02 / T017 | Grok 1.0.13 documents that an allowing prompt hook's `additionalContext` is discarded. The desired per-turn context boundary is not established. | Capture/configuration scaffolding exists; no automatic activation. Requires a supported alternate delivery integration and real capture/delivery test, not an invented hook output. |
| B03 / T018 | Copilot CLI is absent here; its documented prompt hook drops output, and stable turn identity has not been established. SessionStart context alone is not per-turn recall. | Version-1 camelCase configuration and startup normalization exist, but activation is refused. Requires an installed supported host and verified event identity/delivery. Editor/cloud are separate unqualified surfaces. |
| B04 / T019, T024 | Codex 0.162.1 real project hooks, canary delivery and capture→Claude handoff pass only with a vetted fixture's per-invocation trust flag and isolated trusted project config. The product has no completed persistent user hook-trust onboarding, so normal two-host automatic handoff is not qualified. | Normal activation remains refused; production never adds the trust-bypass flag or changes the owner's trust store. Close with a host-supported, user-reviewed persistent-trust flow and a no-bypass activation/handoff test. |
| B05 / T042 | Code lifecycle hooks do not expose complete model/tool/media execution evidence. A successful prompt probe cannot establish full flight reconstruction. | Setup/status and exposure rows explicitly say `capture_coverage=partial`, `reconstruction_status=not_reconstructable`. The existing evidence service is separate and is not silently claimed by Code. Requires actual host instrumentation for the missing boundaries. |
| B06 / T033 | The graph comparison requires complete matched agent tasks and strong repository-map controls, overlapping the expressly excluded phase 9 evaluation. | No coding-quality or token-saving percentage is claimed. The protocol remains specified; execution is deferred rather than replaced by a misleading query-byte microbenchmark. |

No blocker prevented finishing the independent CLI, dashboard, provider,
graph, portability and cross-platform work.

An additional existing repository-wide CI gate is blocked outside this feature:
`openclaw@latest` resolves to `2026.10.3`, for which the hook-context matrix has
no reviewed fixture. Its guard correctly fails; it was not bypassed or replaced
with a fabricated fixture. This prevents calling the whole repository/release
pipeline green, even when the dedicated Code matrix passes. OpenClaw's pinned
minimum and lockfile cells, bridge build/tests and provider-extra jobs are
reported separately in the CI record. Reviewing a new upstream bridge version
is not claimed complete by these Code phases.

## Architecture and implementation boundaries

- One existing AtMem package, encrypted SQLite authority and application
  boundary; the Code extra adds SQLCipher and PQ bundle crypto, not model
  downloads or a second memory authority.
- Concurrent database initialization is serialized with the existing portable
  process/thread lock. SQLite `executescript` commits its current transaction;
  an outer BEGIN alone did not serialize the multi-script schema upgrade. A
  16-initializer regression and concurrent audit-writer test cover this shared
  coding-host startup boundary.
  The derived vector index also serializes WAL selection and schema startup;
  a separate 16-initializer vector regression covers the macOS race exposed by
  the installed-package CI, rather than disabling default vector behavior.
- Project identity is explicitly bound. Shared profiles cross agent IDs;
  private profiles include the agent ID. Clone rebinding is explicit. Turning
  a previously unversioned directory into a Git repository changes its binding
  key; explicitly attach it again and re-enroll its host rather than silently
  granting a new repository access.
- Host credentials bind owner, project, profile, agent, host and repository.
  Signatures are checked before recall, receipts or external egress, even when
  capture is off. Secret-bearing turns are refused before ordinary persistence.
- Disable only pauses automatic capture and injection. It preserves memory,
  hooks and restore material. Uninstall restores prior configuration and
  revokes the enrollment. Failed activation restores the previous bytes.
- Deterministic formation retains explicit source-bound user assertions;
  tool/task output alone is not proof of a durable fact or successful fix.
  English rule patterns cover preferences, project facts, decisions,
  workflows and user-reported fixes. Unsupported text is not invented into
  a memory. Record-origin documents preserve agent/type attribution through
  correction, filtering and export.
- Automatic native recall conservatively withholds source-dependent
  assertions for dirty repositories, missing Git revisions or a changed
  captured revision. Preferences survive source edits. Historical assertions
  remain searchable. This is whole-repository freshness, not semantic
  dependency analysis; an unrelated edit/commit can withhold a still-true fact.
- Local context timeouts discard late results; the host command also has its
  own timeout. No hard one-second process-cancellation guarantee is made.
- Delivery receipts retain exact context bytes and distinguish preparation,
  submission, verified acknowledgement and independently observed model input.
  A successful hook process alone does not prove delivery.
- Provider routes reuse the signed delegated-context boundary, not raw
  untrusted HTTP text. Tests use a real signed provider runtime with controlled
  transport. The existing local-RAG/Mem0 adapter and authenticated loopback
  transport are tested elsewhere in the full repository suite. No user's live
  external memory service was enrolled or contacted for these tests.
- Graph edges are syntax-level definitions/imports/calls, not resolved dynamic
  execution. Other eligible languages receive file-level entries. Source
  changes are rechecked before context submission.
- Bundles use the existing ML-KEM-768/AES-256-GCM/ML-DSA-65 envelope. Import
  verifies pinned signer, schema, exact lane references, state digest and
  screening, preserves lifecycle/source history, and rebuilds local indexes.
  Host configuration, enrollment secrets and provider routes do not travel.
  Canonical import success is distinguished from an optional source-graph
  rebuild requirement in a non-Git destination.

## Verification

The final machine-readable gate record is [verification.json](verification.json).
The final local repository gate passed **2,305 tests** with 89 explicit skips.
The identical installed wheel passed **66 tests on each of macOS, Windows and
Linux**, with seven separately handled host/browser cases skipped per core run.
Five installed host/browser journeys passed separately. The Code CI matrix
passed all six OS/Python combinations; repository unit jobs passed Python
3.10–3.13. The broader CI is still blocked by the existing unreviewed OpenClaw
latest-version fixture, not described as green.

It names the exact wheel hash, platform/Python versions, counts, skips and
host assurance. Tests run from copies outside the checkout and assert that
AtMem imports from the selected installed wheel environment. The wheel retains
the branch's 2.3.8 metadata for development only; it is not a new PyPI artifact.

The interactive Chrome journey verifies authenticated search, setting changes,
CLI parity and previewed clear without JavaScript errors. Interactive browser
testing was macOS-only; authenticated HTTP and CLI journeys ran on all three
platforms. Real host probes use isolated local model-protocol endpoints, not
paid inference or claims that an LLM solved a coding task.

`main` and `origin/main` remain at the peeled `v2.3.8` commit
`267c5b3ac08e8cac26dfee13c6eac2842d4bb876`. The separate Laya worktree and
research artifacts are untouched. No version/tag/registry or website
publication is part of this development request.

## Re-run

```sh
python -m pip install '.[code]'
ATMEM_CODE_SKIP_HOST_PROBES=1 python -m pytest -q
python -m build --wheel
python scripts/verify_code_wheel.py --wheel dist/atmem-2.3.8-py3-none-any.whl --report code-wheel-report.json
python -m pytest -q tests/test_code_claude.py tests/test_code_codex.py
python -m pytest -q tests/test_code_muse.py -rx
```

The [dedicated CI workflow](../../.github/workflows/atmem-code.yml) runs
installed-wheel core gates for Python 3.10 and 3.13 on Ubuntu, macOS and Windows;
its results must be reported separately from the local Python 3.12 runs.
See the [user guide](../../docs/atmem-code.md) for installation and operation.
