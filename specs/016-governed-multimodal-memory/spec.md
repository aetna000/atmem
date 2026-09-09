# Feature Specification: Governed Multimodal Memory

**Product-wide requirements**: [Agent neutrality, multiple agents, private/shared memory, governed providers and clear time-aware feedback](../product-requirements.md) (PR-001–PR-006). Applies to this feature's advertised capabilities; implementation status below remains authoritative.

**Feature directory**: `specs/016-governed-multimodal-memory`
**Created**: 2026-09-05
**Status**: Implemented
**Unified product amendment status**: Specified; implementation and verification pending. The status above describes the historical baseline only.
**Input**: `todo.md` P2.15

## Overview

Recall evidence from images, audio, video, files, and tool artifacts while keeping original bytes host-controlled by default. AtMem stores governed references and derived observations with consent, model, confidence, provenance, retention, and deletion semantics.

## User Scenarios & Testing

### User Story 1 - Capture a media observation safely (Priority: P1)

A host supplies an authorized artifact reference and consent/retention state. Optional processing produces evidence-located observations; AtMem does not copy original bytes unless a separate storage policy explicitly permits it.

**Why this priority**: Media processing begins at a sensitive custody and consent boundary.

**Independent Test**: Process a host-held fixture through a fake local processor and verify no original-byte copy plus exact observation provenance.

**Acceptance Scenario**: **Given** an authorized host reference and consent, **when** processing runs, **then** only governed derived observations are stored unless copying was explicitly approved.

### User Story 2 - Retrieve and delete derived knowledge (Priority: P2)

Queries retrieve authorized observations and optional multimodal-index candidates with safe previews and exact source references. Revocation/deletion makes observations, thumbnails, embeddings, caches, and references ineligible and verifiably removes controlled copies.

**Why this priority**: Derived media knowledge must obey the same retrieval and deletion boundaries as text memory.

**Independent Test**: Retrieve, revoke consent, and delete one artifact while checking every registered derivative.

**Acceptance Scenario**: **Given** consent revocation during processing, **when** late output arrives, **then** it cannot activate and deletion verification identifies every controlled copy.

### Edge Cases

- Changed bytes at the same locator, expired host access, corrupt or malicious files, unsupported codecs, low confidence, processor timeout, and consent revocation fail with stable reasons.
- Artifact metadata cannot leak existence across scope even when original bytes stay outside AtMem.
- Deletion during processing prevents late observations or embeddings from becoming active.

## Requirements

### Functional Requirements

- **FR-001**: Define versioned contracts for image, audio, video, file, and tool-artifact references, locators, media identity/digest, custody, consent, and retention.
- **FR-002**: Original bytes MUST remain host-controlled by default; copying/thumbnailing/transcoding requires an explicit storage policy and receipt.
- **FR-003**: Derived observations MUST record source locator, producing model/provider/revision, prompt/config digest, time, confidence, consent, scope, and exact evidence region when available.
- **FR-004**: Processors MUST receive only authorized minimum content and record local/hosted egress and redaction decisions.
- **FR-005**: Optional multimodal embeddings MUST be derived, generation-bound, compatibility-checked, rebuildable, and deletable.
- **FR-006**: Unsupported/unavailable references, expired access, changed bytes, low confidence, unsafe types, and malware/policy rejection MUST fail safely with reason codes.
- **FR-007**: Retrieval MUST revalidate artifact and observation scope/lifecycle/consent before ranking and delivery.
- **FR-008**: Deletion/consent revocation MUST invalidate all controlled observations, indexes, caches, previews, and retained copies, with backup-policy truth.
- **FR-009**: CLI/dashboard/API MUST distinguish original, reference, derived observation, model inference, and inaccessible/withheld evidence.
- **FR-010**: Optional media/model dependencies MUST support Python 3.10–3.13 and have Apache-2.0-compatible enterprise licensing; base reference contracts MUST import without them.

### Key Entities

- **Artifact Reference**: Scoped digest/locator, media kind, custody, consent, and retention state.
- **Derived Observation**: Evidence-located statement with model/config/time/confidence provenance.
- **Processing Receipt**: Authorized input extent, egress/redaction, provider identity, and outcome.
- **Multimodal Index Generation**: Rebuildable compatible derived vectors tied to eligible observations.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Contract fixtures cover every media class, custody mode, consent state, and evidence locator.
- **SC-002**: Sensitive-content and cross-scope suites record zero unauthorized processing, egress, preview, retrieval, or metadata leakage.
- **SC-003**: Revocation/deletion receipts reconcile every derived consumer and controlled byte copy.
- **SC-004**: Base installation handles references without requiring media/model dependencies or network access.
- **SC-005**: Python-version and dependency-licence audits pass for every advertised processor/index extra and the clean base-install import test remains green.

## Out of Scope

Becoming a general media store, silently retaining originals, or treating model observations as ground truth without provenance/confidence.

## Assumptions

- Specs 005, 008, and 015 provide index, retrieval, and lifecycle foundations.
- Hosts can resolve approved references through a bounded callback contract.
- Unknown legacy consent/custody is not assumed permissive.
## Invariant Attestation

Touches INV-001, INV-002, INV-003, INV-006, and INV-007 through `spec016.reference-authority`, `spec016.preprocessor-auth`, `spec016.observation-revalidation`, `spec016.lineage`, and `spec016.revocation`.


## Unified product amendment — 2026-09-09

**Roadmap status**: Baseline status above is historical; this amendment is specified and not implemented. Existing unchecked tasks remain prerequisites where referenced.

**Product role**: media context lineage. See [product roadmap](../product-roadmap.md) and [implementation review](../implementation-review-2026-09-09.md).

**Observed foundation**: Host-custodied references and derived observations exist.

### Additional functional requirements

- **FR-011**: Represent media-derived context through the common provider/package envelope with artifact version, observation region, consent, processor and egress provenance.
- **FR-012**: Revalidate source access before explanation or preview; expired consent and missing host artifacts MUST yield explicit unavailable evidence, not fetches outside registered access.

### Acceptance and success criteria

- **SC-006**: An artifact-consent revocation prevents new governed delivery and preview while retaining only permitted exposure links; no raw media or secret enters the incident summary.

**Scenario**: Given the declared capability and scope, when the integrated journey executes with the relevant provider or host failure, then the additional requirements above hold and the result distinguishes observed, enforced, missing and unsupported evidence.

### Compatibility and ownership

Integration contracts: Specs 019, 023. This feature owns its existing component adaptation only; new contract ownership is in `specs/integration-ownership.md`. New navigation follows Spec 022; historical four-workspace task text is retained as delivery history and is superseded for future integration. Preserve canonical authority, explicit activation, optional task state, host-owned checkpoints, local fallback and existing public contracts. No new capability may be advertised until its acceptance evidence passes.
