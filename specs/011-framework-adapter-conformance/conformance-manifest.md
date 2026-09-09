# Host Conformance Manifest v1 — proposed public contract

**Owner**: Spec 011 FR-014, consumed by 020 FR-005 and the existing runtime capability authority.
**Status**: Contract definition; schema, runner and listing service are planned under 011 T013–T016.

The public deliverable is the **AtMem Host Conformance Kit**. Third parties can run it, retain results privately or publish a sanitized manifest and submit a listing. The machine schema will be published as `atmem/schemas/v1/host-conformance-manifest.json`, and versioned runner commands documented in `docs/host-conformance.md` when implemented. This document does not imply those artifacts already exist.

## Required manifest fields

| Field | Meaning and validation |
| --- | --- |
| `format` | Exact identifier `atmem-host-conformance-manifest-v1`; reject unknown versions |
| `manifest_id`, `created_at`, `expires_at` | Unique immutable result identity and explicit UTC validity window |
| `adapter` | Name, version, distribution/artifact digest and source commit where available |
| `host`, `atmem`, `suite` | Exact tested versions and artifact identities; a claimed version range requires evidence for its declared matrix |
| `configuration` | Sanitized deployment/profile identity and digest, runtime version, negotiated capability snapshot, enabled hooks and optional components; no raw environment or secret values |
| `issuer` | Identifiable submitter and evidence origin; provenance does not by itself confer independent verification |
| `profiles` | Selected profile IDs: fixture, real-host, restoration, investigation-only, context delivery as applicable; explicit missing prerequisites |
| `boundaries` | One row per tested/declared boundary: supported boolean, observed boolean, enforced boolean, result, test IDs, reason codes and evidence references |
| `results` | Each test ID, profile, exact configuration, executed flag, pass/fail/skip/unsupported/not-tested status, duration and evidence references |
| `evidence` | Content-minimized artifact references and digests, media type, producer, collection time and scope; publicly unavailable evidence remains visibly unavailable |
| `limitations` | Missing hooks, unsupported configurations, restoration limits and known failures |

Boundaries include identity/scoping, model/tool capture, context preparation/placement, dispatch authorization, retry/child linkage, terminal coverage and integration restoration. `supported` describes adapter capability; `observed` requires execution evidence for the stated profile; `enforced` requires a boundary test proving the decision was exercised. Static declarations or fixture-only results cannot establish real-host enforcement. Missing or skipped mandatory tests prevent the corresponding claim. Unknown states cannot be serialized as successful booleans without explicit qualification.

The schema validates structure and consistency; artifact verification checks digests and identity. Neither establishes the truth of an untrusted issuer's narrative. Independent reproduction requires running the declared tests against matching artifacts/configuration and retaining new evidence.

## Listing process and assurance

1. Contributor implements the documented harness, runs the kit and validates the manifest locally.
2. Contributor explicitly submits sanitized manifest/evidence references and licensing/maintainer details; no automated upload occurs by running the suite.
3. Maintainer checks identity, schema, privacy and claim consistency; accepted entries begin **self-reported**.
4. **Independently reproduced** requires a separate reproducer, matching artifact/configuration identities and linked reproduction evidence. **AtMem-verified** requires an authorized AtMem reviewer and retained AtMem-run evidence. Contributors cannot assign these badges themselves.
5. Listings record review identity, date, exact versions, assurance, evidence availability and active/stale/withdrawn status. Expiry, incompatible version changes or withdrawn evidence invalidate current claims while retaining history and reason.

Assurance and test outcome are different dimensions: a verified failed test still fails. Listing is discoverability, not automatic activation or authority. Runtime negotiation remains authoritative for the currently deployed adapter. Private/customer-hosted manifests can be inspected without public submission or an AtMem cloud account.

## Acceptance vectors

Valid: external fixture-only adapter with explicit enforcement gaps; real-host capture-only profile; independently reproduced restoration with exact host configuration.

Invalid: unsupported schema, missing version/digest, claimed enforcement from absent hooks, expired results presented as current, modified evidence, leaked credential metadata, and contributor-supplied verified status without review evidence. The kit must also accept an honest failing/partial manifest while denying unsupported positive claims.
