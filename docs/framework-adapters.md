# Pydantic AI and LangGraph adapters

> AtMem 2.2.6b11 packages delegated exact-delivery support for Pydantic AI and
> LangChain/LangGraph as well as OpenClaw. Delegation remains opt-in and requires
> an enabled registration matching the authenticated scope.

AtMem's framework adapters make capture, retrieval, injection, exposure proof,
and lifecycle evidence automatic. They call AtMem directly and never call
AtBot. AtBot remains AtMem's private inference and ranking component.

Both adapters preserve the framework's own conversation history, checkpoints,
workflow state, tools, and model selection. AtMem supplies only governed
cross-session memory and content-minimizing evidence.

## Install

Choose one framework or install both:

```bash
python -m pip install 'atmem[pydantic-ai]'
python -m pip install 'atmem[langgraph]'
python -m pip install 'atmem[frameworks]'
```

Initialize the generic control plane and register persistent agents before
running an adapter. Shadow mode captures and prepares previews but never injects
memory. Activate AtMem only after reviewing the dashboard:

```bash
atmem control shadow --host generic --memory-db ~/.atmem/memory.db
atmem dashboard
```

## Identity boundary

Every adapter instance needs an authenticated persistent identity. Session,
run, and turn IDs correlate evidence but never grant access:

```python
from atmem.adapters import AtMemAdapterIdentity

identity = AtMemAdapterIdentity(
    subject_id="customer-42",
    agent_id="support-agent",
    workspace_id="ws_support",
    session_id="conversation-17",
    user_id="authenticated-customer-42",
)
```

The identity must match the topology registered in AtMem. A mismatch fails
closed before memory content is returned. `subject_id` selects native AtMem
memory; `user_id` is a distinct authenticated application principal used for
delegated-provider scope. Never derive it from prompt text, model output, or a
tool argument.

For applications whose principal changes per run, supply
`atmem_authenticated_user_id` through Pydantic AI dependencies or LangGraph's
trusted runtime context/configurable values. The adapters intentionally ignore a
generic `user_id` field. They also accept per-run `atmem_session_id` and
`atmem_turn_id`. These values are read without modifying framework state.

## Pydantic AI

Pydantic AI 2.x exposes native run, model-request, and tool-execution hooks.
Add AtMem's capability to the agent:

```python
from pydantic_ai import Agent

from atmem.adapters.pydantic_ai import PydanticAIAtMemAdapter
from atmem.control import ControlPlaneManager

manager = ControlPlaneManager()
memory = PydanticAIAtMemAdapter(manager, identity).capability()

agent = Agent(
    "openai:gpt-5-mini",
    capabilities=[memory],
)

result = agent.run_sync("What drink do I prefer?")
```

The capability captures the authenticated prompt once, prepares memory before
the model boundary, appends authorized memory as a user-data message, confirms
the exact exposure, and records model/tool completion or failure. It does not
modify the agent's dependencies or stored message history.

When an AtMem delegated-provider registration is enabled and matches the full
workspace/agent/user scope, this same capability becomes the host delivery path:
AtMem sends an HMAC-authenticated request containing the exact prompt, verifies
the provider's signed decision, and appends an authorized `inject` as exactly one
unchanged `UserPromptPart`. `withhold` and fail-closed outcomes append nothing.

## LangGraph and LangChain

LangChain agents run on LangGraph and expose the model/tool lifecycle through
`AgentMiddleware`:

```python
from langchain.agents import create_agent

from atmem.adapters.langgraph import create_langgraph_middleware
from atmem.control import ControlPlaneManager

manager = ControlPlaneManager()
memory = create_langgraph_middleware(manager, identity)

agent = create_agent(
    model="openai:gpt-5-mini",
    tools=[...],
    middleware=[memory],
)

result = agent.invoke({
    "messages": [{"role": "user", "content": "What drink do I prefer?"}]
})
```

The middleware uses `before_agent`, sync/async model wrappers, sync/async tool
wrappers, and `after_agent`. It does not replace LangGraph state, checkpointing,
or its cross-thread store. Raw low-level `StateGraph` applications can use
`AtMemTurnLifecycle` from `atmem.adapters` around their existing entry, model,
tool, and terminal nodes; this is the same conformance-tested lifecycle used by
both packaged adapters.

Matching delegated authority uses one unchanged `HumanMessage` at the sync or
async model wrapper. Immediately before invoking the model handler, the
middleware proves that the accepted bytes occur as exactly one complete message
segment. It then confirms delivery and erases the transient context. The
middleware never takes ownership of state, checkpoints, tools, or model calls.

## Security and fallback behavior

- AtMem authorizes before any candidate content reaches AtBot or a framework.
- Adapters inject context only when `inject` is exactly `true`.
- Retrieved memory is added as data, never promoted into the standing system
  prompt.
- Exposure is confirmed at the model boundary, not when retrieval merely runs.
- Delegated provider authorization and host delivery are separate Black Box
  events; neither claims that the model used the context.
- A matching delegated turn is not captured into AtMem canonical memory. A
  nonmatching scope continues through normal native capture and retrieval.
- Delegated failures with the default policy inject nothing. Native fallback is
  possible only when explicitly configured on the provider registration and is
  labeled `atmem_fallback`.
- Shadow mode never injects or confirms exposure.
- AtBot failure falls back to AtMem's deterministic capture and hybrid ranking.
- MCP remains available as a tool-only fallback, but cannot by itself prove
  automatic model-boundary injection.

## Expanded callback adapters (Spec 011)

OpenAI Agents, Microsoft Agent Framework, Google ADK, smolagents and CrewAI use the shared `CallbackAtMemAdapter` boundary. Install only the matching optional extra. The runtime `capabilities()` response is authoritative, and every exact-injection claim is checked by the common conformance suite. MCP remains a tool-only fallback: it cannot prove exact model-boundary placement or complete tool/terminal coverage.
