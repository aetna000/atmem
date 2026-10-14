# Independent Claude Review — 2026-10-13

Reviewer: Claude Sonnet 5, medium effort, read-only CLI review. The initial
review cost USD 0.532 and the resumed output brought the recorded session cost
to USD 0.938. The CLI exhausted its output budget; findings were recovered from
the immutable local session log. No review subprocess edited repository files.

## Blockers

1. Already-public fictional/isolated V1 Hugging Face artifacts need explicit
   deprecated/superseded card updates before replacement publication.
2. Checked Phase 8 tasks retained stale `(missing)`/`(contradicts)` annotations,
   making the checklist internally inconsistent with retained evidence.
3. Strict Choice/Noul/Score V2 contracts and true single-classifier routing are
   specified but not yet implemented; release-facing text must not describe
   those requirements as shipped behavior.

## High findings

1. Baseline adjudication preceding snapshot freeze is only task ordering; the
   freeze command needs a machine-enforced adjudication-receipt prerequisite.
2. Release and website documents drafted for prior artifact identities must be
   revalidated against final replacement revisions before commit/tagging.

## Medium findings

1. The valid-Laya-ruling invariant is repeated with scope drift; the V2 contract
   should be normative and specification requirements should reference it.
2. Scaled allocation needs a minimum achieved fraction per partition so a
   heavily reduced result cannot retain the same scale label.

## Additional owner-requested architecture correction

The publishable SQLite/vector baseline is a third independent Hugging Face
artifact, not an undocumented file inside the transition dataset repository.
Its license, privacy, integrity, clean-load and anonymous-redownload gates are
separate from dataset and model publication.
