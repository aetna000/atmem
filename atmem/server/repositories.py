"""Scope-bound repository facade that rejects cross-tenant access."""
from __future__ import annotations
from typing import Any
from atmem.server.auth import Principal

class ScopedRepository:
    def __init__(self, store: Any, principal: Principal) -> None: self.store, self.principal = store, principal
    def require(self, operation: str, tenant_id: str, scope: str) -> None:
        if tenant_id != self.principal.tenant_id or not self.principal.permits(operation, scope): raise PermissionError("cross-tenant or unauthorized access")
    def get(self, record_id: str, *, tenant_id: str, scope: str): self.require("read", tenant_id, scope); return self.store.get(record_id)
    def put(self, record, *, tenant_id: str, scope: str): self.require("write", tenant_id, scope); return self.store.put(record)
