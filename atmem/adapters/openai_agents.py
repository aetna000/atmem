"""OpenAI Agents SDK callback binding (the SDK remains an optional extra)."""
from atmem.adapters.callbacks import CallbackAtMemAdapter

def create_openai_agents_adapter(manager, identity):
    return CallbackAtMemAdapter(manager, identity, framework="openai-agents")

__all__ = ["create_openai_agents_adapter"]
