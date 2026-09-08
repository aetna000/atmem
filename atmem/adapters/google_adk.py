"""Google Agent Development Kit callback binding."""
from atmem.adapters.callbacks import CallbackAtMemAdapter

def create_google_adk_adapter(manager, identity):
    return CallbackAtMemAdapter(manager, identity, framework="google-adk")

__all__ = ["create_google_adk_adapter"]
