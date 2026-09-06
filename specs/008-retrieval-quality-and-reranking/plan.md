# Implementation Plan: Retrieval Quality, Embeddings, and Reranking

**Branch**: `storizon` | **Date**: 2026-09-06 | **Spec**: `specs/008-retrieval-quality-and-reranking/spec.md`

## Summary

Build one host-neutral pipeline: authorize, generate candidates broadly, normalize signals, establish original-query support, optionally rerank eligible records, revalidate, and build byte-stable context. Replace first-candidate fallback and raw-score fusion. Guide a strong local embedding profile while keeping hashing diagnostic-only.

## Technical Context

- Python 3.10–3.13; TypeScript for OpenClaw.
- Existing SQLite canonical/graph/vector stores and semantic epochs.
- Optional AtBot, sentence-transformers/Ollama/OpenAI-compatible embeddings, and reranker.
- Dashboard, control protocol, OpenClaw, Pydantic AI, LangGraph, and MCP consumers.

## Constitution Check

| Principle | Gate |
| --- | --- |
| Authority Before Intelligence | Authorization precedes content egress; AtMem revalidates selected IDs. |
| Provenance and Exact Evidence | Decisions record components, epochs, models, reasons, and selected IDs. |
| Safe Defaults and Reversibility | Withholding is first class; profiles are rebuildable; fallback remains. |
| Scope, Privacy, Deletion | Cache/final reload include scope, policy, lifecycle, generation, deletion. |
| Host Neutrality | Every host consumes one retrieval-decision schema. |
| Executable Claims | Held-out retrieval, privacy, poisoning, fallback, and conformance gate activation. |
| Local First | Strong local setup is guided; hosted intelligence remains optional. |

## Architecture

```text
query + authenticated scope
 -> AtMem authorization
 -> lexical / fact-key / graph / vector / expansion generators
 -> normalized signals (diagnostic hash cannot establish support)
 -> original-query support: direct | background | none
 -> eligible IDs -> optional AtBot/cross-encoder rerank
 -> AtMem canonical revalidation
 -> prepare_context_v1 -> host/MCP
```

Generation optimizes recall; support gating optimizes safe use. Trust/recency operate only after relevance. Expansion never substitutes for original-query support.

## Contracts and Persistence

Add typed signal, embedding identity, candidate, decision, and reason-code contracts under `atmem/retrieve/`, plus a JSON schema and `calibration-v1.json`. Enrich semantic compatibility identity with prefixes/preprocessing. Preserve public fields while adding the typed decision. No new canonical authority store is introduced.

## Ranking and Withholding

- Normalize lexical, fact-key, and production-vector signals independently.
- Use bounded edit-distance lexical tolerance as a deterministic spelling fallback;
  it cannot by itself broaden scope or bypass answer-support calibration.
- Require answer-support evidence for direct support; ignore hashing similarity for eligibility.
- Treat trust/recency as ordering priors.
- Make fallback query-aware and able to abstain.
- Give AtBot eligible candidates only and accept only those IDs back.
- Inject background only under explicit policy-permitted request.

## Production Embeddings

Use an explicitly supported local semantic model profile, applying model-specific query/document prefixes. Record exact model/revision, dimensions, normalization, distance, preprocessing, provider, epoch, and enterprise-compatible license metadata. Keep hashing only for tests, diagnostics, and plumbing.

## Integration

`Memory.eligible_candidates()` returns broad authorized candidates with signals, not an injection verdict. A shared retrieval service feeds dashboard query and `control_prepare`. OpenClaw, Pydantic AI, LangGraph, and MCP preserve the resulting support class and no-useful-memory outcome. The dashboard shows selected memories, withholding/degradation reason, and embedding health. Settings lists hardware-compatible catalog profiles and turns one confirmed selection into model installation, epoch build, verification, and atomic activation.

## Cache Safety

Derived-work cache keys include query bytes, subject/agent/workspace, generation, semantic epoch, calibration, requested support class, and policy. Cached IDs are canonically revalidated before delivery.

## Test Strategy

Lock the Australian-cars negative, burger paraphrase, and AtBot-down cases first. Unit-test calibration, diagnostic-hash exclusion, prefixes, staleness, and cache keys. Run identical fixtures through every host. Then run Spec 002 privacy/poisoning and held-out AtMem evaluation, with optional pinned Mem0 comparison under equal assumptions.

## Rollout

Shadow the new versioned retrieval profile, activate after SC-001–SC-008, and retain rollback without canonical migration. Users without a strong model continue with lexical/fact-key retrieval and safe abstention.

## Project Structure

- `atmem/retrieve/`: contracts, signals, calibration, ranking, cache, service.
- `atmem/semantic/`: embedding profiles/providers and epoch health.
- `atmem/schemas/v1/`: schemas and capabilities.
- `atmem/benchmark/data/`: calibration and held-out fixtures.
- `atmem/control/`, `atmem/adapters/`, `integrations/openclaw/`: thin consumers.
- `tests/`: unit, integration, cross-adapter, privacy, regression.

## Cross-Spec Dependencies

Spec 002 supplies aggregation/revalidation; Spec 005 supplies semantic epochs; Spec 007 Amendment B supplies run/turn/task correlation; Spec 009 later registers graph/entity signals.
