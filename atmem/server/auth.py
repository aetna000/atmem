"""Scoped, hashed service keys with overlap-safe rotation."""
from __future__ import annotations
import hashlib, hmac, secrets, time, uuid
from dataclasses import dataclass

ROLES = {"reader": {"read"}, "writer": {"read", "write"}, "operator": {"read", "write", "operate"}, "admin": {"read", "write", "operate", "admin"}}

@dataclass(frozen=True, slots=True)
class Principal:
    principal_id: str; tenant_id: str; user_id: str | None; role: str; scopes: tuple[str, ...]
    def permits(self, operation: str, scope: str) -> bool:
        return operation in ROLES.get(self.role, set()) and ("*" in self.scopes or scope in self.scopes)

@dataclass(slots=True)
class _Key:
    key_id: str; digest: bytes; principal: Principal; expires_at: float; revoked: bool = False

class KeyAuthority:
    def __init__(self) -> None: self._keys: dict[str, _Key] = {}
    def issue(self, principal: Principal, *, ttl_seconds: int = 3600) -> tuple[str, str]:
        if principal.role not in ROLES or ttl_seconds <= 0: raise ValueError("valid role and positive ttl required")
        key_id, secret = f"key_{uuid.uuid4().hex}", secrets.token_urlsafe(32)
        self._keys[key_id] = _Key(key_id, hashlib.sha256(secret.encode()).digest(), principal, time.time() + ttl_seconds)
        return key_id, secret
    def authenticate(self, key_id: str, secret: str) -> Principal:
        key = self._keys.get(key_id)
        if key is None or key.revoked or key.expires_at <= time.time() or not hmac.compare_digest(key.digest, hashlib.sha256(secret.encode()).digest()):
            raise PermissionError("invalid, expired, or revoked credential")
        return key.principal
    def rotate(self, key_id: str, *, overlap_seconds: int = 300, ttl_seconds: int = 3600) -> tuple[str, str]:
        old = self._keys.get(key_id)
        if old is None or old.revoked: raise PermissionError("credential cannot be rotated")
        old.expires_at = min(old.expires_at, time.time() + max(0, overlap_seconds))
        return self.issue(old.principal, ttl_seconds=ttl_seconds)
    def revoke(self, key_id: str) -> None:
        if key_id not in self._keys: raise KeyError(key_id)
        self._keys[key_id].revoked = True
