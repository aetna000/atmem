# Implementation Plan: HTTP API and TypeScript SDK

**Branch**: `future/012-http-api-and-typescript-sdk` | **Date**: 2026-09-05 | **Spec**: `specs/012-http-api-and-typescript-sdk/spec.md`

**Input**: Feature specification from `specs/012-http-api-and-typescript-sdk/spec.md`

## Summary

Create one transport-neutral service package, versioned loopback HTTP API, and semantically equivalent Python, TypeScript, MCP, CLI, and dashboard clients.

## Technical Context

- **Language/Version**: Python 3.10–3.13 and a declared supported Node/TypeScript range.
- **Dependencies**: Existing local server stack; generated TypeScript types and enterprise-compatible npm runtime.
- **Storage**: Existing canonical stores plus bounded SQLite idempotency receipts.
- **Testing/Target**: OpenAPI validation, pytest, TypeScript golden vectors, installed-package and upgrade tests.
- **Constraints/Scale**: Loopback default, bounded pagination, explicit timeouts, agent/admin separation.

Turn the existing empty `atmem/service/` namespace into a regular package and extract a transport-neutral application service from `Memory`, review, audit, and control modules. Add `/v1` routes to the existing server, OpenAPI under `docs/contracts/`, and a separately packaged TypeScript SDK under `packages/typescript/`. Do not create a competing `atmem/service.py` module.

## Constitution Check

| Principle | Gate | Evidence required |
| --- | --- | --- |
| I. Authority Before Intelligence | PASS | The service delegates all mutations, authorization, and context to canonical AtMem APIs. |
| II. Provenance and Exact Evidence | PASS | Stable request IDs, evidence identities, idempotency receipts, and error contracts persist. |
| III. Safe Defaults and Reversibility | PASS | Loopback is default; activation, preconditions, idempotency, and deprecation are explicit. |
| IV. Scope, Privacy, and Verifiable Deletion | PASS | Agent/admin separation, cursor isolation, redaction, and deletion outcomes are tested. |
| V. Contract-First Host Neutrality | PASS | OpenAPI is transport/language neutral and all clients share one service layer. |
| VI. Executable Claims | PASS | Cross-language golden vectors, installed SDK examples, and published-upgrade tests gate release. |
| VII. Local-First and Explicit Egress | PASS | API defaults to local loopback and clients never silently introduce provider egress. |

Dependency gate: the Python package remains compatible with 3.10–3.13; the npm package and all generated/runtime dependencies MUST be Apache-2.0-compatible. SQLite idempotency schema changes MUST pass real persisted upgrades from published AtMem versions.

## Design

1. Define public resource/error/page/idempotency/auth-operation schemas before handlers.
2. Route HTTP, CLI/dashboard, Python helpers, and MCP through one service layer.
3. Store bounded idempotency receipts transactionally with mutations.
4. Generate TypeScript types from pinned OpenAPI, then add hand-maintained ergonomic clients without semantic loss.
5. Version with additive compatibility checks and explicit sunset metadata.

## Test Strategy

Schema snapshots, authorization matrix, idempotency races, cursor mutation tests, timeouts/cancellation, redaction, Python/TS golden vectors, MCP mapping, and installed-package examples.

## Rollout

Ship loopback `/v1` disabled unless the local control server is enabled. Keep internal calls until parity gates pass, then migrate UI/CLI incrementally.

## Project Structure

Application services live in `atmem/service/`; routes reuse `atmem/control/server.py`; OpenAPI lives in `docs/contracts/`; Python client in `atmem/client.py`; TypeScript package in `packages/typescript/`.

## Dashboard and CLI Integration

Follow `docs/dashboard-design-language.md`, preserve the four-workspace layout, and follow `specs/integration-ownership.md`: Spec 007 owns the dashboard shell while this feature owns shared CLI routing, public output/error conventions, and API transport integration.
