# Feature Specification: Delegated Context Provider

**Feature directory**: `specs/003-delegated-context-provider`
**Created**: 2026-09-03
**Status**: Implemented, verified, and published as provider-neutral beta 2
**Input**: Implement the provider-neutral delegated context-provider v1 contract proposed in PR #1. Existing AtMem authority remains the default. Delegated mode is an explicit opt-in that lets a compatible provider remain the sole context-decision authority for a bound turn while AtMem owns host delivery and flight evidence.

## Overview

AtMem normally retrieves, authorizes, and prepares context itself. That behavior must remain unchanged for every existing installation and upgrade. Some integrations instead need an external system to remain the context authority. In delegated mode, a locally trusted provider returns one signed `inject` or `withhold` decision bound to the exact host turn. AtMem validates the result, reserves the turn atomically, injects accepted bytes without modification, suppresses its native context preparation for that turn, and records provider authorization separately from delivery.

The wire contract is provider-neutral. No provider receives a privileged product-specific bypass. A public key sent inside a result is never trusted. Delegated mode cannot be activated until an operator registers a provider identity, key, allowed scope, transport endpoint, and failure behavior.

## Clarifications

### Session 2026-09-03

- Q: Which authority mode remains the product default? → A: Native AtMem authority remains the default; delegated provider authority is explicit opt-in.
- Q: What happens when enabled delegation is missing, invalid, expired, untrusted, or unavailable? → A: Fail closed by default; native AtMem fallback requires a second explicit setting and is labeled AtMem-authorized.
- Q: Which provider transport is the first implementation? → A: Provider-neutral loopback HTTP with bounded timeout; remote transport is out of scope for this beta.
- Q: How is an OpenClaw user identity established? → A: Only authenticated host metadata may supply `user_id`; delegated mode is unavailable for a turn when the adapter cannot establish it.
- Q: What prerelease identifiers are used? → A: Python `2.2.6b2`; npm `2.2.6-beta.2` only if the adapter package is released.

## User Scenarios and Acceptance

### User Story 1 — Existing users upgrade without behavior change (P1)

As an existing AtMem user, I can install the beta and continue using native AtMem context authorization without configuring a delegated provider or seeing new failures.

**Independent test**: Upgrade a representative 2.2.5 database and OpenClaw installation, run native shadow and active turns, and compare context, evidence, restore, and dashboard behavior with delegated mode absent.

**Acceptance scenarios**:

1. Given no delegated configuration, every native retrieval, AtBot ranking, AtMem authorization, injection, and exposure path behaves as before.
2. Given an older database, opening it performs only backward-compatible migration and preserves native mode.
3. Given the dashboard or CLI, delegated mode is described as optional and never appears active unless explicitly enabled.

### User Story 2 — An operator safely enables delegated authority (P1)

As an operator, I can register a provider's identity and Ed25519 public key, restrict its scope, verify connectivity, and explicitly enable delegated mode with clear warnings about the changed authority boundary.

**Independent test**: Register a loopback test provider, enable it for one workspace and agent, and verify that status/doctor show the provider, allowed scope, key fingerprint, timeout, failure policy, and current authority mode without exposing secrets.

**Acceptance scenarios**:

1. Registration requires provider ID, version, instance ID, key ID, public key, endpoint, and allowed workspace/agent/user scopes.
2. A self-declared key in a provider response is ignored and cannot authorize a result.
3. Enabling delegated mode requires an explicit command or dashboard confirmation; registration alone does not activate it.
4. Remote HTTP endpoints, ambiguous wildcard scope, malformed keys, and unsafe timeouts fail closed in the beta.
5. Disabling delegated mode immediately restores normal native behavior for later turns without rewriting historical evidence.

### User Story 3 — Exact delegated injection occurs once (P1)

As a host user, when the provider authorizes context for my exact turn, the host receives those exact bytes once and AtMem does not add a second memory context.

**Independent test**: Submit the signed CRLF-and-emoji fixture through the OpenClaw hook path and prove byte identity at acceptance, adapter handoff, and `llm_input`, with one context contribution and no native prepare call.

**Acceptance scenarios**:

1. AtMem rejects duplicate JSON keys, unknown fields, invalid UTF-8/base64, excessive size, digest mismatch, signature failure, expired/future results, identity mismatch, untrusted providers, and replay.
2. A valid `inject` result is atomically accepted for only its bound run, turn, session, agent, user, and workspace.
3. Accepted context is decoded once and is never trimmed, normalized, interpolated, converted, or reserialized before host insertion.
4. Native AtMem retrieval and context preparation are suppressed for that turn.
5. At `llm_input`, AtMem separately confirms the actual inserted segment digest; authorization alone is never presented as delivery proof.

### User Story 4 — Withholding and failures are safe and understandable (P1)

As a host user, a valid provider withholding decision or failed delegation never causes unintended native memory injection.

**Independent test**: Exercise signed withholding plus invalid, timeout, connection, replay, and scope failures under default fail-closed behavior and explicit native-fallback behavior.

**Acceptance scenarios**:

1. A valid `withhold` result contributes no context, suppresses native retrieval, and retains its structured reason.
2. Invalid or unavailable delegation contributes no context by default and records a reason safe for users and auditors.
3. When native fallback is separately enabled, failure creates a new AtMem-authorized preparation; it is never relabeled as delegated authorization.
4. A provider retry of the identical signed envelope is idempotent; a different result for the reserved turn is rejected.

### User Story 5 — Evidence names the real authority (P1)

As an auditor, I can distinguish what the provider authorized from what AtMem delivered and what the host/model later did.

**Independent test**: Verify complete inject, withhold, rejection, and explicit-fallback flights and inspect their human-readable stories and machine-readable events.

**Acceptance scenarios**:

1. Evidence records provider identity/version/instance, trusted key ID/fingerprint, result digest, receipt ID/digest, exact bindings, decision, context digest/length, disposition, and exposure correlation without storing context bytes or public-key material in the flight.
2. Provider authorization and AtMem delivery are separate stages and neither implies model use, tool success, or real-world outcome.
3. Dashboard and CLI use plain language—“Provider authorized” and “AtMem delivered”—while technical IDs remain available on demand.
4. Existing Agent Black Box verification remains valid for native and delegated flights.

### User Story 6 — Beta installation and recovery are simple (P2)

As an evaluator, I can install or upgrade to the beta, configure a test provider, run a self-test, disable the option, and return to native AtMem behavior using guided CLI and dashboard actions.

**Independent test**: Install clean and upgrade from 2.2.5 in isolated environments, configure the fixture provider, run doctor/self-test, disable it, and verify native context works afterward.

**Acceptance scenarios**:

1. `atmem --help`, delegated subcommand help, dashboard settings, and README provide the complete safe path without requiring internal documentation.
2. Doctor distinguishes unconfigured, registered, enabled, reachable, trusted, degraded, and explicit-fallback states and recommends one next action.
3. The release contains schema, fixtures, migration coverage, changelog/release notes, version consistency, wheel inspection, and installed-artifact tests.

## Functional Requirements

- **FR-001**: Native AtMem authority MUST remain the default and MUST be behaviorally unchanged when delegated mode is not configured and enabled.
- **FR-002**: Delegated mode MUST be scoped, explicit, reversible, disabled by default, and clearly identified in CLI, dashboard, status, doctor, and flight evidence.
- **FR-002a**: One AtMem registration enablement MUST be the authority switch. Host adapters MAY require an authenticated user mapping but MUST NOT introduce a second independent enable flag. For OpenClaw, enablement MUST fail readiness until the control-plane adapter path is active.
- **FR-003**: The implementation MUST accept only `atmem.delegated-context-provider.v1` envelopes conforming to the closed schema and semantic rules in `docs/contracts/delegated-context-provider-v1.md`.
- **FR-004**: The beta MUST use bounded loopback HTTP transport only, with configurable timeout from 100 ms through 30 seconds and a default no greater than 3 seconds.
- **FR-005**: Trust registration MUST bind provider ID, provider version, provider instance ID, key ID, Ed25519 public key, and allowed workspace, agent, and user scopes. Result-carried key material MUST never establish trust.
- **FR-006**: OpenClaw MUST source `user_id` only from authenticated host metadata. If unavailable, delegated mode MUST fail closed for the turn.
- **FR-007**: Validation MUST reject duplicate keys before schema/semantic validation and MUST verify exact binding, canonical signing input, Ed25519 signature, time window, context byte length/hash/UTF-8/base64, receipt binding, nonce, and idempotency key.
- **FR-008**: Acceptance MUST atomically enforce one result per complete turn binding, exact retry idempotency, idempotency-key integrity, and nonce replay prevention across process restarts.
- **FR-009**: A valid `inject` result MUST suppress native AtMem retrieval/preparation and deliver exactly one unchanged context contribution through the host's AtMem-owned memory slot.
- **FR-010**: A valid `withhold` result MUST suppress native retrieval/preparation and inject nothing.
- **FR-011**: Invalid, unavailable, or timed-out delegation MUST fail closed by default. Native fallback MUST require explicit per-registration configuration and MUST create separately labeled AtMem-authorized evidence.
- **FR-012**: Evidence MUST separately represent provider authorization and AtMem delivery/exposure, minimize content, remain hash-chain bound, and correlate receipt/result/context digests with the bound flight.
- **FR-012a**: Delegated query and context bytes MUST NOT be persisted in control previews, acceptance rows, delivery rows, configuration, or flight evidence. The adapter MAY retain the exact accepted context only in bounded process memory until `llm_input` confirmation or expiry.
- **FR-013**: The OpenClaw adapter MUST never perform both delegated and native injection for one turn and MUST confirm actual delegated context bytes at `llm_input` where the host exposes that boundary.
- **FR-014**: CLI and dashboard MUST support register, inspect, enable, disable, status, doctor, self-test, and remove actions with clear authority and fallback language.
- **FR-015**: The implementation MUST expose provider-neutral Python/control contracts so later Pydantic AI, LangGraph, Hermes, and other adapters can integrate without provider-specific core logic.
- **FR-016**: Persistent changes MUST include migration and upgrade coverage from AtMem 2.2.5, backup/restore behavior, deletion/cleanup behavior, and unchanged native behavior.
- **FR-017**: The beta MUST preserve Python 3.10–3.13 support, local-first operation, Apache-2.0 compatibility, and avoidance of unrelated mandatory model SDKs.
- **FR-018**: Current release artifacts MUST use Python version `2.2.6b2`; npm version `2.2.6-beta.2` applies only when an adapter artifact is published. Published claims MUST match installed-artifact tests.

## Edge Cases

- Provider responds after the turn deadline or after native explicit fallback has reserved the turn.
- The same nonce or idempotency key is replayed after restart, for another turn, or by another provider instance.
- Two concurrent requests attempt to reserve different decisions for the same turn.
- The provider authorizes empty, non-UTF-8, oversized, or deceptively encoded content.
- Host metadata contains a subject but no authenticated user principal.
- Registration is disabled or removed while a request is in flight.
- A valid authorization is accepted but the host never exposes it to the model.
- The host changes separators around the inserted segment without changing the segment bytes.
- Backup is restored onto a machine without the provider configuration or key.
- Explicit native fallback succeeds after provider failure; late provider output must not replace it.

## Success Criteria

- **SC-001**: Existing native deterministic, AtBot, semantic, OpenClaw, framework, multi-agent, restore, and Agent Black Box suites pass with delegated mode absent.
- **SC-002**: All three positive and twenty negative/stateful PR fixtures pass against production validation, not only the reference test.
- **SC-003**: Tests prove exact byte equality across signed fixture, AtMem acceptance, OpenClaw `prependContext`, and exposure digest for emoji plus CRLF content.
- **SC-004**: Concurrent and restart tests prove zero double acceptance, zero nonce replay, and zero native-plus-delegated double injection.
- **SC-005**: Default failure tests produce zero context injections; explicit fallback tests produce only clearly labeled AtMem-authorized context.
- **SC-006**: Clean-install and 2.2.5-upgrade tests pass on supported Python versions without requiring a delegated provider or a hosted model.
- **SC-007**: CLI/dashboard usability tests demonstrate the authority mode, provider health, trust scope, failure policy, and next safe action without displaying raw keys or context.
- **SC-008**: Built wheel and, if changed, npm package pass contract, installation, version, license, and smoke verification before beta publication.

## Out of Scope

- Making delegated mode the default.
- Giving a delegated provider access to AtMem internals or giving AtMem access to the provider's memory store.
- AtMem independently authorizing or modifying provider-selected context in delegated mode.
- Remote provider transport in the first beta.
- Pydantic AI, LangGraph, Hermes, or other host runtime implementation in this beta; only provider-neutral core contracts are required.
- Treating authorization, delivery, model use, tool execution, or real-world outcome as equivalent claims.
- Automatic native fallback or silent downgrade.

## Compatibility and Migration

- Existing installations remain native and require no new configuration.
- New persistent acceptance state is additive and versioned; migration must be automatic and safe for 2.2.5 databases.
- Removing or disabling a provider affects only future turns and does not rewrite retained flight evidence.
- Existing OpenClaw configuration without delegated fields remains valid.
- The provider contract and event formats are versioned. Additive evolution is preferred; incompatible changes require a new contract/version.
