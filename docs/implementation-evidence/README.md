# Implementation evidence journal

This is the append-only destination for feature verification results. The dated
`specs/implementation-review-2026-09-09.md` is a frozen historical review, not a
current backlog or a destination for new results.

Each feature writes independent entries under `docs/implementation-evidence/NNN/`.
Name each entry with UTC timestamp and source commit, adding a unique suffix
when necessary: `YYYYMMDDTHHMMSSZ-<commit>-<run-id>.md`. Create entries only for
work actually performed; a planned task is not a passing evidence entry.

Every entry records:

- Feature/task/requirement IDs and the claimed boundary.
- Source commit, branch, dirty-tree state and relevant patch/artifact digests.
- Exact package, host, deployment and test-suite versions/configuration.
- Commands, UTC start/end time, result, skips and unmet prerequisites.
- Evidence/artifact references and digests, measurements and limitations.
- Whether results are simulated, installed-host, independently verified or
  human-protocol measurements; do not combine those evidence classes.
- Related previous entries and any correction or supersession reason.

Never overwrite an existing entry. Corrections and new runs create new entries
that reference prior evidence. Apply access control and redaction to artifacts;
do not commit credentials or customer content. Append-only here is a repository
workflow rule, not a claim of tamper-proof storage.

`docs/current-status.md` is a maintained summary linking to these entries. Update
it when the user-visible implementation status changes; routine feature runs
need only their own journal entry. This keeps independent work from contending
on one central report. Historical review numbers and statements remain facts
about their original snapshot, not rolling counts of today's specs or tasks.
