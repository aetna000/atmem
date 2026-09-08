"""CrewAI callback binding."""
from atmem.adapters.callbacks import CallbackAtMemAdapter

def create_crewai_adapter(manager, identity):
    return CallbackAtMemAdapter(manager, identity, framework="crewai")

__all__ = ["create_crewai_adapter"]
