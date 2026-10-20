# Full-campaign readiness — 2026-10-21

The previous result was **9/30 AtMem tasks versus 7/30 Mem0 OSS tasks**, not a
five-percentage-point advantage. Thirty tasks are 5% of the 600-task release.
The original [matched report](../../benchmarks/retrieval_quality/reports/five-percent-results-20261010.md)
and [machine-readable identity](../../benchmarks/retrieval_quality/baselines/dolphinbench-final-b97d35e.json)
remain unchanged. No new task-accuracy result exists.

## Configuration comparison

| Component | Historical 30-task result | Interrupted preparation condition |
| --- | --- | --- |
| Memory ingestion | Scoped authorized history import through `Memory.form_context_episode` | Hermes control-plane capture, AtBot unconfigured, narrow deterministic fallback |
| Retrieval | `Memory.prepare_context_v3`, context-fast | Hermes authorized-at-recall binding; not the same V3 context path |
| Agent/reader | HF-routed Qwen3.5-9B, pinned revision | OpenRouter Azure-hosted GPT-5.6 Luna, medium |
| Judge | Direct OpenAI GPT-5.2-2025-12-11, medium | Planned Azure-hosted GPT-5.6 Sol via OpenRouter, medium; no scored tasks yet |
| Comparator | Matched Mem0 OSS | No matched comparator yet |

These are different configurations. The old result is a bounded reference,
not a score inherited by the new integration. Model, transport, admission or
retrieval changes require a new empty store and an explicit condition identity.

## Preparation stopped before scaling

The first 25 saved memory exports contained no canonical records. A no-model
characterization of the full public histories found only 102 Morgan, 101 Alex,
and 119 Riley rule proposals. These are extraction counts, not admission counts
or accuracy. This is not an adequate qualification of the V3 path used before.

The controller was interrupted after 101 completed exported interactions,
with interaction 102 started. Its ledger records 262 completed API requests,
US$0.415165 actual cost and no unsettled reservations. The incomplete interaction
is retained and is not automatically replayed or counted as completed.
Existing records and the exact original frozen configuration are preserved.

The private campaign entry point now refuses unbounded paid execution before
opening credentials or starting the adapter. Explicit bounded pilots remain
diagnostics, not submissions. Earlier frozen run identities must not be rewritten
to pretend this guard or another memory route was used during preparation.

## Qualification evidence

- Installed V3 API check: five original history messages per persona, encrypted
  isolated stores, explicit scope-bound import authority, nonempty context from
  history-only queries, unchanged canonical checkpoints across retrieval. No
  model calls or test questions/labels. This does **not** qualify native Hermes.
- Separate AtBot wire diagnostic: six model-generated proposals, actual cost
  US$0.000713. Replaying them through ordinary AtMem admission created six active
  records without manual approval. This is not live integration qualification,
  ground truth, or task accuracy. The wire fixes address duplicate `/v1` paths
  and explicitly non-strict JSON-schema generation; governance is unchanged.
- Hermes's read-only authentication status confirms a logged-in ChatGPT OAuth
  provider. A subsequent one-request diagnostic through its explicit Codex
  provider completed on `gpt-5.6-luna`, returned `OAUTH_OK`, and reported 28 input
  and seven output tokens. No paid API fallback or credential copying was used.
  This qualifies provider access, not the native agent's complete Responses/tool
  recording or benchmark cost-accounting compliance. Subscription usage is not
  represented as a paid API charge or as unlimited/free model usage.

## Required before full paid execution

1. Select and freeze the actual product configuration; demonstrate source
   retention, relevant context delivery to the native agent, isolation, drain
   and frozen-memory enforcement using history-only qualification inputs.
2. Prefer the user's Hermes/OpenAI subscription for agent inference if a
   supported end-to-end turn succeeds. Preserve exact model identity, all
   Responses usage and tool exchanges. Do not manufacture API cost or treat
   subscription usage as unlimited. No silent paid fallback or mid-run switch.
3. Keep the fixed Sol-medium judge. Resolve the OpenRouter-vs-direct-Azure
   transport requirement; OpenRouter reporting Azure is not itself acceptance.
4. Validate the upstream submission recording shape with offline fixtures,
   including fixed judge settings, usage, all tool results and replay grading.
   Passing fixtures cannot establish all-600 coverage or guarantee acceptance.
5. Freeze fresh stores, source/artifact hashes, models, budgets and a complete
   recording protocol before ingestion. Retain all failures. Include every
   preparation and uncertain call in the US$250 total ceiling.

The published rules allow participants to choose their agent model. Luna need
not replace Sol: they serve different roles. Official listing is an external
acceptance state and must not be promised from a private configuration.

Sources: [DolphinBench run instructions](https://dolphinbench.ai/run/), pinned
upstream `docs/DRIVER_CONTRACT.md`, `harness/runner.py`, and
`harness/submission.py`; [OpenAI subscription integration](https://developers.openai.com/siwc/token-sharing-open-source/codex-app-server).
