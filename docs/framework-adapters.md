# Pydantic AI and LangGraph adapters

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
)
```

The identity must match the topology registered in AtMem. A mismatch fails
closed before memory content is returned.

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

## Security and fallback behavior

- AtMem authorizes before any candidate content reaches AtBot or a framework.
- Adapters inject context only when `inject` is exactly `true`.
- Retrieved memory is added as data, never promoted into the standing system
  prompt.
- Exposure is confirmed at the model boundary, not when retrieval merely runs.
- Shadow mode never injects or confirms exposure.
- AtBot failure falls back to AtMem's deterministic capture and hybrid ranking.
- MCP remains available as a tool-only fallback, but cannot by itself prove
  automatic model-boundary injection.
