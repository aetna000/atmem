# Feature Specification: Governed Multimodal Memory

**Feature directory**: `specs/016-governed-multimodal-memory`
**Created**: 2026-09-05
**Status**: Draft
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
