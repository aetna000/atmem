# Tasks — stable 2.3.15

- [x] [T001] Align current versions, release note and website manifest; reconcile Specs050/052/053 and public claims (FR001,004,005).
- [x] [T002] Add and execute installed-user journey on native Mac, native Windows SSH and pinned Linux container; record actual receipts and fix failures (FR002,003).
- [x] [T003] Run required Python/companion/OpenClaw/build/metadata/installed/upgrade/docs gates on final candidate (FR005).
- [x] [T004] Merge public reviewed main, annotate/push exact stable tag, wait publisher and verify GitHub/PyPI/npm plus published install (FR006).
- [ ] [T005] Prepare private immutable source-pin/claim refresh with build/gates/docs/browser checks and owner-review PR (FR007).
- [x] [T006] Record source/versions/platform outcomes/workflows, explain release significance and report independent publication states (FR008; SC001–004).

Completion evidence: publication.json and publication.md. T005 has a pushed,
functionally tested private PR, but its hosted npm audit is blocked by unpatched
Picomatch GHSA-fc5q-39xc-vjpf. No audit waiver, private merge or deployment occurred.
The optional owner-host Windows PyPI recheck and remote temporary-directory cleanup
are blocked by host unreachability; its prepublication journey and publisher
Windows artifact gate passed. No postpublication Windows owner-host pass is claimed.
