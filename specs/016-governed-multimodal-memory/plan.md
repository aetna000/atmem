# Implementation Plan: Governed Multimodal Memory

**Branch**: `future/016-governed-multimodal-memory` | **Date**: 2026-09-05 | **Spec**: `specs/016-governed-multimodal-memory/spec.md`

**Input**: Feature specification from `specs/016-governed-multimodal-memory/spec.md`

## Summary

Turn media into host-controlled references and governed derived observations with explicit consent, egress, model evidence, indexing, and deletion.

## Technical Context

- **Language/Version**: Python 3.10–3.13; optional processor/model versions pinned by capability.
- **Dependencies**: Specs 005/008/015; optional enterprise-compatible media/model extras.
- **Storage**: Host-held originals by default; canonical references/observations and rebuildable derived indexes.
- **Testing/Target**: pytest fake-host, malicious/sensitive media, egress, revocation, deletion, and packaging gates.
- **Constraints/Scale**: Minimum authorized content, explicit consent/egress, bounded locators and processing.

Evolve the existing media module into an `atmem/media/` package with custody/reference/observation contracts. Add processor interfaces and derived index adapters behind optional extras; reuse Spec 005 epoch health, Spec 008 retrieval explanations, and Spec 015 lifecycle/deletion verification services while preserving compatible `atmem.media` imports.

## Constitution Check

| Principle | Gate | Evidence required |
| --- | --- | --- |
| I. Authority Before Intelligence | PASS | Processors receive authorized minimum content and can only propose observations. |
| II. Provenance and Exact Evidence | PASS | Custody, locator, model/config, confidence, consent, and evidence regions are bound. |
| III. Safe Defaults and Reversibility | PASS | Host custody is default; copying, processing, indexing, and egress are opt-in. |
| IV. Scope, Privacy, and Verifiable Deletion | PASS | Consent/lifecycle is revalidated and all controlled derivatives are verified. |
| V. Contract-First Host Neutrality | PASS | Artifact/reference/observation contracts work across host media stores. |
| VI. Executable Claims | PASS | Custody, sensitive-content, egress, rebuild, revocation, and deletion tests gate claims. |
| VII. Local-First, Explicit Egress, and Replaceable Intelligence | PASS | Base reference handling is local; processors/models are optional and replaceable and cannot own canonical observations. |

Dependency gate: optional media/model packages MUST support Python 3.10–3.13 and carry Apache-2.0-compatible enterprise licensing; base imports remain dependency-free.

## Design

1. Define artifact identity, host locator, consent/custody, evidence-region, observation, processing, and deletion receipts.
2. Validate safe reference schemes and use host callbacks for bounded content access.
3. Normalize local/hosted processor output into governed proposals with model/config identity.
4. Build optional generation-bound multimodal indexes from eligible observations only.
5. Integrate retrieval explanations and lifecycle-triggered invalidation/deletion verification.

## Cross-Spec Dependencies

- **Spec 005**: derived-index epoch identity, compatibility, rebuild, and health semantics.
- **Spec 008**: registered retrieval signals, explanations, and final revalidation.
- **Spec 015**: consent/lifecycle invalidation and deletion verification.

## Project Structure

Compatible public media imports move into `atmem/media/`; models, access, processors, derived index, and service are separate modules; shared lifecycle and ranker files remain owned by Specs 015 and 008.

## Dashboard and CLI Integration

Follow `docs/dashboard-design-language.md`, preserve the four-workspace layout, and follow `specs/integration-ownership.md`: Spec 007 owns shared dashboard-shell integration and Spec 012 owns shared CLI routing/output conventions.

## Test Strategy

Schema/locator fixtures, fake-host custody, byte-change races, sensitive/redaction/egress policy, malicious files, processor failure, low confidence, scope leakage, index rebuild, consent revocation, and deletion scans.

## Rollout

Ship reference/observation contracts first; processors and indexes remain opt-in. Existing media observations migrate conservatively with unknown consent/custody requiring review where necessary.
