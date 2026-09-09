"""Microsoft Agent Framework callback binding."""
from atmem.adapters.callbacks import CallbackAtMemAdapter

def create_microsoft_agent_adapter(manager, identity):
    return CallbackAtMemAdapter(manager, identity, framework="microsoft-agent-framework")

__all__ = ["create_microsoft_agent_adapter"]
