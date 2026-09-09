# Cross-Spec Integration Ownership

This file resolves shared-surface ownership for Specs 001–024. The 2026-09-09 amendment below governs the unified product; see `specs/product-roadmap.md` for contract-first delivery order.

## Invariant registry

Spec 018 owns `atmem/invariants/`, the `INV-001`–`INV-011` registry, verdict semantics, the attestation loader, and the release gate. Feature specs own the assertions proving their own surfaces and declare an `## Invariant Attestation` section naming the invariant IDs they touch; they do not add, retitle, or narrow an invariant without the Spec 018 amendment record.

## Dashboard shell

Spec 022 owns the target six-section information architecture (Overview, Executions, Context, Policies, Tasks, Settings), route migration, accessibility and shared shell integration in `atmem/control/assets/`. `docs/dashboard-design-language.md` remains the visual reference. This explicitly supersedes Spec 007 FR-041's four-workspace constraint and future execution of T102; completed four-workspace tasks remain historical evidence. Spec 007 retains canonical task/focus semantics and scoped task view models. Feature views consume one authority projection: global attention, execution outcome, remediation and verification are separate labelled dimensions, not competing or conflated verdicts. Shell edits are serialized through Spec 022.

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

## Cross-product acceptance (001, 018)

Spec 001 owns the reproducible cross-domain fixture campaign, including successful runs and 40-minute investigations and separated measurements. Specs 019–024 own their boundary tests; Spec 018 owns invariant registry and verdict semantics, including future assertion registration. No new invariant ID is allocated by this documentation amendment. Dependencies on 018 mean its existing registry, not completion of every future consumer test. New contracts can land before old features' integration amendments consume them; the roadmap must not be interpreted as a cyclic all-features prerequisite.
