# Feature Specification: Memory Integrity Benchmark Qualification

**Feature Branch**: `benchmarking/memory-integrity-benchmark`

**Feature directory**: `specs/benchmarking/001-memory-integrity-benchmark`

**Created**: 2026-09-22

**Status**: Draft

**Input**: Qualify AtMem against the public Memory Integrity Benchmark, nominate
AtMem 2.3.5 without changing it, publish reproducible raw evidence for all seven
categories, and use a prerelease-first correction cycle only if the benchmark
exposes a genuine AtMem defect.

## Overview

AtMem needs independent, reproducible evidence for its persistent-memory
security boundaries. This feature integrates released AtMem into the Apache-2.0
`iluxu/memory-integrity-benchmark` Harness Specification v1 without adding
benchmark-only authority semantics or weakening AtMem's canonical admission,
scope, lifecycle, deletion, evidence, or local-first guarantees.

The first qualification target is the already published `atmem==2.3.5` wheel.
It is immutable: benchmark work may adapt only through public/native AtMem APIs.
If a trial exposes an adapter or harness defect, that defect is corrected in the
benchmark integration and 2.3.5 remains the candidate. If it exposes a genuine
AtMem product defect, the result remains visible, a regression test is added,
and any product correction begins on the next available prerelease version
(expected `2.3.6b1`, subject to repository state). A stable follow-up may be
considered only after all release gates and a complete rerun of the official
benchmark profile.

This is a memory-integrity evaluation. It does not measure general retrieval
quality, answer quality, latency leadership, overall product security, or
compliance certification.

## User Scenarios & Testing

### User Story 1 - Reproduce AtMem's integrity result (Priority: P1)

An independent reviewer can install the pinned benchmark and AtMem artifacts,
run all official trials, and regenerate the AtMem result table from raw evidence
without access to a private service, user database, or unpublished source.

**Why this priority**: A security score without independently rerunnable inputs,
configuration, outputs, and assertions is promotion rather than evidence.

**Independent Test**: From a clean Python 3.11 environment, install the frozen
dependencies, execute one smoke trial and then the official 700-trial profile,
regenerate the report, and verify every evidence-package checksum.

**Acceptance Scenarios**:

1. **Given** the published AtMem 2.3.5 wheel and pinned benchmark commit, **when**
   the full profile runs, **then** each of A, C, D, F, H, I, and L produces 100
   isolated raw trial records plus counter-derived aggregate status.
2. **Given** only `raw-trials.jsonl` and the frozen report code, **when** the
   report is regenerated, **then** its table and metrics match the published
   files byte-for-byte.
3. **Given** a changed dependency, attack definition, configuration, or result
   file, **when** evidence validation runs, **then** the mismatch is visible and
   the package is not publication-ready.

---

### User Story 2 - Review an honest native capability mapping (Priority: P1)

A benchmark maintainer can see precisely how each benchmark operation maps to
AtMem's public/native contracts and why every capability is declared,
unsupported, or not representable.

**Why this priority**: A custom adapter could otherwise manufacture security by
adding labels or enforcement behavior that AtMem itself does not possess.

**Independent Test**: Review the capability document and adapter tests against
the installed AtMem public API; remove or bypass each native control in a test
fixture and verify the relevant assertion changes rather than remaining a
harness-created pass.

**Acceptance Scenarios**:

1. **Given** source trust, derivation tracking, procedural memory, authority
   gating, purpose-scoped recall, and secret blocking, **when** the mapping is
   reviewed, **then** each declaration cites an AtMem API, persisted semantic,
   enforcement point, version, and executable test.
2. **Given** a benchmark concept that AtMem does not natively enforce, **when**
   the corresponding category runs, **then** it reports `NOT_REPRESENTABLE` or
   `NOT_SUPPORTED` rather than emulating the concept or reporting `PASS`.
3. **Given** an infrastructure, installation, or adapter error, **when** a trial
   ends, **then** it reports `ERROR` and is never counted as an AtMem security
   failure or success.

---

### User Story 3 - Preserve utility as well as protection (Priority: P1)

A reviewer can distinguish protection from a system that simply rejects every
write. The authorized-promotion positive control exercises the same native
AtMem authority path used by the defensive categories.

**Why this priority**: A deny-all adapter could appear secure while making
persistent memory unusable.

**Independent Test**: Run category I with the native authorized principal and
with missing, invalid, stale, replayed, and cross-scope authorization; the valid
promotion becomes usable while invalid promotions remain inactive and evidenced.

If AtMem 2.3.5 exposes review decisions but does not natively authenticate or
authorize the approving principal at the public contract boundary, this story is
honestly `NOT_REPRESENTABLE` for 2.3.5 rather than implemented by trusting the
benchmark's principal metadata. That outcome is a capability finding and is
triaged separately from an adapter defect.

**Acceptance Scenarios**:

1. **Given** a legitimate proposal and valid current authorization, **when** it
   is approved through AtMem's native contract, **then** the approved procedure
   becomes available as specified by the benchmark.
2. **Given** the same proposal without valid authority or from another scope,
   **when** approval is attempted, **then** it fails closed without contaminating
   active recall.

---

### User Story 4 - Diagnose failures without hiding them (Priority: P2)

An AtMem maintainer can classify every non-pass as a product defect, adapter
defect, harness incompatibility, environment error, or expected capability gap,
and can trace the classification to raw evidence.

**Why this priority**: Qualification should improve AtMem; it must not optimize
the adapter around a failing result or silently erase uncomfortable evidence.

**Independent Test**: Seed one representative failure in each classification,
verify the report preserves it, and ensure no correction rewrites the original
evidence package.

**Acceptance Scenarios**:

1. **Given** a failed assertion, **when** triage runs, **then** the original
   result is immutable and the diagnosis links to the exact trial and native
   observations.
2. **Given** a product defect in 2.3.5, **when** a correction is proposed, **then**
   it first receives an AtMem regression test and prerelease version; the fixed
   candidate is rerun across all 700 official trials before stable release.
3. **Given** an adapter or harness defect, **when** it is corrected, **then** the
   change does not alter AtMem and the affected category plus full publication
   profile are rerun with a new immutable run identity.

---

### User Story 5 - Publish and propose upstream inclusion (Priority: P2)

The community can inspect AtMem's complete evidence package and benchmark
implementation in a public fork, while upstream maintainers receive a narrow,
tested contribution that follows their evaluation contract.

**Why this priority**: External discoverability and review require upstream
compatibility, but publication must not outrun evidence quality.

**Independent Test**: Clone the public fork without local AtMem source, install
the declared artifacts, verify the published package, and run the documented
reproduction command.

**Acceptance Scenarios**:

1. **Given** a publication-ready run, **when** artifacts are committed, **then**
   raw trials, manifests, configurations, failures, aggregate metrics, generated
   table, environment lock, checksums, commands, and limitations are public.
2. **Given** upstream contribution requirements, **when** the PR is opened,
   **then** it includes the adapter, capability mapping, tests, runner/report
   generalization, evidence package, and no credentials or local paths.
3. **Given** upstream rejection or requested changes, **when** publication is
   reported, **then** the fork result is distinguished from upstream acceptance.

## Edge Cases

- The PyPI JSON endpoint lists an AtMem artifact before the simple index permits
  a normal installation; qualification waits for a clean pinned install.
- A local editable checkout differs from the nominated wheel; publication runs
  reject it or label it development-only, never 2.3.5 evidence.
- AtMem stores untrusted content in a quarantine surface: the adapter must include
  every benchmark-scoring persistent and recall surface in inspection/secret
  scans rather than equating non-injection with non-retention.
- AtMem's governed task state resembles procedural memory but has a distinct
  authority and lifecycle model; it may be mapped only if the benchmark's native
  procedural contract is satisfied without semantic invention.
- Source content is expected in the captured episode/evidence plane but the
  benchmark excludes raw conversational transcripts from category L scoring;
  the adapter documents and tests the exact scoring boundary without hiding any
  AtMem persistence surface.
- Duplicate, repeated, conflicting, derived, expired, quarantined, excluded,
  deleted, cross-agent, cross-workspace, and cross-subject records never gain
  authority merely from benchmark correlation metadata.
- Process interruption leaves a partial run; resume cannot duplicate trials or
  mix incompatible configuration identities.
- A benchmark or AtMem dependency changes after the run; the immutable commit,
  wheel digest, dependency lock, and environment manifest preserve the tested
  configuration.
- Evidence contains generated attack strings and synthetic secrets; publication
  redacts only the synthetic secret value as required while preserving its digest
  and enough native observations to reconstruct every assertion.
- Results vary across operating systems or Python versions; the canonical run
  names its environment, while a portability smoke matrix distinguishes variance
  from the canonical security result.

## Requirements

### Functional Requirements

- **FR-001**: The qualification MUST pin an immutable Memory Integrity Benchmark
  commit, its Apache-2.0 license, Harness Specification v1, AtMem distribution
  version and wheel SHA-256, dependency lock, seed, Python version, platform,
  hardware summary, configuration, and run identity.
- **FR-002**: The initial publication candidate MUST be the unmodified published
  `atmem==2.3.5` artifact installed from PyPI; editable or dirty source MUST NOT
  be reported as 2.3.5.
- **FR-003**: The integration MUST implement the benchmark's
  `MemorySystemAdapter` through AtMem's public/native APIs and MUST NOT patch
  AtMem state, reach into SQLite to fabricate behavior, or add benchmark-only
  authority, trust, taint, purpose, procedure, or secret semantics.
- **FR-004**: The capability mapping MUST independently evaluate
  `source_trust`, `derivation_tracking`, `procedural_memory`,
  `authority_gating`, `purpose_scoped_recall`, and `secret_blocking`, citing
  public/native AtMem semantics and executable tests for every declaration.
- **FR-005**: Each trial MUST use a fresh isolated AtMem Home/database, unique
  scope and deterministic benchmark variation, and MUST close and clean up all
  processes, indexes, temporary stores, and keys without reading existing user
  state.
- **FR-006**: Adapter ingestion MUST preserve benchmark source identity and map
  declared trust only through AtMem's native authenticated source/admission
  contract; harness correlation metadata MUST NOT become authority.
- **FR-007**: Native derivation MUST retain source/parent lineage and trust
  enforcement through the public contract or be reported honestly as not
  representable/supported.
- **FR-008**: Procedure proposal, approval, activation and inspection MUST use
  one native AtMem authority model. Governed task state MUST NOT be relabelled as
  persistent procedural memory unless its actual semantics satisfy the frozen
  benchmark contract.
- **FR-009**: Recall MUST use the real governed preparation/recall boundary and
  preserve scope, purpose, lifecycle, quarantine, exclusion, deletion and final
  canonical revalidation. The adapter MUST NOT post-filter a result to create a
  security pass unless that filtering is native released AtMem behavior.
- **FR-010**: Secret scanning MUST inspect every persistent memory and recall
  surface exposed by AtMem's supported public/native interface, including
  quarantined or derived records where applicable. It MUST explicitly inventory
  the separately governed encrypted Agent Black Box evidence store and classify
  each of its channels against the benchmark's scoring rules. Raw conversational
  transcript/evidence channels excluded by the benchmark MUST remain visible in
  the capability mapping and limitations; exclusion from category-L scoring MUST
  NOT be described as absence from AtMem or as data destruction.
- **FR-011**: The adapter MUST support deterministic reset, inspection, settle,
  and close operations and MUST distinguish native result data from diagnostic
  benchmark metadata.
- **FR-012**: The benchmark fork MUST generalize hardcoded adapter registries,
  labels, ordering, reporting, validation, merge/revision helpers, Make targets,
  and tests sufficiently to add AtMem without changing existing systems' frozen
  results or attack definitions.
- **FR-013**: A one-trial-per-category smoke profile MUST pass harness integrity,
  isolation, schema, cleanup and report-regeneration checks before any full run.
- **FR-014**: The publication profile MUST execute exactly 100 isolated trials
  for each of A, C, D, F, H, I, and L using the official declarative attack
  definitions and a declared seed, for 700 AtMem trials total.
- **FR-015**: Every system/category aggregate MUST use exactly one benchmark
  status: `PASS`, `FAIL`, `PARTIAL`, `NOT_REPRESENTABLE`, `NOT_SUPPORTED`, or
  `ERROR`, preserving the upstream meanings and never counting `ERROR` as a
  security outcome.
- **FR-016**: Aggregate metrics and tables MUST be reconstructed solely from raw
  per-trial counters. Bare percentages, manually edited outcomes, or a suite
  boolean without denominators MUST be rejected.
- **FR-017**: The evidence package MUST include the manifest, frozen system
  configuration and attack definitions, `raw-trials.jsonl`, aggregate metrics,
  every non-pass failure record, generated table, environment lock, reproduction
  commands, SHA-256 manifest, known limitations, durations, error/refusal counts,
  and resource metadata available without changing the official security metric.
- **FR-018**: Generated evidence and logs MUST contain no real credentials,
  private user content, local absolute paths, or unredacted synthetic secret.
  Sanitization MUST preserve evidence digests and assertion reproducibility.
- **FR-019**: The AtMem repository MUST add regression/conformance coverage for
  every native behavior on which the adapter depends, without vendoring the
  external benchmark or making it a base runtime dependency.
- **FR-020**: Triage MUST preserve the first complete evidence package, classify
  each non-pass as product, adapter, harness, environment, or native capability
  gap, and prohibit changing attack definitions, seeds, trial counts, scoring,
  or system semantics merely to improve AtMem's result.
- **FR-021**: If 2.3.5 exposes no product defect, all published qualification
  references MUST continue to identify 2.3.5 and no unnecessary version bump may
  be created for benchmark-only code.
- **FR-022**: If a genuine product defect is confirmed, the correction MUST add
  a failing AtMem boundary regression first, preserve the 2.3.5 result, target
  the next available prerelease version rather than mutate a published artifact,
  pass the full AtMem release gates, and rerun the official 700-trial profile.
- **FR-023**: A stable follow-up release MUST NOT be prepared or published until
  its prerelease artifact is clean-installable, the complete benchmark rerun and
  standard release gates succeed, and documentation distinguishes corrected and
  remaining limitations. Benchmark success alone MUST NOT authorize a release.
- **FR-024**: The public fork MUST document a one-command or bounded-command clean
  reproduction path on Python 3.11+, while AtMem regression coverage continues
  to support Python 3.10–3.13.
- **FR-025**: An upstream proposal/PR MUST be narrow, preserve existing benchmark
  results, include adapter and runner tests, disclose mappings and limitations,
  and clearly distinguish fork publication, PR submission, and upstream merge.
- **FR-026**: Public writing MUST describe the tested version, categories,
  configuration, denominators, failures, and limits; it MUST NOT claim overall
  security, OWASP compliance, certification, retrieval superiority, or an
  upstream leaderboard position.
- **FR-027**: Claude CLI consultation MUST be read-only. Its prompts and reviews
  MUST not include secrets or private user data, and recommendations are adopted
  only when they preserve this specification, the constitution, and benchmark
  comparability. Claude agreement is review evidence, never a test result.
- **FR-028**: AtMem authority, evidence, encryption, scope, lifecycle, deletion,
  exact delivery, supported integrations, and local fallback regressions MUST
  remain passing; benchmark work MUST NOT compromise AtMem's differentiators.

### Key Entities

- **Qualification Target**: Immutable AtMem distribution version, artifact
  digest, configuration, runtime and benchmark commit being evaluated.
- **Capability Mapping**: Benchmark capability, native AtMem semantic, API,
  enforcement boundary, evidence, version and representability decision.
- **Trial Workspace**: Isolated scope, store, index, keys, generated inputs and
  cleanup state for one deterministic trial.
- **Raw Trial**: Frozen inputs, native observed outputs, assertions, counters,
  status, duration, seed and identities for one system/category/trial tuple.
- **Evidence Package**: Raw trials plus generated aggregates, failures,
  configuration, environment, checksums, reproduction commands and limitations.
- **Triage Record**: Immutable original outcome, classification, diagnosis,
  reproduction, owner and disposition without retrospective result rewriting.
- **Release Candidate**: A published prerelease artifact considered only after
  a product defect is proven; distinct from adapter/harness iterations.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A clean environment installs the nominated AtMem artifact and
  benchmark lock, runs the smoke profile, and verifies its package without
  editable source, private services, existing AtMem state, or credentials.
- **SC-002**: The publication run contains exactly 700 AtMem raw trials—100 for
  each official category—with no missing/duplicate trial identity and no mixed
  environment or configuration identity.
- **SC-003**: The generated table and aggregate metrics reproduce byte-for-byte
  from raw trials, and every published evidence checksum verifies.
- **SC-004**: All six declared capability decisions have a public/native AtMem
  reference and executing adapter test; zero capability is inferred solely from
  benchmark metadata or adapter-created enforcement.
- **SC-005**: Category I demonstrates the benchmark's usable authorized path;
  if it cannot, results are not presented as an unqualified security win.
- **SC-006**: Cross-scope, quarantined, excluded, expired, deleted, repeated,
  conflicting and derived-memory fixtures cannot contaminate active recall
  outside the exact native permissions and lifecycle state being evaluated.
- **SC-007**: Published artifacts and logs contain zero real credentials, private
  user records, machine-specific absolute paths, or plaintext synthetic secrets.
- **SC-008**: Every non-pass has a raw failure record and triage classification;
  zero failure is deleted, converted to `ERROR`, or made non-representable solely
  to improve the aggregate result.
- **SC-009**: The existing AtMem installed-wheel, invariant, authority,
  extraction, retrieval, lifecycle, deletion, evidence, encryption, framework
  adapter and release-metadata gates remain passing on supported Python versions.
- **SC-010**: A third party can clone the public benchmark fork, reproduce the
  AtMem result using documented commands, and distinguish the exact tested fork
  commit from any submitted or merged upstream commit.
- **SC-011**: If no product defect is found, the final evidence nominates AtMem
  2.3.5 without a release change. If a product defect is found, a prerelease
  artifact passes its regression and all 700 rerun trials before any stable
  follow-up is proposed.
- **SC-012**: Public conclusions stay limited to persistent-memory integrity in
  the tested categories and state denominators, errors, capability gaps,
  environment and known limitations alongside favorable results.

## Out of Scope

- Changing Memory Integrity Benchmark attack definitions, assertion meanings,
  official trial counts, or existing competitor results.
- Treating the benchmark as a general retrieval, answer-quality, performance,
  privacy, compliance, OWASP-certification, or total product-security measure.
- Adding a hosted model or paid provider to AtMem's qualification path.
- Publishing a new AtMem version merely to add an external adapter or evidence
  package that does not change the AtMem distribution.
- AgentDojo, Agent Security Bench, OWASP mapping, the public Memory Security Lab,
  consultant enablement, and outreach; these are follow-on benchmarking tracks.
- Upstream merge or publicity outcomes, which remain maintainer/editor decisions.

## Assumptions

- The benchmark remains publicly available under Apache-2.0 and Harness
  Specification v1 throughout the qualification run; any contract change
  triggers review and a new run identity.
- AtMem 2.3.5 remains installable from PyPI with `atmem-atbot==0.1.0` and
  `atflows==0.1.2`; registry propagation is complete before qualification.
- The canonical benchmark environment uses Python 3.11 or newer, while AtMem's
  own release compatibility remains Python 3.10–3.13.
- All benchmark content, principals, credentials and secrets are synthetic and
  isolated; no user's `~/.atmem` directory participates.
- Public upstream contribution begins with a mapping/proposal discussion if the
  runner/report changes would otherwise be unexpectedly broad.

## Invariant Attestation

Touches INV-001, INV-002, INV-003, INV-006, INV-007, INV-010 and INV-011 through
an external adapter and its AtMem boundary regressions. The adapter does not
become a new authority surface: it exercises canonical admission, authorization
before intelligence, final revalidation, provenance, deletion, local operation
and installed-artifact compatibility. Benchmark evidence proves only the tested
category assertions; it does not prove semantic truth or overall security.
