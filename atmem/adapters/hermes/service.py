"""Scoped Hermes operations over the existing encrypted control store."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import time
from typing import Any
import uuid

from atmem.adapters.base import AtMemAdapterIdentity
from atmem.evidence.crypto import open_json, seal_json
from atmem.locking import ProcessFileLock
from atmem.service import APIError, APIPrincipal

from .binding import HermesMemoryBinding, _identifier


class HermesService:
    """Transport never accepts caller-selected scope or a shared dashboard token.

    Bindings use the existing encrypted identity-key custody, separately from
    the execution store so a slow model call cannot lock out revocation.
    """

    def __init__(self, manager: Any):
        self.manager = manager

    @contextmanager
    def _locked(self):
        state = self.manager.state()
        lock = ProcessFileLock(Path(state.control_dir) / ".hermes.lock")
        deadline = time.monotonic() + 2.0
        while True:
            try:
                lock.acquire()
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Hermes authority is busy; retry the operation") from None
                time.sleep(0.01)
        try:
            yield
        finally:
            lock.close()

    def _records(self) -> dict[str, Any]:
        vault = self.manager.evidence_service()
        vault.storage_key()  # Locked evidence also locks adapter authority.
        path = Path(self.manager.state().control_dir) / "hermes-bindings.enc.json"
        if not path.exists():
            return {}
        wrapper = json.loads(path.read_text(encoding="utf-8"))
        if wrapper.get("format") != "atmem-hermes-bindings-encrypted-v1":
            raise ValueError("unsupported Hermes authority format")
        return open_json(vault.accounts.key, "atmem-hermes-bindings-v1",
                         base64.b64decode(wrapper["nonce"], validate=True),
                         base64.b64decode(wrapper["ciphertext"], validate=True))

    def _load(self, binding_id: str) -> dict[str, Any]:
        row = self._records().get(binding_id)
        if row is None:
            raise APIError("unauthenticated", "Hermes credential is invalid or revoked", status=401)
        return row

    def _save(self, row: dict[str, Any]) -> None:
        records = self._records()
        records[row["binding_id"]] = row
        vault = self.manager.evidence_service()
        vault.storage_key()
        nonce, ciphertext = seal_json(vault.accounts.key, "atmem-hermes-bindings-v1", records)
        path = Path(self.manager.state().control_dir) / "hermes-bindings.enc.json"
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump({"format": "atmem-hermes-bindings-encrypted-v1",
                           "nonce": base64.b64encode(nonce).decode(),
                           "ciphertext": base64.b64encode(ciphertext).decode()}, handle)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            if os.name != "nt":
                directory = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _admin(principal: APIPrincipal) -> None:
        principal.require("config:write")
        if principal.tenant_id != "local":
            raise PermissionError("Hermes currently supports local tenant bindings only")

    @staticmethod
    def _owner(principal: APIPrincipal, row: dict[str, Any]) -> None:
        identity = row["identity"]
        if (identity["subject_id"] != principal.subject_id or
                (principal.workspace_id and principal.workspace_id != identity["workspace_id"])):
            raise PermissionError("binding is outside the administrator scope")

    @staticmethod
    def _public(row: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in row.items() if key != "token_digest"}

    def _binding(self, row: dict[str, Any]) -> HermesMemoryBinding:
        return HermesMemoryBinding(
            self.manager, AtMemAdapterIdentity(**row["identity"]),
            profile_id=row["profile_id"], enabled=row["enabled"],
            max_context_chars=row["max_context_chars"],
        )

    def provision(self, principal: APIPrincipal, *, profile_id: str,
                  agent_id: str, workspace_id: str, user_id: str | None = None,
                  accept_reduced_capture: bool = False) -> dict[str, Any]:
        self._admin(principal)
        if accept_reduced_capture is not True:
            raise ValueError("this Hermes profile requires explicit acceptance of memory-only capture")
        profile_id = _identifier(profile_id, "profile_id")
        identity = AtMemAdapterIdentity(
            agent_id=_identifier(agent_id, "agent_id"),
            workspace_id=_identifier(workspace_id, "workspace_id"),
            subject_id=principal.subject_id,
            user_id=_identifier(user_id, "user_id") if user_id is not None else None,
            framework="hermes",
        )
        self._owner(principal, {"identity": asdict(identity)})
        with self._locked():
            self._binding({"identity": asdict(identity), "profile_id": profile_id,
                           "enabled": False, "max_context_chars": 4096})._scope()
            rows = list(self._records().values())
            existing = any(row["profile_id"] == profile_id for row in rows)
            if existing:
                raise APIError("conflict", "profile already has a binding; inspect or rotate it", status=409)
            if any(row["identity"]["subject_id"] == identity.subject_id for row in rows):
                raise APIError("conflict", "use a distinct authorized subject/workspace or rotate that subject's existing binding", status=409)
            binding_id = uuid.uuid4().hex
            token = "hermes_" + binding_id + "." + secrets.token_urlsafe(32)
            row = {
                "format": "atmem-hermes-binding-v1", "binding_id": binding_id,
                "profile_id": profile_id, "identity": asdict(identity),
                "token_digest": hashlib.sha256(token.encode()).hexdigest(),
                "generation": 1, "enabled": False, "revoked": False,
                "expires_at": int(time.time()) + 90 * 86400,
                "max_context_chars": 4096, "capture_coverage": "memory_operations_only",
                "reconstructable": False, "reduced_capture_accepted": True,
            }
            self._save(row)
            return {"binding": self._public(row), "credential": token}

    def configure(self, principal: APIPrincipal, binding_id: str, *, enabled: bool) -> dict[str, Any]:
        self._admin(principal)
        if not isinstance(enabled, bool):
            raise ValueError("enabled must be a boolean")
        with self._locked():
            row = self._load(_identifier(binding_id, "binding_id"))
            self._owner(principal, row)
            if row["revoked"] or row["expires_at"] <= time.time():
                raise PermissionError("rotate the revoked or expired binding before activation")
            self._binding(row)._scope()
            if row["enabled"] != enabled:
                row["generation"] += 1
            row["enabled"] = enabled
            self._save(row)
            return self._public(row)

    def revoke(self, principal: APIPrincipal, binding_id: str) -> dict[str, Any]:
        self._admin(principal)
        with self._locked():
            row = self._load(_identifier(binding_id, "binding_id"))
            self._owner(principal, row)
            row.update(revoked=True, enabled=False)
            self._save(row)
            return self._public(row)

    def rotate(self, principal: APIPrincipal, binding_id: str) -> dict[str, Any]:
        self._admin(principal)
        with self._locked():
            row = self._load(_identifier(binding_id, "binding_id"))
            self._owner(principal, row)
            self._binding(row)._scope()
            token = "hermes_" + row["binding_id"] + "." + secrets.token_urlsafe(32)
            row.update(token_digest=hashlib.sha256(token.encode()).hexdigest(),
                       generation=row["generation"] + 1, revoked=False, enabled=False,
                       expires_at=int(time.time()) + 90 * 86400)
            self._save(row)
            return {"binding": self._public(row), "credential": token}

    def list_bindings(self, principal: APIPrincipal) -> list[dict[str, Any]]:
        self._admin(principal)
        with self._locked():
            rows = sorted(self._records().values(), key=lambda row: row["profile_id"])
            return [self._public(row) for row in rows
                    if row["identity"]["subject_id"] == principal.subject_id and
                    (not principal.workspace_id or row["identity"]["workspace_id"] == principal.workspace_id)]

    def _authenticate(self, token: str) -> dict[str, Any]:
        if not isinstance(token, str) or len(token) > 256 or not token.startswith("hermes_"):
            raise APIError("unauthenticated", "Hermes credential is invalid or revoked", status=401)
        binding_id, separator, _ = token[7:].partition(".")
        if not separator or len(binding_id) != 32:
            raise APIError("unauthenticated", "Hermes credential is invalid or revoked", status=401)
        row = self._load(binding_id)
        if (row["revoked"] or row["expires_at"] <= time.time() or not secrets.compare_digest(
                row["token_digest"], hashlib.sha256(token.encode()).hexdigest())):
            raise APIError("unauthenticated", "Hermes credential is invalid or revoked", status=401)
        return row

    def dispatch(self, token: str, operation: str, body: dict[str, Any]) -> dict[str, Any]:
        allowed = {"status": set(), "recall": {"query", "session_id", "turn_id"},
                   "observe": {"text", "session_id", "observation_id"}}
        if operation not in allowed:
            raise APIError("not_found", "unknown Hermes operation", status=404)
        if set(body) != allowed[operation]:
            raise ValueError("unexpected or missing fields; scope comes from the credential")
        with self._locked():
            row = self._authenticate(token)
            binding = self._binding(row)
            binding._scope()
            if operation == "status":
                return {**binding.status(), "binding_id": row["binding_id"],
                        "generation": row["generation"], "expires_at": row["expires_at"],
                        "reconstructable": False}
            if not binding.enabled:
                raise APIError("inactive", "Hermes memory is not activated", status=403)
        # Slow retrieval/extraction cannot lock out an administrator's revoke.
        # A previously accepted write may finish, but no new call is accepted
        # after revocation; recall is rechecked before releasing its result.
        value = (asdict(binding.recall(**body)) if operation == "recall"
                 else binding.observe_user(**body))
        try:
            with self._locked():
                current = self._authenticate(token)
                if not current["enabled"] or current["generation"] != row["generation"]:
                    raise APIError("inactive", "Hermes binding changed during the operation", status=403)
                self._binding(current)._scope()
        except Exception:
            if operation == "observe":
                raise APIError("observation_uncertain", "an accepted write may have completed before revocation; inspect its receipt", status=409) from None
            raise
        if "error" in value:
            raise APIError("observation_uncertain", "inspect the observation outcome before retrying", status=409)
        return value
