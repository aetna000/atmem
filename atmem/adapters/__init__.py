"""Optional framework adapters for automatic governed memory lifecycle hooks."""

from atmem.adapters.base import AtMemAdapterIdentity, AtMemTurnLifecycle
from atmem.adapters.callbacks import CallbackAtMemAdapter, callback_adapter

__all__ = ["AtMemAdapterIdentity", "AtMemTurnLifecycle", "CallbackAtMemAdapter", "callback_adapter"]
