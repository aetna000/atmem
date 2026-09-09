# Cross-Spec Integration Ownership

This file resolves shared-surface ownership for Specs 001–025. The 2026-09-09 amendment below governs the unified product; see `specs/product-roadmap.md` for contract-first delivery order.

## Invariant registry

Invariant-bearing specs are governed by 018 FR-012 regardless of feature number; ranges in historical reviews are not an exclusion list. Ongoing verification belongs to per-feature append-only entries under `docs/implementation-evidence/NNN/`, following that journal's README. `docs/current-status.md` links to supported capability evidence; the dated implementation review is frozen history.

The binding product-wide requirements are [PR-001–PR-006](product-requirements.md): agent neutrality, multiple agents, private/shared memory, governed providers, explanatory feedback and time provenance. They apply to every feature and advertised profile; M0 has an explicit narrower delivery scope, not an exception allowing host-specific core authority.

Spec 018 owns `atmem/invariants/`, the `INV-001`–`INV-011` registry, verdict semantics, the attestation loader, and the release gate. Feature specs own the assertions proving their own surfaces and declare an `## Invariant Attestation` section naming the invariant IDs they touch; they do not add, retitle, or narrow an invariant without the Spec 018 amendment record.

## Dashboard shell

Spec 022 owns the target seven-section information architecture (Overview, Executions, Context, Connections, Policies, Tasks, Settings), route migration, accessibility and shared shell integration in `atmem/control/assets/`. `docs/dashboard-design-language.md` remains the visual reference. This explicitly supersedes Spec 007 FR-041's four-workspace constraint and future execution of T102; completed four-workspace tasks remain historical evidence. Spec 007 retains canonical task/focus semantics and scoped task view models. Feature views consume one authority projection: global attention, execution outcome, remediation and verification are separate labelled dimensions, not competing or conflated verdicts. Shell edits are serialized through Spec 022.

## CLI shell

Spec 012 owns public transport/error/output-envelope conventions and the integration router in `atmem/cli.py`. Feature specs own handlers in their feature packages. Shared-router edits are serialized through Spec 012 and MUST preserve human/JSON parity, stable exit behavior, and authority-safe errors.

## Retrieval signals

Spec 008 owns `atmem/retrieve/signals.py`, the base ranker, calibration, explanations, and extension registry. Spec 009 owns `atmem/retrieve/graph_signal.py` and registers entity/graph behavior through that extension point without modifying base ownership.

## Adapter capabilities

Spec 007 owns task-aware adapter identity/lifecycle, activation gating, and `atmem/contracts/versions.py::capabilities()` as runtime authority. Spec 011 owns framework-specific bindings and their reusable conformance suite; every capability projection mirrors Spec 007's authority.

## Application service

Spec 012 owns the transport-neutral `atmem/service/` package. Spec 013 consumes `atmem/service/application.py` and adds production-only infrastructure under `atmem/server/`; it does not create another service module.

## Canonical schema and migrations

Spec 010 owns the future canonical-store protocol and global SQLite migration registry in `atmem/store/sqlite.py`, but it is not an implementation prerequisite for Specs 006 or 007. The current unnumbered idempotent initializer remains the pre-registry baseline. Before Spec 010 lands, Spec 006 reserves bootstrap migration identifiers `0060–0069` and Spec 007 reserves `0070–0079`; each appends only inside its range and MUST remain idempotent. Spec 010 formalizes the registry by recording that baseline and importing the reserved bootstrap identifiers without renumbering or replaying them. Later Specs 012 and 015 request identifiers through the formal registry. No feature may renumber, replace, reuse, or bypass an earlier identifier. The combined published-version upgrade suite is the release authority for the resulting sequence.

## Maintenance orchestration

Spec 007 owns the shared maintenance job registry and scheduling integration in `atmem/maintenance.py`, because it is the first roadmap feature that extends the existing maintenance surface. Specs 009 and 015 register graph-repair and lifecycle jobs through that interface without creating competing schedulers or changing another feature's job semantics.

## Retrieval cache

Spec 010 owns `atmem/retrieve/cache.py`, including key identity, invalidation, revalidation, and byte-stability rules. Spec 013 may configure limits and expose production metrics through the public cache interface, but MUST NOT weaken keys, bypass revalidation, or mutate cache internals directly.

## Lifecycle invalidation

Spec 015 owns `atmem/lifecycle/invalidation.py` and its derived-consumer registry. Spec 016 registers media observations, previews, embeddings, and retained-copy verifiers through that registry; it does not modify lifecycle ordering or verification semantics independently.

## Provider-neutral context (019)

Spec 019 owns `atmem/context/` package/decision/provider/grant contracts and native-provider orchestration. Spec 004 owns external connector implementations and SDK compatibility; Spec 008 still owns native ranking. Spec 003 owns unchanged closed trusted-delegation v1 and signature semantics. Governed-external authorization is independently performed by AtMem; trusted delegation stays explicitly labelled. Spec 023 owns only the lifecycle subpackage and consumes the 019 grant interface. Provider packages never create a second canonical memory store.

## Execution and investigation (007, 020, 021)

Spec 007 Amendment B owns `atmem/contracts/execution.py` baseline identity, task focus/links and `atmem/investigation/` locator. Spec 020 extends that same identity with job/attempt/parent/producer fields and owns `atmem/execution/` durable capture, coverage and execution projections. Existing `atmem/control/blackbox.py` remains the flight-verification foundation; event-contract additions are serialized through 020. Its control-store migrations use the existing control-store version sequence, coordinated with Spec 010 for any canonical references. Do not put execution authority in task memory or fabricate old associations.

Spec 021 owns `atmem/incidents/` findings, dependency-impact projections, explanation claims and resolution revisions. It consumes the existing locator and 020 evidence, with optional 019 context links. It never creates another task, flight or memory authority. Checkpoint ownership and external-effect verification stay with registered hosts/verifiers.

## Application projections (012)

Spec 012 owns shared operation authorization, public schemas, HTTP/MCP/SDK/CLI mappings and `atmem/service/`. New feature service modules (context, executions, incidents, fleet) live inside that package and invoke their domain owners. Runtime submissions and operator actions have distinct authenticated capabilities. Spec 011 owns actual framework bindings; 020 adds coverage contracts through the existing `capabilities()` authority rather than a parallel registry.

## Context lifecycle and fleet (023, 024)

Spec 023 owns `atmem/context/lifecycle/` revocation, exposure lineage and policy simulation, registering invalidation through 015 and obtaining observed exposures through 020. It cannot rewrite past deliveries or claim causal influence from exposure.

Spec 024 owns optional `atmem/fleet/` policy distribution and evidence anchoring; Spec 013 owns production route authentication, credentials, workers and recovery under `atmem/server/`. Local operation is independent of fleet availability. Administrative evidence remains distinct from agent-reported events.

## Provider connection journey (025)

Spec 025 owns the guided provider connection lifecycle, authentication experience, effective-access preview, conditional approval and first-delivery monitoring requirements. It extends existing registration authority through 019/003 and connectors through 004, uses 012 public services and 013 authenticated administration, and reuses 017 onboarding. Spec 022 integrates its top-level Connections destination; the prior six-section target is superseded by seven sections. Context retains source/package evidence, Policies retains governing rules, and Settings retains broader identity/deployment administration. Spec 024 adds optional federation/fleet distribution; no second credential authority or fleet prerequisite is introduced for local setup.

## Cross-product acceptance (001, 018)

Spec 001 owns the reproducible cross-domain fixture campaign, including successful runs and 40-minute investigations and separated measurements. Specs 019–025 own their boundary tests; Spec 018 owns invariant registry and verdict semantics, including future assertion registration. No new invariant ID is allocated by this documentation amendment. Dependencies on 018 mean its existing registry, not completion of every future consumer test. New contracts can land before old features' integration amendments consume them; the roadmap must not be interpreted as a cyclic all-features prerequisite.

## Canonical terminology and compatibility projections

| Concept | Canonical product term | Preserved legacy term/API | Projection rule and owner |
| --- | --- | --- | --- |
| Whole correlated job | Execution | Flight, run/session identifiers | 020 owns execution projections. An execution may contain multiple flights/attempts only with explicit identity links; an unlinked legacy flight stays a flight, never a fabricated complete job. |
| Evidence for a captured run | Flight evidence | `verify_flight`, flight IDs and verified-flight report | 020 preserves the original record and verifier semantics. 021 consumes its observations; “verified flight” does not imply business success or complete host coverage. |
| Actionable evidence statement | Finding | `attention_points`, `flight_attention` | 021 owns deterministic translation from each attention point to scoped finding classification and source-event references. Preserve original reasons; keep recovered, unresolved and missing-evidence states distinct. |
| Summary of work needing review | Attention summary | Attention queue, review/failed badges | 021 owns aggregate rules over findings and legacy verifier results; 022 renders them. Deduplicate by evidence identity and use one service projection, not two independent counters. Acknowledgment changes review state only. |
| Authorized context artifact | Context package | Native context text and delegated exact payload | 019 owns the envelope and authority mode. Preserve original bytes/signatures; transformed content gets new lineage. A package is distinct from proof of delivery. |
| Evidence of preparation/decision/delivery | Receipt | Existing receipt/exposure/confirmation IDs | 019 owns receipt-to-package references; 020 links observed delivery events. Receipts remain evidence objects, never renamed into packages. Missing legacy links remain unknown. |
| Result and operator follow-up | Execution outcome; finding/remediation/verification states | Flight outcome and acknowledgment | 020 owns observed execution outcome, 021 owns resolution states, 022 renders both. Acknowledgment cannot rewrite a flight outcome or verify an external action. |

Spec 012 owns public serialization and legacy aliases; 020/021/019 own the mappings above. M0 already uses these mappings inside the existing shell; 022 must not ship parallel vocabularies or infer equivalence from similar labels. Shared mapping fixtures cover one execution with several flights, unlinked flights, duplicate attention, recovered errors and receipts with no known package.

## Memory spaces, membership, feedback and timestamps

Planning decomposes 012 FR-015 into T016–T032 and 013 FR-010 into T012–T025. Their original umbrella rows are roll-ups. 013 T012 freezes principal/trust identity against baseline 012; 012 T016 consumes it for membership contracts. Production routes consume 013 T018/T019; 024 and 025 are downstream consumers, never prerequisites for this foundation. See each plan for persistence, generation, invalidation and recovery boundaries.

Spec 012 owns the transport-neutral MemorySpace/SpaceMembership contract and persisted authenticated service, reusing the current scope authority with Spec 010 migration allocation. Spec 006 owns canonical admission/contributor provenance, 015 invalidation and 019 provider use/delivery authorization. Spec 022 renders private/shared membership and permission controls; 017/025 consume them in onboarding and connection access previews. Memory access, execution visibility and credential administration are independent grants. Existing scopes keep their behavior on upgrade.

Spec 012 owns feedback serialization; each domain owns its state/reason/verification facts. Spec 020 owns event/receive time and ordering; Spec 021 owns finding effects and next-action advice; Spec 022 owns shared timestamp/timezone/freshness rendering. Spec 025 shows actual authentication checks and expiry. No client replaces missing timestamps with now, renews checks on refresh, infers authority from color or independently computes a conflicting verdict.

## Public host conformance

Spec 011 owns the named Host Conformance Kit, versioned manifest schema, public runner, contributor documentation and listing criteria. Spec 020 supplies execution-coverage fields through that contract; Spec 007 retains runtime capability authority. Manifest validation and listing do not enable an adapter. Results distinguish self-reported, independently reproduced and AtMem-verified assurance with exact versions, configuration and evidence. INV-009 is host-neutral under amendment 018-A001; each host supplies its own restoration coverage.
