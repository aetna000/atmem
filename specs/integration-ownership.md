# Cross-Spec Integration Ownership

This file resolves shared-surface ownership for Specs 005–017.

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
