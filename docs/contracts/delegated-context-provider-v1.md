# Delegated context-provider contract v1

Status: implemented in the AtMem 2.2.6 beta; disabled by default

Working contract ID: `atmem.delegated-context-provider.v1`

This contract defines an opt-in mode in which an external provider authorizes
exact context bytes—or a withholding decision—while AtMem remains responsible
for host integration, exact delivery evidence, and the agent flight.

Storizon is the initial intended provider, but the wire contract is
provider-neutral. A provider does not need access to AtMem internals, and AtMem
does not need access to the provider's memory store or receipt body.

The contract is deliberately separate from AtMem's existing preparation path.
Accepting a delegated result makes that provider the only context-decision
authority for the bound turn. It does not turn external authorization into an
AtMem memory-policy decision.

## 1. Claim boundary

A verified provider result establishes only:

> The locally registered provider authorized these exact context bytes—or
> authorized withholding—for this exact run, turn, session, agent, user, and
> workspace under the referenced receipt and expiration window.

It does not establish:

- that AtMem or the host delivered the bytes;
- that the model attended to or followed the context;
- that a tool or real-world action succeeded;
- that AtMem independently authorized the context; or
- that opaque source references are true or available.

AtMem's context-exposure and flight evidence own the delivery claim. Operator
surfaces must keep provider authorization and AtMem delivery distinct.

## 2. Wire object

Every field is required so absence cannot acquire an ambiguous default:

```json
{
  "contract_id": "atmem.delegated-context-provider.v1",
  "provider": {
    "id": "storizon",
    "version": "0.2.0a1",
    "instance_id": "storizon-demo-instance"
  },
  "binding": {
    "run_id": "run-delegated-001",
    "turn_id": "turn-delegated-001",
    "session_id": "session-delegated-001",
    "agent_id": "agent-main",
    "user_id": "user-opaque-001",
    "workspace_id": "workspace-demo"
  },
  "decision": "inject",
  "context": {
    "encoding": "base64",
    "media_type": "text/plain; charset=utf-8",
    "bytes_base64": "...",
    "byte_length": 40,
    "sha256": "..."
  },
  "receipt": {
    "id": "axr2-...",
    "contract_id": "storizon.agent-experience-receipt.v2",
    "sha256": "..."
  },
  "created_at": "2026-09-01T12:00:00Z",
  "expires_at": "2026-09-01T12:02:00Z",
  "nonce": "AAAAAAAAAAAAAAAAAAAAAA",
  "idempotency_key": "dcp-...",
  "source_refs": ["opaque:memory:decision-001"],
  "withhold_reason": null,
  "signature": {
    "algorithm": "ed25519",
    "profile": "ed25519-jcs-subset-v1",
    "key_id": "storizon-demo-key-1",
    "signed_payload_sha256": "...",
    "value_base64": "..."
  }
}
```

The closed JSON Schema is
[`delegated-context-provider-v1.schema.json`](delegated-context-provider-v1.schema.json).
Unknown fields fail closed.

For `inject`, `context` is nonempty and `withhold_reason` is `null`. For
`withhold`, `context` is `null` and `withhold_reason` is a structured
`{code, retryable}` object.

`user_id` is an opaque, host-authenticated principal binding and must never be
derived from prompt text. AtMem's existing `subject_id` is a memory-scope
identifier and remains distinct. An adapter must define an explicit mapping or
declare delegated mode unavailable when it cannot establish `user_id`.

`source_refs` is a required array that may be empty. Its entries are optional
opaque identifiers; AtMem neither dereferences nor trusts them and does not
require raw source locators.

The JSON parser must reject duplicate object keys before schema validation;
last-key-wins parsing is not an acceptable interpretation of a signed object.

## 3. Exact context bytes

For `inject`, the provider:

1. produces a nonempty, valid UTF-8 byte string;
2. computes SHA-256 over those bytes;
3. records the decoded byte length;
4. encodes the bytes using canonical padded base64; and
5. signs those properties with the identity and receipt bindings.

The v1 upper limit is 262,144 decoded bytes. A deployment may configure a
smaller limit but must not accept a larger value.

After verification, AtMem decodes once and gives the exact UTF-8 string to the
host's memory-context slot. The OpenClaw MVP maps that slot to the one
`prependContext` contribution owned by AtMem. At the exposure boundary, AtMem
hashes the actual inserted segment again. Host-added separators and surrounding
prompt content belong to the separate model-input hash.

No Unicode normalization, newline conversion, trimming, interpolation, or
reserialization is permitted between verification and insertion.

## 4. Signature and trust

The required Ed25519 signature covers the provider, all host bindings, exact
context, receipt identifier/hash, decision, time window, nonce, idempotency
key, withholding reason, and source references. A separate nested receipt
signature is unnecessary for v1.

Construct the signing input as follows:

1. Remove the complete `signature` member.
2. Serialize the remaining closed object using RFC 8785 JSON Canonicalization,
   restricted to this schema's strings, integral numbers, booleans, arrays,
   objects, and null values.
3. Prefix those UTF-8 bytes with the ASCII string
   `ATMEM-DELEGATED-CONTEXT-V1` followed by one NUL byte.
4. Sign the complete domain-separated byte string with Ed25519.

`signed_payload_sha256` is SHA-256 over that same domain-separated signing
input. The fixtures use only fixed ASCII object keys and integral numbers, so
the supplied sorted-key, no-whitespace UTF-8 test serializer is equivalent to
the restricted profile.

AtMem trusts only a locally registered tuple of:

```text
provider id + provider version + provider instance + key id + public key
```

Registration may further restrict workspace, agent, and user IDs. A public key
inside a provider result would never be self-authorizing, so v1 carries no
public key. Delegated mode is off by default.

The public key in the fixture trust record is deterministic test material and
must never be trusted outside conformance tests.

## 5. Idempotency, replay, and time

The stable idempotency key is:

```text
"dcp-" + sha256(JCS({
  contract_id,
  provider,
  binding,
  decision,
  context_sha256,
  receipt_id,
  receipt_sha256,
  source_refs,
  withhold_reason
}))
```

Creation time, expiration, nonce, the key itself, and signature are excluded.
An exact transport retry retains the same key. A semantic change produces a
different key.

The reference profile permits a maximum five-minute lifetime and 30 seconds
of future clock skew. Deployments may be stricter. Production nonces must
contain at least 128 bits from a cryptographically secure random source; the
repeated-character fixture nonces are deterministic test values only.

Acceptance state is atomic:

- the first valid result reserves the exact bound turn;
- an exact retry of the same signed envelope is idempotent;
- another result for the reserved turn fails;
- an idempotency key reused for different bytes fails; and
- a nonce reused for a different envelope fails.

Expiration is checked on every attempt. Acceptance is not a delivery event;
delivery remains pending until confirmed at the host exposure boundary.

## 6. OpenClaw MVP state machine

Recommended processing order:

1. Confirm delegated mode is explicitly enabled for this host scope.
2. Establish run, turn, session, agent, user, and workspace from authenticated
   host metadata.
3. Request one result from the configured provider.
4. Parse with duplicate-key rejection and validate the closed schema plus local
   size and time limits.
5. Match every host identity binding exactly.
6. Match the trusted provider registration, scope, and key.
7. Verify the signature, receipt/context hashes, nonce, and idempotency key.
8. Atomically reserve one result for the turn.
9. For `inject`, suppress every AtMem retrieval/injection path and contribute
   only the decoded provider bytes to OpenClaw's `prependContext` slot.
10. For `withhold`, contribute nothing and preserve the structured reason.
11. At `llm_input`, confirm the exact context-block bytes and record AtMem's
    separate delivery/exposure evidence.
12. Close the normal model, tool, and terminal flight events.

AtMem must not retrieve or inject its own memory after accepting a delegated
result. Provider failure, an invalid result, or `withhold` fails closed. Native
AtMem preparation is allowed only when an operator explicitly configures
fallback. Fallback is a new AtMem-authorized disposition—not a delegated
result—and must be labeled separately in the flight.

The same wire contract can serve later Pydantic AI and LangGraph adapters. Only
the mapping from the semantic memory-context slot to the framework changes.

## 7. Evidence separation

AtMem should retain at least:

```text
provider id/version/instance
provider result SHA-256
receipt id + receipt SHA-256
bound run/turn/session/agent/user/workspace identifiers
decision and structured withholding reason
context SHA-256 + byte length (not context bytes after handoff)
trusted key id
acceptance/idempotency disposition
AtMem exposure event id + actual context SHA-256
```

The flight should expose two distinct stages:

```text
provider.authorization = verified | rejected | withheld
atmem.delivery          = injected | not_injected | failed
```

Provider authorization does not imply delivery. Delivery does not imply model
use or an external outcome.

## 8. Conformance assets

The fixture directory contains:

- `inject.valid.json`: signed UTF-8 context with an emoji and CRLF bytes;
- `withhold.valid.json`: signed withholding with no context;
- `trust.json`: the scoped fixture public key; and
- `test-vectors.json`: three positive and twenty negative/stateful cases.

The OpenClaw conformance test verifies both signatures and exact bytes, then
exercises trust, every identity binding, temporal checks, tampering,
idempotency, one-result-per-turn, and nonce replay behavior.

AtMem implementation tests must additionally prove:

- delegated mode is off by default;
- accepted delegation suppresses every AtMem retrieval/injection path;
- OpenClaw receives exactly one context contribution;
- `llm_input` observes the provider context-block digest;
- authorization and delivery remain separate evidence records;
- invalid delegation never reaches the model; and
- fallback occurs only under explicit configuration and is labeled
  AtMem-authorized.

## 9. Implemented beta profile

The beta accepts this contract ID as written, uses an operator-configured
OpenClaw owner-to-opaque-user mapping, restricts providers to bounded loopback
HTTP, stores private trust configuration at mode `0600`, and records separate
authorization and delivery evidence. Production Python validation runs every
provided positive, negative, and stateful vector.

The AtMem request is closed by
[`delegated-context-request-v1.schema.json`](delegated-context-request-v1.schema.json).
