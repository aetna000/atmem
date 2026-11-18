# Stable 2.3.15 release qualification

Source-freeze record; registry publication is not inferred from this file.
AtMem2.3.15 / OpenClaw2.3.15 (`latest`), unchanged AtBot0.1.1 / AtFlows0.1.8.
The unpublished b2 delivery target is superseded; frozen research artifacts are
unchanged. This release adds operationally tested guarded interfaces and honest
evaluation, not a demonstrated learning gain.

## Actual installed-user journeys

Final candidate wheel SHA256
`bc59f9e5b2c0305a95c7f6534ae88963c9a4e9a7f0f18453534f642fa0cd3a5c`
passed all six journey groups outside the checkout on all three platforms:

| Platform | Runtime | Result |
|---|---|---|
| Native macOS26.5.2 ARM64 |Python3.12.13|6/6; own services stopped|
| Native Windows11 Pro26200 x64 via owner SSH |Python3.12.6|6/6; own services stopped|
| Debian12 ARM64 Docker, unprivileged user |Python3.12.16|6/6; own services stopped|

Receipts are macos-user.json/windows-user.json/linux-user.json. Linux is a container,
not a bare-metal desktop claim. The image is pinned by digest in its receipt.
The journey uses installed console executables and covers version/dependencies,
fresh isolated Home onboarding, loopback dashboard and AtFlows HTTP, SQLCipher
remember/recall/integrity across processes, encrypted document CLI search/inspect,
wrong-workspace denial and the encrypted zero-model study contract. Test-owned
AtBot/AtFlows/dashboard processes were stopped. Existing owner Homes were not used.
SSH credentials are never retained in these artifacts. AtBot was unconfigured and
correctly selected deterministic fallback; no model/agent/learning test is implied.

The first candidate exposed two documentation-gate issues: the stable note lacked
the exact npm compatibility pin, and the feedback docs checker required literal
unreleased wording. The note now pins the exact npm package; the checker accepts
explicit incomplete production qualification for stable optional interfaces and
tests that removing that limitation fails. No quality or authority gate was waived.
Both corrected checks passed. Current README/install examples and PyPI classifier
are stable. The final wheel/sdist/twine/rebuild passed; its runtime payload matches
the preliminary artifact byte-for-byte. All three full journeys were repeated on
the final artifact and explicitly verified the stable classifier. Registry-installed
artifact verification remains a post-publication gate.

## Spec Kit reconciliation

Spec054 owns stable publication and operational acceptance. Spec052 retains its
four-arm failed experiment but delivers through the stable release contract.
Spec053 has one normative final protocol; failed preceding drafts are historical
in protocol-history.md. Original candidate/package versions and JSON registrations
are not rewritten. Spec050 remains a broader unfinished roadmap: T010/T016/T017/
T021/T022/T023/T024 are not marked complete by package publication. Full installed
Hermes enforcement, production-policy qualification, dependent acceptance matrices
and efficacy are excluded. The constitution is unchanged. No Spec051/pgvector dirty
work, model training or new DolphinBench run is included.

Coverage mapping: FR001/004→T001; FR002/003→T002; FR005→T003; FR006→T004;
FR007→T005; FR008→T006. All requirements have tasks. Current package/installer/
bridge metadata agree on2.3.15, the manifest has72pages, public guides use current
stable install pins, and historic benchmark/wheel identities remain explicit.

## Gates and publication

Focused run:36passed with two documentation failures described above. Their
correction rerun passed10/10. Earlier unchanged feature boundaries had28targeted
passes, with11comparison checks rerun after the final actor-boundary correction.
Native user receipts, wheel/sdist/twine and source-distribution wheel rebuild
completed. Local OpenClaw typecheck/build/test/smoke and21AtBot tests passed.
Final exact-commit hosted regression/bridge/upgrade/distribution gates,
public main merge, annotated tag and publisher/registry verification are required.

Private website source pin/version/claim refresh is a separate owner-review PR
after public main exists. No private merge or live deployment is performed by
this release lead. Final publication receipts belong to the GitHub release and
workflow; a source-freeze checklist is not a claim that publishing already occurred.

The first hosted Python3.10 full run found one missed documentation metadata
transition: capabilities.json still labeled the package prerelease. Its 4,344
other tests passed (203 skipped). The status is corrected to stable and optional
interfaces are labeled opt_in, retaining incomplete production qualification.
The documentation regression and applicable hosted gates must pass on the fix.
