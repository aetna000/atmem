# Read-only implementation review

Date: 2026-09-25. Scope: **offline foundation only**, not completion of G0–G5.
Claude CLI 2.1.281; requested model `claude-opus-5-5`. Every consultation used
`--tools '' --setting-sources '' --strict-mcp-config --mcp-config '{"mcpServers":{}}'
--no-session-persistence`. Code was supplied on stdin. Claude ran no commands,
opened no repository files and made no edits. Codex applied changes and ran tests.

## Review history

1. First code review found eight issues: unreachable recovery cases, absent
   lost-request cases, weak pin enforcement, biased timing, teardown risks,
   worker-claimed outcomes, unchecked receipt payloads and customer-alias leakage.
   Implemented additional barriers/fenced aborts, hash/version checks, isolated
   timing, robust teardown, durable-state/oracle scoring, payload validation and
   canonical customer clustering. Kept the strong baseline; did not weaken it to
   manufacture an AtMem advantage.
2. Second pass required preserving design-exposed clusters before zero-write
   exclusion and isolating AtFlows' shared module cache. Corrected both. Its
   concern that AtFlows had no pyproject was disproved by the actual repository
   and successful isolated wheel installation; no unnecessary version-reader
   rewrite was made. Applied additional event-lock, transport, file-handle and
   missing-value recommendations.
3. Reviewer approved bounded foundation but recommended stronger negative-control
   and outcome-matrix assertions plus editable-product source hashing. Added all.
4. Follow-up questioned a default fault argument. Supplied actual signature and
   distinguished explicit clean `None` from default `after_commit`. Reviewer
   accepted that distinction; both arms keep the same expected outcome matrix.
5. That follow-up found a real `None == None` bug: clean trials incorrectly
   matched ordinary events as fault barriers. Inspection of raw rows confirmed
   the bug. All pre-fix clean-control results are invalid. Added explicit non-null
   fault guard and six process-level clean controls, plus runtime assertions for
   no kill, no restart, exactly one non-resumed run and completion.
6. Final fix review: **APPROVE**, conditional on rerunning tests and regenerating
   smoke evidence from corrected source. No unresolved blocker was reported for
   this bounded scope. Full public-corpus or production approval was not requested
   or granted.

## Evidence handling

Development outputs, including interrupted/source-change-aborted runs, are not
qualification evidence. Final validation status and the canonical passing output
are recorded in `benchmarks/agent_continuity/reports/implementation-status.md`.
The 20-repeat final-source qualification, native tau adapter, four-arm public
pilot and held-out evaluation remain open. Product runtime sources, defaults and
versions are unchanged in both repositories; no release or deployment is included.
