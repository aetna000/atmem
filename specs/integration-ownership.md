# Cross-Spec Integration Ownership

This file resolves shared-surface ownership for Specs 005–018.

## Invariant registry

Spec 018 owns `atmem/invariants/`, the `INV-001`–`INV-011` registry, verdict semantics, the attestation loader, and the release gate. Feature specs own the assertions proving their own surfaces and declare an `## Invariant Attestation` section naming the invariant IDs they touch; they do not add, retitle, or narrow an invariant without the Spec 018 amendment record.

## Dashboard shell

`docs/dashboard-design-language.md` and Spec 007 own the four-workspace information architecture, navigation, single global verdict, shared accessibility behavior, and integration points in `atmem/control/assets/app.js`. Feature specs own their scoped view models and feature modules. Changes to the shared shell are serialized through the Spec 007 contract; no feature may add a fifth workspace or a competing global verdict.

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
