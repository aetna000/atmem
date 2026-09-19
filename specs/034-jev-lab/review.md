# JEV-Lab review record

## Consistency check

The specification, plan, and tasks agree on the following boundaries:

- the experiment is synthetic and under `research/jev_lab/`;
- Jev nominates or scores candidates but AtMem remains the authority;
- live mode is opt-in, pinned to `jev-1.13.0`, and one batched request is used;
- offline mode is deterministic and visibly distinct from live mode;
- JSON evidence and an inline SVG/HTML report are both required;
- production retrieval, memory, dashboard, and persisted schemas are not changed.

All FR-001 through FR-010 are covered by T001–T008. The offline runner, live
smoke request, six focused tests, and retrieval regression tests passed on the
`jev-lab` branch.

## Review findings applied

1. A live API outage must not be labelled as a successful offline experiment;
   the runner now emits `mode=unavailable` and retains transport status.
2. The report must show more than ranking quality; it now includes agreement,
   transport latency, authority overrides, MRR, and top-1 bars.
3. API secrets must not appear in request artifacts, reports, or output; tests
   assert this explicitly.
4. Jev responses cannot bypass AtMem; the local authority gate removes expired,
   excluded, or out-of-scope candidates after every ranking.

## Claude consultation

The requested Claude read-only consultation was attempted twice. The existing
CLI session did not return, and a clean `--bare` invocation reported that the
CLI was not logged in. No files were edited by Claude. The safety and validity
checks above were therefore performed manually and recorded here rather than
claiming a successful external review.
