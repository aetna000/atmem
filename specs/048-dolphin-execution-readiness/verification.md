# Verification — 2026-10-26

**Full-run decision: NO GO. Live pilot: 0/60, blocked before reader/judge calls.**
Original published result remains **390/600 (65.0%)**. No new accuracy claim.

## Frozen roles: verified against completed 600-run evidence

| Component | Execution | Model/settings |
| --- | --- | --- |
| Agent host | Local native Hermes, isolated benchmark profile | Simulated MCP apps; read-only memory discovery |
| Reader inference | Existing ChatGPT subscription, remote | GPT-5.6 Luna, high; 60 turns; configured context 1,050,000 |
| Judge inference | Paid OpenRouter, Azure only, fallback disabled | GPT-5.6 Sol, medium; 8,000 tokens; JSON-object response |
| Storage/retrieval | Local installed AtMem 2.3.10b1 | Source-coherent V3, original verified memories/indexes |
| Embeddings | Local Ollama | Exact digest in routes.json; no truncation |
| Both state assessors | Disabled | No model calls |

Local Hermes execution does not mean local reader inference. The abandoned
Sol-reader campaigns do not establish what produced the public result. All 6,047
public recorded assistant completions use Luna/high; the completed private run
records the same reader and disabled assessors. Historical ledger reports judge
API spend US$3.3469 across 514 calls and zero incremental reader API cash across
6,048 recorded ledger calls (including a failure); subscription fees are separate.

## Implemented and verified

- Spec Kit artifacts, persistent restart instructions and role-specific runbook.
- Isolated tool/skill profile; actual native Hermes request capture with direct
  app tools plus authorized read-only memory discovery, no local terminal/skills.
- Actual upstream sandboxed app bridge: create_doc/send_email/send_slack_dm;
  returned results, persisted state and independent logs agree.
- Crash after a successful mutation exits 73; raw evidence remains; duplicate
  journal and actual upstream app-workspace reset are refused.
- Frozen options/source/artifacts/checkpoints/interpreters/dependency inventory,
  budgets and known fixture dispositions; per-dispatch and pre-forward checks.
- Fixed 60-ID pilot executor/report with original cohorts and passed controls;
  missing grades, IDs, journal/request evidence, uncertainty or regressions block.
- Actual subscription and judge route verification; same validation on future
  full results. Full launch requires a completed passing pilot receipt.
- **64 focused tests passed** across execution readiness, existing campaign gate,
  resume and gateway suites. No release/product behavior changes are claimed.
- Claude Opus 5.5 medium review completed, fixes and confirmations retained in
  [review.md](review.md); final review is not a substitute for the live pilot.
- Original mounted image is read-only; isolated copied memories match all three
  original checkpoints through the installed AtMem API. No original DB mutation.

Public evidence: `docs/benchmarks/evidence/dolphin-execution-readiness-20261026/qualification-summary.json`.
It records synthetic qualification and hashes, not successful live pilot grades.

## Exact private condition and evidence locations

Private base: `~/.local/share/atmem-dolphin-readiness-20261026/`.

- `candidate-options-v1.json`, `candidate-descriptor-v1.json`.
- `condition-v4.json`, `condition-v4-source.json`, `receipts-v4/`.
- Condition identity:
  `32d9caadf3a84b211bab01bceec2444595e0eafc481a25ed35f51b3a77f36932`.
- `profile-v7/`: actual installed native profile capture, zero model calls.
- `synthetic-v7/`: real bridge/state/log/crash checks, zero model calls.
- `frozen-copy-v1/{home,memory,indexes,checkpoints}`: private isolated state.
- Additional private evidence/config backup on MEM:
  `/Volumes/MEM/atmem-dolphinbench-20261020/readiness-qualification-20261026-v4/`.
  This excludes API/OAuth credentials. Paths are durable files, not Codex caches.

Receipts expire after 24 hours at launch. New source/bindings require a new freeze
and qualification. Never relabel earlier receipts with a fresh timestamp.

## Failed attempts and current blocker

- `readiness-pilot-20261026-v3` under the same MEM parent failed service startup:
  provider bare model alias was passed to a CLI requiring its prefixed alias.
  Corrected; source refrozen and qualification rerun. Zero tasks/model calls.
- `readiness-pilot-20261026-v4` failed service startup because Hermes reported its
  subscription OAuth refresh token terminally invalid/already consumed by another
  client. The fixed route refused paid API fallback. Zero tasks/judge calls.
  Preserve `subscription-service.log`, condition, admission and run identity.
- Owner must complete `hermes auth add openai-codex --type oauth` sign-in.
  Do not copy/share tokens or switch the reader to OpenRouter to bypass this gate.

After sign-in, revalidate source/receipt freshness and use a **new output folder**.
Then finish exactly the fixed 60 tasks, report outcomes/costs/fixture limits and
regressions. Full remains blocked until that live report passes. No full 600 run
is authorized by this implementation task.
