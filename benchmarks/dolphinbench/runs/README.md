# Private DolphinBench campaign — 2026-10-21

Status: the fallback ingestion condition was stopped at 101 completed exported
interactions after its memory path was found to differ from the historical V3
configuration. **No new final task-accuracy score is available.** Full paid
execution is now blocked pending qualification; see the
[configuration and readiness audit](../../../docs/benchmarks/dolphinbench-readiness-20261021.md).
The user's total spending ceiling is
US$250; no paid infrastructure is provisioned.

## Frozen inputs

- AtMem base: published 2.3.9, source `a50659256ac14caae0f60cbdb98e534d4e7df1d0`.
- Product patch: monotonic Hermes memory freeze; installed wheel SHA-256
  `bc9a2e0e678b1b99caf9ef7b5c8c60db64f820b3bed527a3a7198d525ac25c51`.
  This is a patched research artifact, not an unmodified PyPI release.
- Implementation commit: `949062e` on `bench-dolphinbench-239-20261020`.
- DolphinBench source: `81cb6f8405b40a9e76089cef650806a80af06ea2`.
- Installed Hermes source: `d0288be5b3330d2442e3907185b8e9d0958297bb`.
- Distributed release: 13,539 single-message interactions, three isolated
  personas, then all 600 tasks. Every source hash and the parsed release digest
  are checked. The construction validator's 11,147 sessions are a different
  unit, before single-message replay normalization.
- Agent: Azure-hosted `openai/gpt-5.6-luna`, medium reasoning, 4,096 output-token
  cap, 20 tool turns. Judge: Azure-hosted `openai/gpt-5.6-sol`, medium, 8,000
  output tokens. Transport is OpenRouter with Azure-only routing and no fallback.
- Normal AtMem memory capture/recall remains active. Hermes model title
  upgrades and automatic background skill review are disabled using supported
  configuration. Fresh native profiles do not share session-search histories;
  each persona's AtMem store is the persistent memory.

The private runner reuses upstream ordering, simulated apps, exact-message
validation and grading prompts/rubrics. It does not claim satisfaction of the
official direct-Azure-deployment transport gate. Maintainer acceptance and
leaderboard submission are separate, pending actions.

## Evidence and costs

Working directory: `/Volumes/AtMemDolphin/campaign-atmem-239-frozen` on MEM.
The per-call SQLite budget ledger durably reserves before sending, retains
uncertain calls, and settles using returned usage/cost. The frozen campaign cap
is US$249.90; US$0.10 is reserved for earlier preparation ledgers, whose current
actual-plus-uncertain exposure is US$0.051654. Those ledgers are not deleted or
reclassified as free calls.

Earlier attempts are preparation evidence, not accuracy results:

| Directory suffix | Outcome |
| --- | --- |
| `campaign-atmem-239` | Main pilot responses saved; background title request lacked completion evidence; conservative reservation retained |
| `campaign-atmem-239-qualified` | One paid ingestion completed for US$0.003617; controller-only export repair preserved prior identities and resumed without another model call |
| `campaign-atmem-239-full` | Three interactions exported; a longer fourth exposed native background skill review; all 15 API calls and US$0.017835 cost saved |
| `campaign-atmem-239-frozen` | Fallback preparation stopped after 101 exported interactions; US$0.415165 in completed API calls, no scored tasks; not the historical V3 memory condition |

All preparation batches and gate reports have been committed to the private
[AtMem evidence repository](https://huggingface.co/datasets/atmem/dolphinbench-evidence-20261020)
and independently downloaded at exact revisions to verify size and SHA-256.
The running campaign checkpoints every 25 ingestion interactions and at phase
boundaries. Raw requests, responses, usage, native witnesses, controller
identities, SQLite accounting backups and neutral product memory exports are
allowlisted; credentials and live encrypted database files are excluded.
Neutral exports are not a claim of bit-exact encrypted-database restoration.
Only disposable generated profiles are removed after verified cloud backup;
canonical AtMem databases, credentials and benchmark evidence remain on MEM.

## Gates completed

- 55 installed product/controller/transport tests passed.
- 35 upstream offline MCP/submission tests passed after reinstalling the
  benchmark-only `pydantic-core==2.50.1` dependency whose signature failed.
- No-cost native process fixture verified capture, drain, product freeze,
  fresh-process recall, unchanged frozen canonical state, actual simulated-app
  calls and exact request/auxiliary separation.
- Real Azure-hosted Sol diagnostic passed; reported cost US$0.000396.

The first few interactions cannot establish final cost, completion time,
accuracy or superiority over another system. There is no matched native or
Mem0 arm in this approved initial campaign. Historical 30-task comparisons
remain separate and are not reused as the new result.
