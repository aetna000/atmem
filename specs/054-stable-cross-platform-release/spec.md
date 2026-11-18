# Spec 054 — Stable AtMem 2.3.15 release

Status: authorized 2026-11-18. This stable publication decision supersedes the
unpublished 2.3.15b2 release target in Specs052/053. Frozen experiment manifests,
source identities, installed versions and results remain historical evidence.

## User outcome and scope
An ordinary user can install the same stable artifact on Windows, macOS and Linux,
initialize an isolated local Home, open the local services, persist and recall a
memory, and exercise the governed document and experimental study boundaries.
The release explains the useful operational changes without claiming the agent
learned: Spec052's revision failed; Spec053's final small SDK check scored6/6 for
all conditions and established no accuracy gain. Stable package status does not
qualify an experimental policy or an untested host integration.

## Requirements
- FR-001: AtMem2.3.15 and OpenClaw2.3.15 are the single current stable versions in
  package metadata, installers, server identity, tests and active guides. Retain
  exact AtBot0.1.1/AtFlows0.1.8 pins. Historical study/release identities are not rewritten.
- FR-002: Test the built installed wheel outside the source checkout on native
  macOS ARM64, the owner's native Windows SSH machine and Linux in the existing
  Docker engine. Record exact OS/architecture/Python, artifact digest, commands,
  observed outcomes and limitations. Do not infer a platform pass from unit tests.
- FR-003: Each user journey covers fresh venv install/dependency health, CLI version,
  isolated Home initialization, dashboard/AtFlows readiness and loopback HTTP,
  cross-process remember/recall/integrity, encrypted document search/inspection and
  wrong-scope denial, and a zero-model study contract. Stop only task-owned services.
  Never alter the owner's existing Home, accounts, hosts or credentials. Never
  persist the provided SSH password in source, logs or release evidence.
- FR-004: Reconcile active Specs050/052/053 with this release. Preserve incomplete
  production-policy qualification and installed-host conformance tasks as exclusions,
  not fabricated completion. Move superseded test protocols out of normative Spec053.
  Keep the constitution unchanged. Every stable claim maps to shipped code/evidence.
- FR-005: Before tagging run applicable Python, companion, bridge, metadata, build,
  sdist rebuild, installed-artifact, persisted-upgrade and public-documentation gates.
  Add docs/releases/v2.3.15.md with installation, opt-in/migration/compatibility and
  honest limitations. Update the public website manifest and affected public guides.
- FR-006: Review and merge the complete public change to main, commit/push before
  an annotated v2.3.15 tag on the exact reviewed commit. Wait for publisher success;
  verify non-prerelease GitHub release, PyPI wheel/sdist, npm stable version/latest
  and a fresh registry installation. No companion tag when its code/version is unchanged.
- FR-007: After public main exists, pin its immutable SHA in the private website,
  refresh stable metadata/content lock/claims and run build/gates/docs/browser checks.
  Push an owner-review PR through the private repository's existing author/SSH remote.
  Honor the hosted dependency audit; report an unpatched upstream blocker without
  weakening it. Owner-only merge and validated-main deployment remain separate; do not self-merge,
  deploy a feature branch or call pending documentation live.
- FR-008: No further paid memory-quality experiment, model training, new DolphinBench
  run, arbitrary policy activation or publication of the dirty Spec051/pgvector work.
  Platform journeys are operational tests, not learning or production-quality evidence.

## Acceptance
- SC-001: Three real installed-user receipts cover FR002–003 or expose an exact
  actionable blocker. No unknown/failed step is described as a pass.
- SC-002: Current spec/plan/task/release documents contain no contradictory active
  version, scope, completion or learning claims; historical artifacts stay immutable.
- SC-003: Stable release and matching registry artifacts are published, installed
  and verified after all applicable gates pass on the reviewed source.
- SC-004: The website refresh is a tested pushed PR; final report separates package
  publication, owner merge and live deployment and explains why this release matters.

Publication status: stable package verified; website readiness remains blocked.
See publication.md/publication.json for post-tag evidence and exact limits.
