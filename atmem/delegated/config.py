"""Private, explicit delegated-provider registration and activation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import stat
import tempfile
from typing import Any
from urllib.parse import urlparse

from atmem.delegated.canonical import public_key_fingerprint, strict_base64
from atmem.delegated.contracts import MAX_CONTEXT_BYTES


DEFAULT_CONFIG_PATH = Path.home() / ".atmem" / "delegated-context.json"


@dataclass(frozen=True, slots=True)
class DelegatedRegistration:
    provider_id: str
    provider_version: str
    provider_instance_id: str
    key_id: str
    public_key_base64: str
    endpoint: str
    workspace_ids: tuple[str, ...]
    agent_ids: tuple[str, ...]
    user_ids: tuple[str, ...]
    timeout_ms: int = 3000
    max_context_bytes: int = MAX_CONTEXT_BYTES
    enabled: bool = False
    native_fallback_on_failure: bool = False

    def __post_init__(self) -> None:
        _validate_registration(self)

    @property
    def registration_id(self) -> str:
        return f"{self.provider_id}:{self.provider_instance_id}"

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "DelegatedRegistration":
        expected = {
            "provider_id", "provider_version", "provider_instance_id", "key_id",
            "public_key_base64", "endpoint", "workspace_ids", "agent_ids", "user_ids",
            "timeout_ms", "max_context_bytes", "enabled", "native_fallback_on_failure",
        }
        if set(value) != expected:
            raise ValueError("delegated registration fields do not match the contract")
        registration = cls(
            provider_id=str(value["provider_id"]),
            provider_version=str(value["provider_version"]),
            provider_instance_id=str(value["provider_instance_id"]),
            key_id=str(value["key_id"]),
            public_key_base64=str(value["public_key_base64"]),
            endpoint=str(value["endpoint"]),
            workspace_ids=tuple(str(item) for item in value["workspace_ids"]),
            agent_ids=tuple(str(item) for item in value["agent_ids"]),
            user_ids=tuple(str(item) for item in value["user_ids"]),
            timeout_ms=int(value["timeout_ms"]),
            max_context_bytes=int(value["max_context_bytes"]),
            enabled=value["enabled"],
            native_fallback_on_failure=value["native_fallback_on_failure"],
        )
        _validate_registration(registration)
        return registration

    def safe_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("public_key_base64")
        value["workspace_ids"] = list(self.workspace_ids)
        value["agent_ids"] = list(self.agent_ids)
        value["user_ids"] = list(self.user_ids)
        value["registration_id"] = self.registration_id
        value["key_fingerprint"] = public_key_fingerprint(self.public_key_base64)
        return value


class DelegatedConfigStore:
    def __init__(self, path: str | Path | None = None) -> None:
        configured = path or os.environ.get("ATMEM_DELEGATED_CONFIG") or DEFAULT_CONFIG_PATH
        self.path = Path(configured).expanduser()

    def registrations(self) -> list[DelegatedRegistration]:
        if not self.path.exists():
            return []
        if self.path.is_symlink() or not stat.S_ISREG(self.path.stat().st_mode):
            raise ValueError("delegated configuration must be a regular file")
        if self.path.stat().st_mode & 0o077:
            raise ValueError("delegated configuration permissions must be 0600")
        value = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or set(value) != {"format", "registrations"} or value.get("format") != "atmem-delegated-context-config-v1":
            raise ValueError("unsupported delegated configuration")
        if not isinstance(value["registrations"], list):
            raise ValueError("delegated registrations must be a list")
        rows = [DelegatedRegistration.from_dict(row) for row in value["registrations"]]
        if len({row.registration_id for row in rows}) != len(rows):
            raise ValueError("duplicate delegated provider registration")
        return rows

    def register(self, registration: DelegatedRegistration, *, replace: bool = False) -> dict[str, Any]:
        _validate_registration(registration)
        if registration.enabled:
            raise ValueError("registration cannot enable delegated authority; enable it separately")
        rows = self.registrations()
        existing = [row for row in rows if row.registration_id == registration.registration_id]
        if existing and not replace:
            raise ValueError("delegated provider is already registered; use replace")
        rows = [row for row in rows if row.registration_id != registration.registration_id]
        rows.append(registration)
        self._write(rows)
        return registration.safe_dict()

    def set_enabled(self, registration_id: str, enabled: bool) -> dict[str, Any]:
        rows = self.registrations()
        changed: list[DelegatedRegistration] = []
        found = False
        for row in rows:
            if row.registration_id == registration_id:
                found = True
                row = DelegatedRegistration(**{**asdict(row), "enabled": bool(enabled)})
            changed.append(row)
        if not found:
            raise ValueError("delegated provider registration was not found")
        _reject_ambiguous_enabled(changed)
        self._write(changed)
        return next(row.safe_dict() for row in changed if row.registration_id == registration_id)

    def remove(self, registration_id: str) -> bool:
        rows = self.registrations()
        kept = [row for row in rows if row.registration_id != registration_id]
        if len(kept) == len(rows):
            return False
        self._write(kept)
        return True

    def match(self, *, workspace_id: str, agent_id: str, user_id: str | None) -> DelegatedRegistration | None:
        potential = [
            row for row in self.registrations()
            if row.enabled and workspace_id in row.workspace_ids and agent_id in row.agent_ids
        ]
        if not potential:
            return None
        if not user_id:
            raise ValueError("delegated context requires an authenticated user ID")
        matched = [row for row in potential if user_id in row.user_ids]
        if len(matched) > 1:
            raise ValueError("delegated provider scope is ambiguous")
        if not matched:
            raise ValueError("no delegated provider is trusted for this user")
        return matched[0]

    def has_enabled_for_agent(self, agent_id: str | None) -> bool:
        return bool(agent_id) and any(
            row.enabled and agent_id in row.agent_ids for row in self.registrations()
        )

    def status(self) -> dict[str, Any]:
        rows = self.registrations()
        enabled = [row for row in rows if row.enabled]
        return {
            "format": "atmem-delegated-context-status-v1",
            "authority_default": "atmem",
            "delegated_mode_default": False,
            "configured": bool(rows),
            "enabled": bool(enabled),
            "registrations": [row.safe_dict() for row in rows],
            "config_path": str(self.path),
            "next_action": (
                "Register a trusted provider; native AtMem authority remains active."
                if not rows else
                "Delegated authority is enabled for matching scopes."
                if enabled else
                "Run `atmem delegated enable REGISTRATION_ID` to opt in."
            ),
        }

    def _write(self, rows: list[DelegatedRegistration]) -> None:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.path.parent.is_symlink() or self.path.is_symlink():
            raise ValueError("delegated configuration path cannot be a symlink")
        if not stat.S_ISDIR(self.path.parent.stat().st_mode):
            raise ValueError("delegated configuration parent must be a directory")
        value = {
            "format": "atmem-delegated-context-config-v1",
            "registrations": [
                {**asdict(row), "workspace_ids": list(row.workspace_ids), "agent_ids": list(row.agent_ids), "user_ids": list(row.user_ids)}
                for row in rows
            ],
        }
        descriptor, temporary = tempfile.mkstemp(prefix=".delegated-context.", suffix=".tmp", dir=self.path.parent)
        temporary_path = Path(temporary)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(value, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self.path)
            os.chmod(self.path, 0o600)
        finally:
            temporary_path.unlink(missing_ok=True)


def _validate_registration(row: DelegatedRegistration) -> None:
    for value in (row.provider_id, row.provider_version, row.provider_instance_id, row.key_id):
        if not value or value != value.strip() or len(value) > 256:
            raise ValueError("invalid delegated provider identifier")
    strict_base64(row.public_key_base64, expected_length=32)
    parsed = urlparse(row.endpoint)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "::1"} or parsed.username or parsed.password:
        raise ValueError("delegated beta endpoints must use loopback HTTP")
    if not parsed.port:
        raise ValueError("delegated endpoint requires an explicit loopback port")
    if not 100 <= row.timeout_ms <= 30_000:
        raise ValueError("delegated timeout must be between 100 and 30000 ms")
    if not 1 <= row.max_context_bytes <= MAX_CONTEXT_BYTES:
        raise ValueError("delegated context limit is outside the contract")
    if not isinstance(row.enabled, bool) or not isinstance(row.native_fallback_on_failure, bool):
        raise ValueError("delegated mode flags must be boolean")
    for values in (row.workspace_ids, row.agent_ids, row.user_ids):
        if not values or len(values) > 64 or "*" in values or len(set(values)) != len(values):
            raise ValueError("delegated beta scopes must be explicit and unique")
        if any(not item or item != item.strip() or len(item) > 256 for item in values):
            raise ValueError("invalid delegated scope identifier")


def _reject_ambiguous_enabled(rows: list[DelegatedRegistration]) -> None:
    enabled = [row for row in rows if row.enabled]
    for index, left in enumerate(enabled):
        for right in enabled[index + 1:]:
            if set(left.workspace_ids) & set(right.workspace_ids) and set(left.agent_ids) & set(right.agent_ids) and set(left.user_ids) & set(right.user_ids):
                raise ValueError("enabled delegated provider scopes overlap")
