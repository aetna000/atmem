# Implementation Plan: Storizon Delegated Context Provider

## Technical Context

- **Runtime**: Python 3.10–3.13 and the existing TypeScript OpenClaw adapter.
- **Release target**: AtMem `2.2.6b1`; OpenClaw adapter `2.2.6-beta.1` if published.
- **Contract input**: `docs/contracts/delegated-context-provider-v1.md`, its closed JSON Schema, signed Ed25519 fixtures, and 23 conformance vectors from PR #1.
- **Default behavior**: Native AtMem context authority remains unchanged. Delegated mode is absent/off unless a scoped registration is explicitly enabled.
- **Transport**: HTTP POST to a loopback endpoint only for this beta. The request deadline and response size are bounded.
- **Trust**: Locally registered Ed25519 public keys and exact provider/version/instance/key/scope matching. `cryptography` supplies maintained Ed25519 verification; no model SDK is added.
- **Persistence**: Private configuration stores registration and activation state. Control SQLite schema v5 stores atomic acceptance/replay state. Flight evidence remains content-minimizing.
- **Host path**: `control_prepare` chooses exactly one authority path. OpenClaw injects delegated bytes in one `prependContext` contribution and records delivery separately at `llm_input`.

## Constitution Check

| Principle | Plan compliance |
|---|---|
| I. Authority Before Intelligence | Native mode remains governed by AtMem. Delegated mode is separately named and explicit; AtMem enforces contract/trust but does not reinterpret provider-selected context. |
| II. Provenance and Exact Evidence | Signed bytes, provider receipt, bindings, acceptance, handoff, and delivery use distinct digests and events. |
| III. Safe Defaults and Reversibility | Delegation is disabled by default, fail-closed, independently reversible, and native fallback requires explicit opt-in. |
| IV. Scope, Privacy and Deletion | Trust is scope-bound; raw delegated context is not persisted in flight evidence; configuration removal affects future turns only. |
| V. Contract-First Host Neutrality | Core request/result/decision types are provider- and host-neutral. OpenClaw owns only host mapping and injection. |
| VI. Executable Claims | PR fixtures, production validation, concurrency/restart, exact-byte, native regression, upgrade, wheel, and npm tests gate release. |
| VII. Local-First and Explicit Delegation | Loopback-only beta, explicit authority label, and no self-authorizing result key satisfy the separately named delegated-authority exception. |

No constitution amendment is required.

## Architecture and Decisions

### 1. Provider-neutral delegated package

Create `atmem/delegated/`:

- `contracts.py`: frozen request/binding/result/decision types and content-minimizing public result dictionaries;
- `canonical.py`: restricted RFC 8785-compatible serialization for the closed integral/string schema, domain separation, and deterministic idempotency calculation;
- `validation.py`: duplicate-key rejecting JSON parser, closed-shape/semantic validation, exact digest/base64/UTF-8 checks, time checks, trust matching, and Ed25519 verification;
- `config.py`: private atomic configuration with registration, enabled state, scoped trust, timeout, maximum bytes, explicit fallback, fingerprint, and safe status projection;
- `client.py`: bounded loopback HTTP request/response transport;
- `service.py`: orchestration of request, validation, atomic acceptance, evidence projection, and fail-closed/fallback disposition.

The core package uses generic terms (`delegated provider`, `provider_id`) rather than embedding Storizon logic. Storizon is a CLI/dashboard preset and the fixture provider identity.

### 2. Request contract

Define `atmem.delegated-context-request.v1` as the AtMem-to-provider request:

```json
{
  "contract_id": "atmem.delegated-context-request.v1",
  "binding": {
    "run_id": "...",
    "turn_id": "...",
    "session_id": "...",
    "agent_id": "...",
    "user_id": "...",
    "workspace_id": "..."
  },
  "query": "exact user query",
  "query_sha256": "...",
  "max_context_bytes": 262144,
  "deadline": "UTC timestamp"
}
```

All fields are required and closed. The query is sent only to the registered loopback provider and is never copied into acceptance or flight evidence. The provider response is the existing signed v1 result.

### 3. Private configuration and activation

Use `~/.atmem/delegated-context.json`, written atomically with mode `0600`. Its versioned shape contains registrations keyed by provider/instance. Every registration has:

- provider ID/version/instance and key ID;
- raw 32-byte Ed25519 public key encoded as canonical base64;
- allowed workspace, agent, and user identifier lists with no wildcard in the beta;
- loopback endpoint, timeout, and maximum context bytes;
- `enabled` and `native_fallback_on_failure` booleans, both false initially.

Registration never enables delegation. `enable` is a separate operation. Only one registration may be enabled for an exact scope tuple; ambiguous matches fail closed. CLI and dashboard render only a SHA-256 key fingerprint, never the raw key.

### 4. Durable acceptance and replay protection

Raise `ControlStore.SCHEMA_VERSION` from 4 to 5 and add:

- `delegated_context_acceptances`: envelope digest, provider tuple, complete turn binding, decision, receipt/context digests and lengths, key ID, timestamps, nonce digest, idempotency key, disposition, and evidence correlation;
- `delegated_context_deliveries`: content-free requested/shown/failed delivery state bound to one acceptance and exposure identifier; this does not reuse native `previews`, because native previews persist context text;
- unique indexes for complete bound turn, provider-instance plus nonce digest, and provider-instance plus idempotency key.

Use `BEGIN IMMEDIATE` to validate prior state and insert acceptance atomically. Exact envelope retries return the original acceptance as idempotent. Any semantic conflict fails. Context bytes are returned to the caller but are not stored in this table.

### 5. Authority switch in `control_prepare`

Extend `ControlManager.prepare()` and the control tool contract with required-for-delegation `turn_id`, `user_id`, and `workspace_id` inputs.

Processing order:

1. Resolve native control state and the authenticated authority tuple.
2. Find zero or one enabled delegated registration matching workspace/agent/user.
3. If none, execute the existing native path byte-for-byte.
4. If one, request and validate one provider result.
5. Atomically accept the result before producing output.
6. For `inject`, return the exact decoded text, delegated evidence projection, and `context_location=prependContext`; do not call native candidate retrieval or `prepare_context_v1()`.
7. For `withhold`, return no context and do not call native retrieval.
8. For provider failure, reject by default. Only an explicitly configured fallback executes the existing native path, labeled `authority=atmem_fallback`.

The output remains additive so older adapters ignore unfamiliar fields. New adapters use `authority`, `delegated`, `context_location`, and evidence correlations.

### 6. OpenClaw binding and exact insertion

Add an optional `delegatedContext` adapter configuration with:

- `userId` with no default;
- `requireOwner` default true.

The AtMem registration's `enabled` state is the single authority switch; the
adapter does not introduce a second enable flag. The adapter passes the
configured user ID only when host hook metadata confirms the sender is the
owner. It creates/reuses a stable per-hook turn ID and sends
run/session/agent/workspace bindings to `control_prepare`. If a registration
could match but authenticated identity is missing, the request fails closed.
OpenClaw readiness also requires its control-plane adapter path to be active.

For delegated `inject`, return `{prependContext: exactContext}` with no concatenation or suffix. Native output remains in its existing location. Record:

- `context.provider_authorization` when AtMem reports accepted/withheld/rejected provider disposition;
- `context.delivery` from `llm_input` using the actual inserted-segment digest;
- existing `context.disposition` for compatibility, with explicit authority and no candidate IDs for delegated context.

Pending prompt state may retain the exact accepted context only in process
memory for the existing bounded prompt-cache lifetime. `llm_input` locates that
exact string in the model input, verifies that it occurs once, hashes its UTF-8
bytes, records delivery, and immediately removes the value. It is never written
to configuration, SQLite, logs, or flight evidence. Provider keys and raw
receipt bodies are never retained there.

### 7. Operator experience

Add `atmem delegated` commands:

- `register`, `enable`, `disable`, `status`, `doctor`, `self-test`, and `remove`;
- `--json` output for automation;
- examples in parent/subcommand help;
- safe next-action guidance and explicit authority/fallback language.

Dashboard Settings receives a collapsed “Context authority” row. Native AtMem is shown as the default. Opening the row exposes Storizon registration, scope, connection test, enable/disable, failure policy, and copyable CLI equivalents. Destructive remove requires confirmation and never erases historical evidence.

### 8. Documentation and beta release

Update README quick start, contract status, generic/OpenClaw integration docs, dashboard language, changelog/release notes, and `todo.md`. The beta instructions show:

1. install/upgrade;
2. verify native default;
3. register trust;
4. run doctor/self-test;
5. explicitly enable;
6. disable and return to native mode.

Build the wheel and npm package in isolated directories. Inspect contents and metadata, install the wheel over 2.2.5, run production fixture and native tests from installed artifacts, then publish only after all gates pass.

## Data and Contract Details

### Public decision projection

```json
{
  "format": "atmem-delegated-context-decision-v1",
  "authority": "delegated",
  "decision": "inject",
  "context": "exact decoded text",
  "context_sha256": "...",
  "context_byte_length": 40,
  "acceptance_id": "dca_...",
  "provider": {"id":"storizon","version":"...","instance_id":"..."},
  "receipt": {"id":"...","sha256":"..."},
  "result_sha256": "...",
  "idempotent": false
}
```

The context exists only in the immediate prepare response. Persisted evidence omits it.

### Evidence events

- `context.provider_authorization`: `verified_inject`, `verified_withhold`, `rejected`, or `unavailable`.
- `context.delivery`: `injected`, `not_injected`, or `failed`.
- `context.disposition`: compatibility summary with `authority=delegated|atmem|atmem_fallback`.

Every event uses versioned formats and hashes. Provider authorization never sets delivery fields.

## Failure and Threat Analysis

- **Self-authorization**: response keys are ignored; only local trust matches.
- **Replay**: durable unique constraints plus transactional checks cover turn, nonce, and idempotency across restart/concurrency.
- **Double injection**: authority routing occurs before native candidate work, and the adapter has one exclusive delegated return branch.
- **Late response**: deadline and envelope expiration are checked before acceptance; fallback reservation prevents a late provider result.
- **Identity confusion**: subject is never substituted for user; missing owner/authenticated mapping fails closed.
- **Unicode mutation**: strict UTF-8 decode once, byte hash before/after transport, no whitespace transformations.
- **Configuration tamper**: private regular file, no symlink, atomic writes, closed versioned shape, safe projections.
- **Endpoint abuse**: loopback host, HTTP only, bounded timeout/response, no redirects, no userinfo.
- **Evidence leakage**: no raw query/context/public key in configuration,
  acceptance, delivery, preview, audit, or flight persistence; exact context
  exists only in the immediate response and bounded adapter memory until
  delivery confirmation.
- **Restore without provider**: history verifies; future delegation remains disabled/degraded until local config and trust return.

## Implementation Touch Points

```text
atmem/delegated/                                  new host-neutral implementation
atmem/control/store.py                           schema v5 acceptance/replay state
atmem/control/manager.py                         exclusive authority routing
atmem/control/server.py                          additive control inputs/actions
atmem/cli.py                                     delegated operator commands
atmem/control/web.py                             dashboard API
atmem/control/assets/app.js                      subtle authority settings UI
atmem/control/assets/app.css                     authority UI states
integrations/openclaw/index.ts                   binding, exclusive injection, evidence
integrations/openclaw/src/types.ts               authenticated identity shape
integrations/openclaw/openclaw.plugin.json        optional delegated configuration
tests/test_delegated_context.py                   production contract/security tests
tests/test_delegated_control.py                   manager/store/CLI/dashboard tests
tests/test_openclaw_control.py                    host boundary integration
integrations/openclaw/test/*.mjs                  exact-byte and double-injection tests
docs/contracts/*                                 implemented contract/request docs
README.md, docs/*, todo.md                        user guidance and status
pyproject.toml, integrations/openclaw/package.json prerelease metadata
```

## Verification Strategy

- Production Python validation against all PR fixtures/vectors.
- Duplicate-key, closed-shape, base64, UTF-8, hash, signature, time, trust, binding, endpoint, and size tests.
- SQLite migration from schema 4, exact retry, concurrent conflict, process-restart replay, backup/restore, and cleanup tests.
- Native mode regression with no delegated config and with disabled registration.
- Manager tests spying that native retrieval is never called after delegated acceptance/withhold/default failure.
- OpenClaw tests for owner/user mapping, exact `prependContext`, one contribution, `llm_input` digest, explicit fallback, and missing identity.
- CLI and dashboard tests for discoverability, safe status, confirmation, and no key/context leakage.
- Full Python and npm suites, deterministic benchmark, package build/inspection, clean install, and 2.2.5 upgrade.

## Rollback

Disable delegated mode first. Native AtMem behavior resumes for future turns. Schema v5 tables are additive and may remain unread by older releases, so package rollback after opening a v5 control database requires restoring the pre-upgrade control-plane backup. Canonical memory databases are unchanged. Historical evidence and acceptances are never rewritten by disable/remove.
