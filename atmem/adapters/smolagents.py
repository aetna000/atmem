"""Hugging Face smolagents callback binding."""
from atmem.adapters.callbacks import CallbackAtMemAdapter

def create_smolagents_adapter(manager, identity):
    return CallbackAtMemAdapter(manager, identity, framework="smolagents")

__all__ = ["create_smolagents_adapter"]
