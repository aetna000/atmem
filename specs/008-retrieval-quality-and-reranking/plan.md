# Implementation Plan: Retrieval Quality and Reranking

**Branch**: `future/008-retrieval-quality-and-reranking` | **Date**: 2026-09-05 | **Spec**: `specs/008-retrieval-quality-and-reranking/spec.md`

**Input**: Feature specification from `specs/008-retrieval-quality-and-reranking/spec.md`

## Summary

Extend Spec 002 with independently measurable registered signals, calibrated withholding/support classes, optional local reranking, and safe explanations.

## Technical Context

- **Language/Version**: Python 3.10–3.13.
- **Dependencies**: Implemented Spec 002; Spec 005 vector health; optional local cross-encoder/AtBot extras.
- **Storage**: No new canonical store; versioned calibration and benchmark data are checked-in artifacts.
- **Testing/Target**: pytest, benchmark ablations, privacy adversaries, deterministic fallback, CLI/dashboard contract tests.
- **Constraints/Scale**: Final `prepare_context_v1()` revalidation and byte-stable delivery cannot change.

Extend the implemented Spec 002 ranking path around typed signal contributions and a versioned calibration profile. Reuse fact keys, Spec 005 semantic epoch health, policy revalidation, AtBot, and benchmark infrastructure. Spec 009 later supplies the graph/entity plugin without taking ownership of the base ranker.

## Constitution Check

| Principle | Gate | Evidence required |
| --- | --- | --- |
| I. Authority Before Intelligence | PASS | Signals and rerankers see authorized candidates only; final canonical revalidation remains. |
| II. Provenance and Exact Evidence | PASS | Every score, stage, support class, rank, and delivery decision is attributable. |
| III. Safe Defaults and Reversibility | PASS | `no_useful_memory`, deterministic fallback, shadow scoring, and version rollback are explicit. |
| IV. Scope, Privacy, and Verifiable Deletion | PASS | Scope/lifecycle/deletion/exclusion checks from Spec 002 remain mandatory. |
| V. Contract-First Host Neutrality | PASS | Candidate/signal/decision contracts are host-neutral and extensible by Spec 009. |
| VI. Executable Claims | PASS | Ablation, compatibility, calibration, safety, and fallback fixtures gate release. |
| VII. Local-First and Explicit Egress | PASS | Cross-encoder is optional/local and AtBot egress remains explicit. |

Re-check after design: Spec 002 FR-010 and all `prepare_context_v1()` checks MUST still pass byte-for-byte compatibility tests.

## Design

1. Define candidate, signal contribution, support class, rank decision, and explanation contracts.
2. Give every generator a common authorized input/output boundary and measure it independently.
3. Fit/check in calibration only from declared training fixtures; evaluate separate holdout fixtures.
4. Add optional batched local cross-encoder behind the same boundary and deterministic tie-breaking.
5. Feed only revalidated selected records to existing context preparation and evidence recording.

## Spec 002 Compatibility Contract

Spec 002 remains the shipped supporting-evidence foundation. Its aggregation identity, bounded supporting-chunk signals, deterministic fallback ordering, and every FR-010 `prepare_context_v1()` revalidation check remain mandatory. Spec 008 may add typed signal envelopes and calibration around that path but MUST NOT bypass or weaken expiry, generation, lifecycle, deletion, exclusion, scope, egress, byte-stable serialization, or final canonical reload checks. Compatibility tests pin existing Spec 002 fixtures and public output fields before shadow activation.

## Test Strategy

Run per-signal ablations, calibration/holdout tests, topical-not-answer negatives, temporal/conflict cases, privacy adversaries, fallback fault injection, explanation reconciliation, and deterministic byte-output tests.

## Rollout

Shadow-score beside current ranking, compare decisions, then activate by versioned configuration. Rollback selects the prior calibration/ranker without data migration.

## Cross-Spec Dependencies

- **Spec 002**: implemented supporting-evidence aggregation and final revalidation contract.
- **Spec 005**: semantic model/epoch identity and compatibility health for the vector signal.
- **Spec 009**: downstream extension only; it registers entity/graph signals after this feature and is not a prerequisite.

## Project Structure

The base ranker and registry remain under `atmem/retrieve/`; schemas under `atmem/schemas/v1/`; benchmark fixtures under `atmem/benchmark/`; UI projections reuse existing CLI/control-plane files.

## Dashboard and CLI Integration

Follow `docs/dashboard-design-language.md`, preserve the four-workspace layout, and follow `specs/integration-ownership.md`: Spec 007 owns shared dashboard-shell integration and Spec 012 owns shared CLI routing/output conventions.
