# 2.3.3b1 documentation and Spec Kit consistency audit

**Status:** in progress; this is not release acceptance.

On 2026-09-17, a read-only local-link scan of all 211 tracked Markdown files
found zero missing local path targets. The ignored local `idea.md` archive was
outside that tracked scan and was left untouched. The scan does not validate
external URLs or fragment anchors. A repository-wide version/status scan found the active README,
`docs/current-status.md`, `docs/release-roadmap.md` and
`docs/benchmarks.md` consistently identify 2.3.2 as published/stable and
2.3.3b1 as proposed, not released. Dated 2.2.x/2.3.0 evidence and release
notes retain their historical package versions rather than being rewritten.

The 2.0.19 LongMemEval result is a historical benchmark; the separate 2.0.20
pre-change observation is not a 2.3.3 result. The benchmark guide now says a
new run of current source cannot reproduce the older result exactly.

Spec 031 explicitly preserves 003 delegated-provider authority, 007 governed
task context, 008 retrieval safety, 019 framework adapter contracts, and 028–030
encrypted evidence/portable-home behavior. Its 2×/10× targets are conditional
on matched quality and timing evidence; no benchmark claim is yet cleared.

Still required before candidate acceptance: re-run the Spec Kit cross-artifact
analysis after code/tasks settle; check external links and fragment anchors;
reconcile every version/installer constant after a candidate version is chosen;
run UI/accessibility and all host-adapter/package gates; record final Mem0 base
and hybrid profiles plus held-out/native results. The current audit therefore
does **not** certify all specifications or Markdown as release-consistent.
