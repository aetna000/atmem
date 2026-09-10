# Feature Specification: Delegated Context Provider

**Product-wide requirements**: [Agent neutrality, multiple agents, private/shared memory, governed providers and clear time-aware feedback](../product-requirements.md) (PR-001–PR-006). Applies to this feature's advertised capabilities; implementation status below remains authoritative.

**Feature directory**: `specs/003-delegated-context-provider`
**Created**: 2026-09-03
**Status**: Base contract and Amendment A published in 2.2.6b10; Amendment B packaged in 2.2.6b11
**Unified product amendment status**: Specified; implementation and verification pending. The status above describes the historical baseline only.
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
5. Compatibility disposition evidence distinguishes a placement-neutral digest
   of all context AtMem delivered in the turn from the structural digest of the
   exact host-return envelope and from the later exact-segment model-input proof.

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
- **FR-012b**: For `context.disposition`, `context_sha256` and
  `context_block_sha256` MUST hash the same placement-neutral delivered-context
  aggregate: non-empty `prependContext` and `appendContext` values in that
  order, joined with exactly two LF bytes. This aggregate is not a claim that
  the values were adjacent in the rendered prompt. `context_envelope_sha256`
  MUST separately hash the canonical exact host-return object and remains the
  structural authority for field placement. Equivalent delivered content on
  delegated and native paths MUST therefore have the same aggregate digest.
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
- Hermes and other host runtime implementations beyond OpenClaw, Pydantic AI,
  and LangChain/LangGraph. Pydantic AI and LangChain/LangGraph are brought into
  scope by Amendment B below.
- Treating authorization, delivery, model use, tool execution, or real-world outcome as equivalent claims.
- Automatic native fallback or silent downgrade.

## Compatibility and Migration

- Existing installations remain native and require no new configuration.
- New persistent acceptance state is additive and versioned; migration must be automatic and safe for 2.2.5 databases.
- Removing or disabling a provider affects only future turns and does not rewrite retained flight evidence.
- Existing OpenClaw configuration without delegated fields remains valid.
- The provider contract and event formats are versioned. Additive evolution is preferred; incompatible changes require a new contract/version.

## Amendment A — Authenticated local transport (2026-09-07)

The beta-9 review confirmed that beta-3 transport still permits unsigned local
requests and repeated provider access. Signed responses do not authenticate
callers. This amendment supersedes the original transport/readiness behavior;
historical release versions above describe completed base work, not this change.
This work implements and verifies source/artifacts; publication is a separate
release operation. Storizon remains an independent consumer of the shared profile.

### User outcomes and requirements

- **FR-019**: Each provider installation MUST use its own random request secret,
  independent of Ed25519 response keys. Registrations MUST reference a private
  credential file and request key ID; secrets MUST never appear in commands,
  status, logs, evidence, or committed production configuration.
- **FR-020**: A versioned host-neutral HMAC-SHA256 HTTP profile MUST authenticate
  the exact method, authority, target, body bytes, provider/instance/key IDs,
  issue/expiry times and nonce. Missing, duplicate, malformed, unknown-key,
  wrong-instance and tampered authentication MUST fail before provider access.
- **FR-021**: Request expiry and durable atomic replay rejection MUST precede
  memory/model/provider callback access. Concurrent and restart replay attempts
  MUST invoke the callback at most once. Replay storage MUST be bounded, retain
  only authentication metadata, and fail closed on storage failure/clock rollback.
  An identical HTTP retry is rejected; existing signed-result retry idempotency
  remains unchanged. Fresh transport nonces do not promise business idempotency.
- **FR-022**: Health MUST use the same authenticated transport and MUST disclose
  no provider identity on authentication failure. Doctor MUST distinguish an
  authenticated healthy endpoint from an open TCP port.
- **FR-023**: Operators MUST have explicit credential setup, client credential
  replacement, provider rotation and old-key revocation commands. Rotation MUST
  permit a bounded overlap (at most 300 seconds), reload without restarting,
  preserve replay history, and never change response keys or enable delegation.
- **FR-024**: Old provider/configuration files MUST remain inspectable with
  actionable migration guidance. Missing credentials MUST prevent enablement
  and network calls, including previously enabled legacy registrations; they
  MUST NOT silently fall through to native retrieval. Native-only installations
  remain unchanged. Operators may explicitly disable delegation to restore native.
- **FR-025**: Shared positive/negative transport vectors and HTTP boundary tests
  MUST prove reject-before-access, authenticated health, safe rotation, migration,
  exact query/context bytes, privacy, and unchanged signed-result validation.
  Installed-wheel tests and an OpenClaw delegated turn through authenticated
  HTTP, exact llm_input delivery and flight closure MUST verify the claim.

### Acceptance scenarios

1. Another local process without the credential receives a generic rejection
   for context and health; provider callback/status spies remain untouched.
2. A valid request produces a verifiable signed inject/withhold response;
   changing any signed component or replaying the HTTP request is rejected.
3. Concurrent duplicate requests and duplicates after process restart invoke
   the provider only once. Expired requests invoke it zero times.
4. Rotation accepts old/new credentials only during the declared overlap;
   revocation or overlap expiry rejects the old key without clearing nonce state.
5. A beta-3/beta-9 enabled registration without credentials stays visibly blocked;
   guided configuration and explicit enablement restore authenticated operation.
6. The installed artifact completes an instrumented OpenClaw delegated turn with
   exact bytes at llm_input and a closed flight. A private live Storizon endpoint
   is not required for this test and must not be claimed as independently tested.

## Amendment B — Pydantic AI and LangChain/LangGraph host adapters (2026-09-08)

The base release provided provider-side framework adapters and a complete
OpenClaw host path. This amendment adds the host-side delegated lifecycle to the
existing Pydantic AI capability and LangChain/LangGraph middleware. It does not
turn those frameworks into providers and does not change who owns their state,
checkpoints, tools, or model calls.

### User outcomes and requirements

- **FR-026**: The existing Pydantic AI and LangChain/LangGraph host adapters MUST
  pass the complete run, turn, session, agent, authenticated user, and workspace
  binding to `control_prepare`. The authenticated user MAY come from the
  adapter's application-configured identity or the framework's trusted runtime
  dependency/context under the explicit `atmem_authenticated_user_id` field. A
  subject ID, prompt value, model output, or tool argument MUST NOT be promoted
  to an authenticated user identity.
- **FR-027**: When an enabled delegated registration matches the adapter's full
  scope, the provider request MUST receive the exact user-prompt text before
  whitespace normalization. The delegated prompt MUST NOT be captured into
  AtMem canonical memory. If no registration matches and native authority
  remains selected, existing normalized native capture and retrieval behavior
  MUST remain intact.
- **FR-028**: A verified delegated `inject` MUST bypass the native AtMem context
  preamble and contribute exactly one unchanged context segment: one Pydantic AI
  `UserPromptPart`, or one LangChain `HumanMessage`. A verified `withhold` or
  fail-closed result MUST contribute no delegated or native memory segment.
  Explicit native fallback retains the native preamble and is labeled
  `atmem_fallback`.
- **FR-029**: Immediately before the Pydantic AI model request or LangGraph model
  handler, the adapter MUST prove that exactly one message segment equals the
  accepted delegated context and that its UTF-8 digest matches the accepted
  digest. A mismatch MUST fail before the model call, MUST NOT confirm exposure,
  and MUST record failed delivery. Successful proof MUST confirm the delegated
  delivery and erase transient context bytes from adapter state.
- **FR-030**: Pydantic AI and LangChain/LangGraph flights MUST record provider
  authorization separately from `context.injected` delivery and the compatible
  `context.disposition` summary. Evidence MUST contain only bindings, decisions,
  provider/receipt identifiers, hashes, lengths, locations, and safe failure
  reasons—never raw query or context bytes.
- **FR-031**: The shared lifecycle MUST remain host-neutral and preserve native
  capture, task-state delivery, tool evidence, model evidence, sync/async
  LangGraph behavior, and Pydantic AI behavior when delegation is absent or
  disabled. One AtMem provider registration remains the only authority switch;
  neither framework adapter may add a second enable flag.

### Acceptance scenarios

1. A Pydantic AI run and both synchronous and asynchronous LangGraph model calls
   deliver the signed CRLF-and-emoji fixture as one exact message segment and
   close a verifiable flight.
2. Framework runtime identity overrides are read without mutating dependencies,
   context, state, messages, checkpoints, or tool configuration; missing or
   unauthenticated user identity fails closed before provider access.
3. Delegated inject, withhold, provider failure, and explicit fallback each
   select only one authority path. Spies prove no native candidate retrieval or
   canonical prompt capture occurs on a delegated-authority turn.
4. A duplicate, prefixed, suffixed, normalized, or digest-mismatched delegated
   segment is rejected before the model handler and remains unconfirmed.
5. With delegated configuration absent or disabled, the existing Pydantic AI,
   LangChain/LangGraph, task-state, and generic lifecycle regression tests remain
   behaviorally unchanged.

### Success criteria

- **SC-009**: Focused tests using real Pydantic AI and synchronous/asynchronous
  LangChain/LangGraph boundaries plus shared-lifecycle branch tests cover
  delegated inject/withhold/failure/fallback, exact delivery, identity, privacy,
  evidence separation, and flight closure.
- **SC-010**: Native framework regression tests pass unchanged, and delegated
  tests prove zero raw prompt capture, zero native-plus-delegated double
  injection, and zero model calls after failed exact-delivery proof.
- **SC-011**: Optional framework imports remain lazy, supported Python versions
  remain unchanged, and framework adapters continue to preserve host-owned
  state, checkpoints, tools, and model execution.


## Unified product amendment — 2026-09-09

**Roadmap status**: Baseline status above is historical; this amendment is specified and not implemented. Existing unchecked tasks remain prerequisites where referenced.

**Product role**: delegated authority. See [product roadmap](../product-roadmap.md) and [implementation review](../implementation-review-2026-09-09.md).

**Observed foundation**: Signed exact-byte delegation, replay protection and exposure evidence exist; independent enterprise content authorization is a different mode.

### Authorized acceptance scope

The operator subsequently authorized real Mem0 with generated dummy data and
identity role-play because Storizon access is unavailable, and limited host
compatibility to the latest releases. The current matrix targets OpenClaw
2026.9.2 and 2026.9.3 with Claude CLI 2.1.236; historical and future versions
are not a universal compatibility promise. Real Mem0 retrieval, authenticated
HTTP, real AtMem MCP and actual CLI turns establish local delivery and tool
lifecycle behavior. Role-play establishes adapter enforcement under supplied
host identities, not authenticated identity on a live shared channel.

### Additional functional requirements

- **FR-032**: Keep trusted delegation separately named from native and governed-external retrieval; record provider authorization, AtMem delegation-policy decision and observed delivery as distinct evidence.
- **FR-033**: Preserve closed delegated v1 fields and exact bytes; any enterprise redaction or composition MUST create a new versioned derived package with parent digests rather than modifying a signed provider response.

### Acceptance and success criteria

- **SC-012**: Legacy v1 inject/withhold/fallback fixtures remain compatible; native-plus-delegated double injection and relabeling provider approval as independent AtMem approval are rejected.

**Scenario**: Given the declared capability and scope, when the integrated journey executes with the relevant provider or host failure, then the additional requirements above hold and the result distinguishes observed, enforced, missing and unsupported evidence.

### Compatibility and ownership

Integration contracts: Specs 019. This feature owns its existing component adaptation only; new contract ownership is in `specs/integration-ownership.md`. New navigation follows Spec 022; historical four-workspace task text is retained as delivery history and is superseded for future integration. Preserve canonical authority, explicit activation, optional task state, host-owned checkpoints, local fallback and existing public contracts. No new capability may be advertised until its acceptance evidence passes.


## Host compatibility acceptance amendment — 2026-09-09

**Status**: Implemented and verified locally for the latest-release Mem0 scope,
with attributed Storizon acceptance against the published 2.2.6 artifacts; live
shared-channel identity remains unverified.
This amendment refines FR-006, FR-013 and evidence/readiness claims without
changing the shared HMAC profile or the closed delegated v1 response contract.
Historical verification entries above retain their original scope and date.

### Reported verification and limits

The Storizon operator subsequently reported a complete rerun against published
`atmem==2.2.6` and `openclaw-memory-atmem@2.2.6` at release commit
`04a063ce1e7bd2c95bf7d0c04bf9098f5f30c08e`. Actual Storizon, authenticated
HTTP, real AtMem MCP, OpenClaw 2026.9.2/2026.9.3, Claude CLI 2.1.251, Haiku 4.5,
Node 26.5.0 and Linux exercised eight scenarios per host. All 16 assertions
reportedly passed: three identity refusals before provider access; inject and
withhold with matching Storizon v2 receipts, exact context digests and one/zero
deliveries; successful read/exec closure; observed tool-error closure; and
deliberately suppressed result observations retaining `incomplete_evidence`.
The existing HMAC implementation required no change.

These results close the previously reported Storizon-specific v2 receipt and
local toolful lifecycle gaps for those exact versions and the isolated scoped
configuration. They are attributed partner results, not tests rerun by the AtMem
maintainer during this specification update. The release tag and published AtMem
and bridge versions were independently checked; the partner harness, CI run and
private fixture state were not independently reproduced here. Live shared-channel
identity, other hosts/backends and independent external task outcomes remain
unverified or outside scope.

### Authorized acceptance scope

The operator authorized real Mem0 with generated dummy data and identity
role-play for local maintainer acceptance, and limited host compatibility to the
latest releases. The Mem0 matrix targets OpenClaw
2026.9.2 and 2026.9.3 with Claude CLI 2.1.236; historical and future versions
are not a universal compatibility promise. Real Mem0 retrieval, authenticated
HTTP, real AtMem MCP and actual CLI turns establish local delivery and tool
lifecycle behavior. Role-play establishes adapter enforcement under supplied
host identities, not authenticated identity on a live shared channel.

### Additional functional requirements

- **FR-034**: The default OpenClaw owner gate MUST remain fail closed when
  `senderIsOwner` is absent or false. Diagnostics MUST distinguish missing host
  identity/ownership evidence from provider authentication or HMAC failure.
  Successful provider authentication MUST NOT establish host user identity.
- **FR-035**: An explicit local-operator mapping MUST be limited to an isolated,
  trusted local execution context and a bound operator/workspace/agent scope.
  It MUST NOT silently activate, infer ownership from missing metadata, override
  an explicit non-owner result, or authorize shared-channel participants. This
  refines FR-006 only for an explicitly trusted isolated local mapping; shared
  channels still require authenticated per-turn host identity. If isolation or
  the mapping scope cannot be established, delegation MUST fail closed. The
  mapping is identity configuration, not a second delegated-authority switch.
  If the host omits CLI origin, the mapping additionally MUST name an absolute,
  owner-only, non-symlink state directory matching `OPENCLAW_STATE_DIR`; the
  current process MUST be `agent --local`, without delivery/routing flags and
  without configured shared channels. Exact agent, workspace, session key and
  session generation remain required. Missing ownership is never inferred.
- **FR-036**: Observed read/exec requests MUST NOT imply tool completion or a
  complete verified toolful flight. Required terminal observations MUST correlate
  to the same tool invocation and turn; missing observations MUST retain
  `incomplete_evidence`, even when delegated delivery and the text response pass.
  A terminal tool failure MAY close evidence when fully observed, but MUST NOT
  be reported as successful tool execution. When typed completion hooks are
  absent, a real terminal host tool-event result MAY supply the observation only
  when its run, session, invocation and canonical tool match a recorded request.
  Store only scope and result digests in a bounded, expiring process cache;
  deduplicate typed completions and reject conflicting or incomplete results.
  Feature-detect host event APIs rather than accepting a version string as proof.
- **FR-037**: Compatibility reporting MUST separately identify provider protocol
  conformance, isolated local text-only execution, default owner-gate behavior,
  shared-channel identity, and toolful lifecycle closure. Each claim MUST state
  its tested host/package versions, identity configuration, evidence source,
  and passed/blocked/unverified outcome. Local text-only success MUST NOT promote
  either remaining gate to ready or imply compatibility with other host versions.

### Acceptance and success criteria

- **SC-013**: Retain the supplied Storizon report with its original attribution;
  independently exercise real Mem0 inject/withhold through authenticated HTTP,
  MCP and the latest real OpenClaw CLI releases. Match provider receipt digests
  to the bound flight, exact context digests, one/zero deliveries and verification
  results. Mem0 receipts do not establish Storizon v2 receipt compatibility.
- **SC-014**: On the real CLI path, absent `senderIsOwner` blocks the default
  owner gate. An explicit isolated local mapping permits only its trusted scope;
  absent mapping, explicit non-owner identity, scope mismatch, and attempted
  shared-channel reuse fail closed without provider access or delegated delivery.
- **SC-015**: Under the authorized role-play substitute, exercise non-owner,
  missing identity and cross-user/workspace refusals through the real bridge/MCP
  with real Mem0, proving denied turns never access the provider. Keep live
  authenticated shared-channel principal binding explicitly unverified; local
  success cannot authorize a broader shared-channel readiness claim.
- **SC-016**: A separate real toolful check correlates read/exec requests with
  observed terminal results and verifies flight closure with truthful tool
  outcomes. A missing-completion case returns `incomplete_evidence`; unmatched
  or cross-turn observations cannot close it. Toolful lifecycle readiness for a
  host/provider profile remains unverified until that profile has positive
  closure evidence. Text-only completion does not satisfy this criterion.

Shared-channel identity and toolful lifecycle closure are independent acceptance
gates before broader readiness claims. Toolful closure now passes for the scoped
Mem0 and attributed Storizon configurations above; shared-channel identity does
not. Host lifecycle evidence contracts remain owned by Specs 011 and 020; this
feature verifies their use on delegated turns.
