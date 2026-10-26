# Status against the published DolphinBench feedback

Updated 2026-10-26. **Implemented does not mean recovered in a live benchmark.**
Original record: 390/200. New fixed pilot: 0/20. New full suite: not launched.

| Concern | Implemented response | Verified extent / remaining gap |
| --- | --- | --- |
| Apple Notes skill/memo/osascript detour | Isolated MCP-only profile removes operational skills, terminal and unrelated local-app tools. Actual provider-bound tool arrays and skill prologues are checked. | Actual native capture and negative boundary tests passed. Recovery of the 35 affected failures has not been measured. |
| Real GitHub CLI/auth detour | Same profile excludes CLI route and exposes upstream simulated tools directly. | Native capture and schema/allowlist checks passed; recovery of the six affected failures remains unmeasured. |
| Deferred tool search failed to discover create_doc | Disable deferred tool search; make available simulated MCP schemas visible in the native request. | Actual captured request contains create_doc and authorized memory discovery. Actual model selection/completion still requires pilot evidence. |
| Draft written but action not completed | Retain actual app results, raw persisted state and independent backend logs; original grading remains authoritative. | Real synthetic create_doc/send_email/send_slack_dm round trips agree. This does not certify that benchmark content is factually correct. |
| Lost backend logs / unsafe replay | Durable intent, snapshots, existing-workspace protection and uncertain-action refusal. | Synthetic crash after mutation and replay/reset refusal passed. Full live recovery is not demonstrated. |
| 83 untraced-zero versus 84 traced-zero versus 43 partial failures | Reproduced all 200 ledger; separate cohort labels and fixed pilot sampling both traced cohorts plus passed controls. | Cohort accounting is complete. Root-cause transcript analysis and remedies for all 127 traced failures are not complete. |
| Retrieval ranking, packing, temporal interpretation and content correctness | Hold memory/retrieval fixed for the first execution-only experiment. | No new fix is claimed for these failure classes. They remain investigation work after execution qualification. |
| Higher task latency | Record durations in new evidence; compare after real pilot. | No measured latency improvement yet. |
| Repeatability and unsupported score claims | Freeze per-role routes/models/options/artifacts; launch admission, cost uncertainty checks, full denominator and no-regression pilot promotion. | 64 focused tests passed. 75.4% remains a conditional diagnostic, not a corrected 600 score. |

## Current operational gap

The AtSys worker could not write to the bound private runtime/evidence directories,
Hermes installation lock or MEM output root under its workspace-only sandbox.
Its reported mounted MEM/hash checks passed; the pilot never launched. This is a
configuration gap in the prepared AtSys execution context. Scope-correct access
must be provisioned before retry; do not disable the benchmark agent's isolation,
change frozen model/memory settings or grant real-app access as a workaround.

Hermes subscription bridge authentication was subsequently verified. MEM has been
recovered and filesystem/access/hash checks passed. Neither operational recovery
establishes that the original benchmark failures have been corrected.

## Promotion evidence still needed

1. Reconcile the blocked AtSys attempt and give the execution context required
   scoped access through a supported runner mechanism.
2. Generate fresh actual profile/app/crash receipts for the unchanged condition.
3. Run exactly the fixed 20 IDs once. Retain original grading, all failures,
   actual calls/state/logs, uncertainty, costs and cohort labels.
4. Report recovered failures and regressed controls. A trace alone is not a pass.
5. Only after the pilot passes qualification, seek the separate full 600 launch
   decision. The full score remains 390/200 until a complete new run establishes one.

Sources: Git-tracked audit/ledger, execution_profile.py, qualify_profile.py,
qualify_execution.py, safe_runner.py, pilot_readiness.py, readiness.py and the
AtSys pilot-needs-attention.json. The published article and feedback:
https://huggingface.co/blog/javadtaghia/atmem-2310-bounded-evidence-discovery-for-persiste
