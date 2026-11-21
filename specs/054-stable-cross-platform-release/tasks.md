# Tasks — stable 2.3.15

- [x] [T001] Align current versions, release note and website manifest; reconcile Specs050/052/053 and public claims (FR001,004,005).
- [x] [T002] Add and execute installed-user journey on native Mac, native Windows SSH and pinned Linux container; record actual receipts and fix failures (FR002,003).
- [x] [T003] Run required Python/companion/OpenClaw/build/metadata/installed/upgrade/docs gates on final candidate (FR005).
- [x] [T004] Merge public reviewed main, annotate/push exact stable tag, wait publisher and verify GitHub/PyPI/npm plus published install (FR006).
- [x] [T005] Prepare private immutable source-pin/claim refresh with build/gates/docs/browser checks and owner-review PR (FR007).
- [x] [T006] Record source/versions/platform outcomes/workflows, explain release significance and report independent publication states (FR008; SC001–004).

Completion evidence: publication.json and publication.md. T005 is complete: the
private PR passed all validation after actual source remediation, the owner merged
it, and the explicitly authorized Hosting deployment used the checksum-verified
artifact from validated private main. Both live domains match that artifact;
search/navigation and stable version/source identity passed. No audit waiver,
private self-merge or feature-branch deployment occurred.
The optional owner-host Windows PyPI recheck and remote temporary-directory cleanup
are blocked by host unreachability; its prepublication journey and publisher
Windows artifact gate passed. No postpublication Windows owner-host pass is claimed.
