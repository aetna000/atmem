# Context-provider adapters

AtMem normally owns governed retrieval. Context-provider adapters are an
optional deployment mode for teams that want Mem0, a LangGraph, or a Pydantic
AI agent to remain the context-decision authority while AtMem verifies and
delivers the exact result once and records the agent flight.

Installing or starting an adapter does not enable it. The safe sequence is:

1. install exactly one optional extra;
2. initialize and start its private loopback service;
3. register its public key and exact user, agent, and workspace scopes;
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
