# Fresh public retail pilot

Four fresh, no-fault conversations on exposed tau2-bench retail task0. Same
registered model snapshot, seed, prompts, tools, graph and original database.
This is an engineering pilot, not a held-out production success-rate estimate.

| Configuration | Normal end | Native task score | Native tool calls | New store changes | Model calls | Estimated USD |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Baseline | Yes | 1 | 6 | 1 | 14 | 0.053470 |
| +AtMem | Yes | 0 | 6 | 1 | 18 | 0.060450 |
| +AtFlows | Yes | 0 | 6 | 1 | 18 | 0.056462 |
| Both | Yes | 0 | 6 | 1 | 18 | 0.056226 |

Total:68new model calls, estimatedUSD0.226608. Including the preserved earlier
native pilot, the sharedUSD20 ledger records86calls and estimatedUSD0.283932,
with no unresolved charges or reservation breaches. Prices are usage-based
estimates, not independently verified invoices. This task has no NL assertions,
so its NL evaluator returns the native empty-assertion result without a paid
grader call; the differing scores come from exact native database grading.

All four conversations ended normally. Only baseline selected the replacement
items matching the task's expected final database. The other three selected a
different replacement keyboard. No configuration was rerun or discarded.
Identical first model requests produced differing user/agent wording before tool
dispatch. Temperature0 and a seed did not make this provider deterministic.
This pilot cannot establish that a product caused the score difference, nor
support a task-success or speed improvement claim. The separate recorded-response
qualification checks equal-input integration parity; interruption evidence is
reported separately rather than inferred from these no-fault results.

Provenance: upstreamMIT tau2-bench commit
`b7ea9074c1cba482b30687fecdb5c8425fd6f619`; see included LICENSE. Manifest pins
task, source, graph implementation, installed-file hashes, prompts, schemas,
decoding, package dependencies and budget registration. `source_integrity=true`
means the frozen code and installed artifact checks passed after execution.
`comparison_eligible=true` means all four planned arms completed with grading and
observation available; it is not statistical evidence of superiority.

Each arm directory retains compressed original requests/responses, native
trajectory, checkpoint-state observation, exact tool/effect journal, status,
accounting and checksums. Top-level SHA256SUMS covers all generated public
artifacts; this README and LICENSE are ancillary descriptions. Export checked
that the actual provider key and isolated-service secrets were absent. Product
vaults, credentials and checkpoint database files were not exported.

AtFlows received the actual shipped tool observers' events without errors.
Their unreported prices remain unknown. Model spend above comes from independent
experiment accounting; it was not inserted into AtFlows to fill a feature gap.

Reproduction uses `benchmarks.agent_continuity.retail_live_pilot --help` and the
registered `specs/benchmarking/002-agent-continuity/fresh-pilot-protocol.md`.
Dry-run is default. `--execute` uses the existing cumulative authorization ledger;
never reset it to create more spending allowance. Fixed arm order and one exposed
task limit interpretation. Fresh faulted and held-out comparisons remain separate
gates, not completed by this pilot.
