# Context-provider adapters

AtMem normally owns governed retrieval. Context-provider adapters are an
optional deployment mode for teams that want Mem0, a LangGraph, or a Pydantic
AI agent to remain the context-decision authority while AtMem verifies and
delivers the exact result once and records the agent flight.

Installing or starting an adapter does not enable it. The safe sequence is:

1. install exactly one optional extra;
2. initialize and start its private loopback service;
3. register its public key, request-credential references and exact user, agent, and workspace scopes;
4. inspect status and doctor output;
5. explicitly enable that registration.

Disable the registration to return immediately to native AtMem authority.

## Mem0

Use Mem0 OSS locally:

```bash
python -m pip install 'atmem[mem0]'
atmem provider init mem0-local --kind mem0 --mode oss --port 8788
atmem provider start mem0-local
atmem provider doctor mem0-local
```

The Mem0 extra installs the verified Python 2.x SDK range
`mem0ai>=2.0.20,<3`. AtMem calls both OSS and Platform search with mandatory
`filters={"user_id", "agent_id", "app_id"}` plus bounded `top_k`; it never
retries without those three scope boundaries. Accepted results retain Mem0's
ranked order when the provider runtime builds the signed context proposal.

For Mem0 Platform, export the credential only in the provider process
environment and select platform mode:

```bash
export MEM0_API_KEY='...'
atmem provider init mem0-cloud --kind mem0 --mode platform --egress hosted --port 8788
```

Every search carries all three authenticated boundaries in one call:
`user_id`, `agent_id`, and `app_id` (the AtMem workspace). The adapter never
retries without them. A contradictory returned scope is discarded.

If your application already constructs a configured Mem0 client, expose a
zero-argument Python factory and pass `--factory package.module:build_client`.

## LangGraph

```bash
python -m pip install 'atmem[langgraph-provider]'
atmem provider init graph-context --kind langgraph \
  --factory myapp.memory_graph:build_graph --port 8789
atmem provider start graph-context
```

The factory returns a compiled graph or compatible callable. It receives a
fresh `delegated_request` dictionary and a fresh config whose `thread_id` is
bound to the authenticated session and turn. Its final output is closed:

```python
{
    "context_decision": {
        "decision": "inject",
        "items": [{"text": "User likes burgers.", "source_ref": "memory:42"}],
        "source_refs": ["memory:42"],
    }
}
```

Sync and async graphs are supported. An interrupt or malformed result fails
closed and produces no signed authorization.

## Pydantic AI

```bash
python -m pip install 'atmem[pydantic-provider]'
atmem provider init ai-context --kind pydantic-ai \
  --factory myapp.memory_agent:build_agent --egress local --port 8790
atmem provider start ai-context
```

The factory returns a configured Pydantic AI agent. Use
`atmem.provider_adapters.pydantic_ai.proposal_output_model()` as its
`output_type`, or return a compatible validated output model. AtMem reads only
`AgentRunResult.output`; free-form model text is not accepted as authority.
Mark hosted models with `--egress hosted` so status and receipt attribution do
not imply local processing.

## Register and enable exact trust

`atmem provider init` prints a complete registration command with three
placeholders. Replace them using authenticated IDs from your host integration:

```bash
atmem delegated register \
  --provider-id mem0-context-provider --provider-version 1.0 \
  --instance-id mem0-local --key-id primary \
  --public-key-file ~/.atmem/providers/mem0-local/public.key \
  --endpoint http://127.0.0.1:8788/v1/delegated-context \
  --request-key-id REQUEST_KEY_ID --request-secret-file /absolute/private/request.key \
  --workspace WORKSPACE_ID --agent AGENT_ID --user USER_ID
atmem delegated status
atmem delegated enable mem0-context-provider:mem0-local
atmem delegated doctor
```

Provider failure withholds context by default. Native fallback exists only if
you deliberately add `--native-fallback` at registration. AtMem still verifies
binding, signature, expiry, replay state, receipt digest, and exact context
bytes, and the host still has to confirm what reached model input.

## Stop and roll back

```bash
atmem delegated disable mem0-context-provider:mem0-local
atmem provider stop mem0-local
atmem provider remove mem0-local --yes
```

Removal deletes the provider's local key and configuration. It does not delete
the external provider's database and does not erase AtMem's historical flight
evidence.

## Authenticated HTTP and beta migration

Beta 10 requires the shared
[HMAC request profile](contracts/delegated-request-auth-v1.md). Newly initialized instances generate
their own request secret independently of their Ed25519 keys. The init command
prints the exact request key ID and secret-file reference in its registration
command; use those values instead of the placeholders above.

Unsigned context and health requests are rejected before provider access.
Doctor checks authenticated health. An identical HTTP replay is rejected even
after restart; signed-response acceptance idempotency is unchanged.

For an old managed instance, stop it, run `atmem provider auth-init INSTANCE`,
and start it again. Attach the returned credential references with
`atmem delegated set-request-auth PROVIDER:INSTANCE --request-key-id KEY_ID
--request-secret-file /absolute/private/request.key`, check doctor, then
explicitly enable. Legacy enabled registrations without credentials stay blocked
until migrated or explicitly disabled. Provider `auth-rotate` and `auth-revoke`
support bounded overlap without restarting; see the profile for exact commands.

Custom providers such as Storizon must adopt the same HTTP profile and generate
their own per-installation request secret. AtMem's managed-provider commands do
not configure an external Storizon service. Public demo keys remain test-only.


## 2.2.6 delegated host compatibility

The maintainer-run acceptance scope is OpenClaw **2026.9.2 and 2026.9.3** with
Claude CLI **2.1.236**, real local Mem0, Qdrant and Ollama, and dummy data. A
separate attributed Storizon rerun used the same OpenClaw versions with Claude
CLI **2.1.251**, Haiku 4.5, Node 26.5.0 and Linux against the published AtMem and
bridge 2.2.6 artifacts.

| Boundary | Evidence | Result |
| --- | --- | --- |
| Storizon HMAC/v2 receipts | Partner rerun against published 2.2.6 artifacts | Reported pass on both hosts; exact receipt/context digests and one/zero deliveries |
| Storizon identity refusal | Three scenarios per host | Missing ownership, legacy owner bypass without mapping, and wrong session generation refused before callback |
| Storizon tool lifecycle | Actual read/exec, missing-file error and suppressed-observation scenarios | Reported complete success, completed_with_tool_errors and incomplete_evidence respectively |
| Default owner gate | Actual CLI turns on both latest releases | Missing owner metadata refused; zero provider acceptance |
| Isolated local inject/withhold | Actual CLI, real Mem0, authenticated HTTP and real MCP | Exact receipt/context digests, one/zero deliveries, complete flights |
| Read/exec and terminal errors | Actual tool execution on both latest releases | Complete success or completed_with_tool_errors, with observed terminal results |
| Missing completion | Actual tool execution with deliberate result-observation suppression | incomplete_evidence on both releases |
| Identity role-play | Real Mem0/MCP/bridge; synthetic host principals/scopes | Non-owner, missing owner, cross-user and cross-workspace denied before provider access |
| Live shared-channel identity | No authenticated shared-channel fixture | Unverified; role-play cannot establish it |

The CLI sends terminal results on the host tool-event stream when typed completion
hooks are absent. The bridge matches those observations to requests and records
result digests; requests or model text never create completion evidence. Missing,
conflicting or mismatched observations still fail closed. This matrix does not
promise every historical/future OpenClaw version or every channel/backend.

See [identity configuration](delegated-context-provider.md#isolated-local-cli-identity-226),
[maintainer-run Mem0 evidence](implementation-evidence/003/20260909T052000Z-740c5c89d63c-mem0-latest-hosts.md),
and the [attributed Storizon 2.2.6 report](implementation-evidence/003/20260910-storizon-published-2.2.6.md).
