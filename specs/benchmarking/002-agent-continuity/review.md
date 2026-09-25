# Read-only design review record

Date: 2026-09-25. Reviewer: Claude CLI 2.1.281, requested model
`claude-opus-5-5`. Author/reviser: Codex. Scope: planning only.

This is the historical planning review. Subsequent code review and current
implementation status are in [implementation-review.md](implementation-review.md).

Invocation: `claude -p --model claude-opus-5-5 --tools '' --setting-sources ''
--strict-mcp-config --mcp-config '{"mcpServers":{}}' --no-session-persistence`.
Documents supplied on stdin; no tool, repository-write or MCP access. No secrets,
private memory or runtime data supplied. Reviews below are summaries, not a
fabricated verbatim transcript. No benchmark was executed.

## Round 1

Verdict: not approved; eight blockers. Corrections:

| Concern | Resolution |
| --- | --- |
| Fault seeds do not identify comparable barriers | Ordinal write target, explicit barrier, divergent operation disclosure and unreachable-target disposition |
| Late held-out split risks selection bias | G0 seeded task-cluster partition and ID digests before pilot |
| Unclear arm ownership | Responsibility table, single AtMem writer and equal runtime capabilities |
| Unknown outcomes versus legal state | Audit legal existing transitions; unsupported mapping is a gap, no new enum |
| Blocking-only strategy can look safe | Completion/safety non-inferiority plus primary benefit; unnecessary-block metric |
| Many endpoints invite selective claims | Primary comparisons, separate Holm-corrected families and descriptive secondary metrics |
| User simulator omitted | Persist per-trial history across kill; pin configuration and separate costs |
| Metrics implemented after baseline report | T011 in G1 before T008; deterministic adapter equivalence checks |

Additional suggestions adopted: harness smoke thresholds, charge provenance,
AtFlows non-interference checks, frozen-current-artifact held-out reruns, evidence
labels, and acyclic cross-repository task dependency.

Deliberate refinements to advice: do not force identical simulator conversations
across divergent arms; do not invent an AtMem status mapping without API audit.
Claude accepted both in round 2.

## Round 2

Reviewer confirmed all original blockers resolved. One new blocker: unnecessary
blocks / all blocks has a treatment-dependent denominator and missing no-block
cells. Replaced primary denominator with fixed oracle-intended operation count;
retained per-block ratio only descriptively. Moved T011 physically into G1.

## Round 3

Verdict: **APPROVE**, explicitly for planning/harness, not production claims.
Reviewer found no new blockers. Adopted final non-blocking clarifications:
public-interface evidence rule governs both blocking numerators; primary blocking
counts only intended operations; unrequested bad effects remain counted and
explicit; denominator common to per-operation rates; zero-write cohort exclusions
and limited completion claims explicit; changed-arm amendments precede G5.

No fourth review was performed after these non-blocking wording clarifications.
Codex agrees the protocol is ready for harness work subject to G0 pinning and
the stated gates. This is design agreement, not empirical validation.

## Validation

Both repositories' Spec Kit prerequisite checks passed. All 16 AtMem requirement/
success IDs and all 9 AtFlows IDs have task references (13 and 8 tasks respectively).
Relative links checked; `git diff --check` passed. Runtime files, versions,
credentials and deployed services unchanged. At planning review time, branches
were local and uncommitted; no publish/merge was performed.
