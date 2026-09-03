# Optional delegated context authority

Native AtMem retrieval remains the default. Delegated mode is for a deployment
where a compatible local provider must remain the sole context-decision
authority for selected users, agents, and workspaces. AtMem
then verifies the signed decision, passes the exact context to the host once,
and records authorization and delivery as separate evidence.

Delegation changes only who selects context for a matching turn. It does not
move canonical memory into AtMem, import the provider's database, or give AtMem
access to the provider's internals. The provider is not bundled with AtMem; the
operator runs a compatible provider separately on the same computer.

## Choose the authority mode

| Mode | Context decision | Delivery and evidence | Failure default |
| --- | --- | --- | --- |
| Native AtMem | AtMem searches governed lexical, graph, and vector memory, then prepares context | Host adapter plus AtMem flight evidence | Safe local ranking or no context |
| Delegated provider | The registered provider signs one exact `inject` or `withhold` decision | AtMem verifies the contract; the host adapter delivers it and records what reached model input | No context |
| Delegated with explicit native fallback | Provider normally decides; AtMem may prepare a new native result only after provider failure | The fallback is labeled `atmem_fallback`, never provider-authorized | Native AtMem context |

Use native mode unless another product must remain the context authority.
Delegated mode is not required to use AtBot, semantic retrieval, OpenClaw,
Pydantic AI, or LangGraph.

## Requirements

- AtMem and the relevant host adapter must already be installed and verified.
- Context injection requires AtMem control mode to be active; shadow mode never
  injects context.
- The provider must implement the closed v1 request/result contracts and hold
  the private half of an Ed25519 signing key.
- AtMem receives only the base64 public key and a numeric loopback HTTP endpoint
  such as `127.0.0.1`. Remote endpoints and wildcard scopes are rejected in this
  beta.
- The host must supply an authenticated `user_id`. Prompt text, a memory subject,
  or an agent-generated claim cannot establish user identity.

## Set up a delegated provider

Obtain the provider version, instance ID, key ID, base64 Ed25519
public key, and loopback endpoint. Save only the base64 public key in a local
file. Find the governed workspace ID with `atmem control agents --json`, then
register exact scopes:

```bash
atmem delegated register \
  --provider-id context-provider \
  --provider-version 1.0 \
  --instance-id local \
  --key-id primary \
  --public-key-file ./provider.pub \
  --endpoint http://127.0.0.1:8788/v1/delegated-context \
  --workspace ws_123 \
  --agent main \
  --user local-owner
```

Registration does not activate delegation. Check it, then opt in:

```bash
atmem delegated status
atmem delegated self-test
atmem delegated enable context-provider:local
atmem delegated doctor
```

`self-test` verifies local signature and configuration primitives without
contacting the provider. `doctor` checks the configured scope and whether the
enabled loopback service is reachable. Its state is one of:

- `unconfigured`: no trust registration exists;
- `registered_disabled`: trust exists, but native AtMem remains authoritative;
- `ready`: an enabled provider is reachable for its registered scope;
- `degraded`: delegation is enabled, but the provider cannot be reached.

The dashboard exposes the same state and actions under **Settings → Context
authority**. The dashboard and CLI modify the same private configuration file;
neither is a separate source of truth.

For OpenClaw, map the opaque authenticated user in the bridge configuration:

```json
{
  "delegatedContext": {
    "userId": "local-owner",
    "requireOwner": true
  }
}
```

This mapping does not enable delegation. The AtMem registration is the single
activation switch. If OpenClaw cannot prove the sender is the owner, AtMem
withholds delegated context.

After changing the OpenClaw bridge configuration, verify the complete path:

```bash
atmem openclaw upgrade
atmem control verify
atmem delegated doctor
```

The `delegatedContext` block only maps authenticated host identity. Do not add
another delegation enable flag to the host configuration.

## Complete request and return path

```text
User query
  → host adapter sends query + run/turn/session/agent/user/workspace binding
  → AtMem matches an explicitly enabled trust registration
  → AtMem sends the request to the loopback provider
  → provider returns a signed inject or withhold result
  → AtMem validates identity, scope, time, bytes, receipt and replay state
  → AtMem reserves the turn and suppresses native context preparation
  → host adapter inserts one exact context segment, or inserts nothing
  → host model receives its input
  → adapter confirms the exact delivered segment at the model-input boundary
  → AtMem records provider authorization separately from delivery
  → answer returns to the user
```

AtMem never performs native retrieval after an accepted delegated `inject` or
`withhold` decision. The provider cannot authorize a different turn by changing
an ID, reuse a nonce, introduce its own public key, or cause both native and
delegated memory context to be injected.

## Turn behavior

For a matching scope:

1. AtMem sends the query and authenticated turn binding to the loopback provider.
2. AtMem validates the closed contract, time window, scope, hashes, replay state,
   and Ed25519 signature.
3. An `inject` result becomes the only memory-context contribution for the turn.
4. A `withhold` result contributes nothing.
5. AtMem confirms the exact segment at model input and records delivery evidence.

AtMem never persists the delegated query or context bytes. It retains bounded
identifiers, digests, provider attribution, receipt correlation, the decision,
and delivery state. Provider failure is fail-closed. Native fallback is possible
only when `--native-fallback` was explicitly set during registration, and the
result is labeled as AtMem-authorized fallback rather than delegated context.

## Inspect what happened

Use the dashboard **Evidence** view for the human-readable flight story, or use
the CLI for machine-readable verification:

```bash
atmem blackbox runs
atmem blackbox verify RUN_ID
atmem delegated status --json
```

For a delegated injection, evidence distinguishes:

1. the provider authorized exact bytes for the bound turn;
2. AtMem accepted the signed result and requested delivery;
3. the OpenClaw adapter observed exactly one matching segment at `llm_input`;
4. the model produced output afterward.

Authorization alone is not delivery proof, and delivery does not prove that the
model followed the context or that a real-world action succeeded.

## Failure behavior

| Symptom | Meaning | Safe action |
| --- | --- | --- |
| `unconfigured` | No provider trust exists | Keep native mode, or register the provider |
| `registered_disabled` | Registration exists but delegation is off | Review scopes and fingerprint, then enable deliberately |
| `degraded` | Enabled loopback service is unreachable | Start the provider and rerun `atmem delegated doctor` |
| Missing authenticated user | Host could not establish the registered principal | Correct the host identity mapping; do not derive it from prompt text |
| Signature, digest, expiry, binding, or replay rejection | Result did not satisfy the closed trust contract | Inspect provider logs and issue a fresh correctly bound result |
| No memory context | Provider withheld or delegation failed closed | Inspect the flight evidence; enable native fallback only if that policy is intended |

Do not work around a failure by widening user, agent, or workspace scopes. A
provider response cannot register itself or replace its trusted key.

## Disable, remove, or rotate trust

Disable or remove the integration safely:

```bash
atmem delegated disable context-provider:local
atmem delegated remove context-provider:local --yes
```

Disabling affects later turns immediately and leaves historical evidence
unchanged. Removal is allowed only after disabling. To rotate the public key,
disable the registration, replace it with the new key and key ID, inspect the
new fingerprint, run the checks, and explicitly enable it again:

```bash
atmem delegated disable context-provider:local
atmem delegated register --replace \
  --provider-id context-provider --provider-version 1.0 --instance-id local \
  --key-id rotated-2026-09 --public-key-file ./provider-rotated.pub \
  --endpoint http://127.0.0.1:8788/v1/delegated-context \
  --workspace ws_123 --agent main --user local-owner
atmem delegated status
atmem delegated enable context-provider:local
atmem delegated doctor
```

## Provider implementers

Implement the [request schema](contracts/delegated-context-request-v1.schema.json)
and the [signed result contract](contracts/delegated-context-provider-v1.md).
The contract directory includes signed inject/withhold examples and all
positive, negative, and stateful conformance vectors. Treat the request
deadline as a hard bound and return the exact binding unchanged.

The complete wire format and claim boundary are in the
[v1 contract](contracts/delegated-context-provider-v1.md).
