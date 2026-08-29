from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any

from atmem.core.canonical import canonical_json, sha256_hex


STATE_FORMAT = "atmem-control-plane-state-v1"


class ControlMode(str, Enum):
    OFF = "off"
    SHADOW = "shadow"
    ACTIVE = "active"

    @property
    def captures(self) -> bool:
        return self is not ControlMode.OFF

    @property
    def influences_agent(self) -> bool:
        return self is ControlMode.ACTIVE


class ProviderState(str, Enum):
    """Single derived answer to "which memory provider is in charge right now".

    Every status surface (dashboard chip, banner, hero, switch control) must
    render from this one value instead of re-deriving state from mode,
    takeover, or readiness fragments.
    """

    UNAVAILABLE = "unavailable"
    RESTORE_REQUIRED = "restore_required"
    ACTIVE = "active"
    READY = "ready"
    SHADOW = "shadow"
    OFF = "off"


def derive_provider_state(
    *,
    mode: ControlMode,
    host: str,
    takeover: dict[str, Any] | None,
    readiness: dict[str, Any] | None,
    warning: str | None,
    migration_id: str,
) -> ProviderState:
    """Derive the one provider state from the authoritative status inputs.

    Precedence: fail-closed unavailability, then an interrupted or verified
    OpenClaw cutover (a state file claiming ACTIVE without a verified cutover
    requires restore), then generic ACTIVE, then OFF, then shadow readiness.
    """
    if warning or migration_id == "unavailable":
        return ProviderState.UNAVAILABLE
    if host == "openclaw":
        cutover = takeover or {}
        if cutover.get("requires_restore"):
            return ProviderState.RESTORE_REQUIRED
        if cutover.get("active"):
            return ProviderState.ACTIVE
        if mode is ControlMode.ACTIVE:
            return ProviderState.RESTORE_REQUIRED
    elif mode is ControlMode.ACTIVE:
        return ProviderState.ACTIVE
    if mode is ControlMode.OFF:
        return ProviderState.OFF
    if (readiness or {}).get("ready_for_active"):
        return ProviderState.READY
    return ProviderState.SHADOW


@dataclass(frozen=True)
class ControlState:
    migration_id: str
    host: str
    subject_id: str
    control_dir: str
    mode: ControlMode
    revision: int
    created_at: str
    updated_at: str
    format: str = STATE_FORMAT
    state_sha256: str = ""

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "format": self.format,
            "migration_id": self.migration_id,
            "host": self.host,
            "subject_id": self.subject_id,
            "control_dir": self.control_dir,
            "mode": self.mode.value,
            "revision": self.revision,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @property
    def digest(self) -> str:
        return sha256_hex(canonical_json(self.unsigned_dict()))

    def to_dict(self) -> dict[str, Any]:
        return {**self.unsigned_dict(), "state_sha256": self.digest}

    def with_digest(self) -> "ControlState":
        return replace(self, state_sha256=self.digest)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ControlState":
        if value.get("format") != STATE_FORMAT:
            raise ValueError(f"unsupported migration state format: {value.get('format')!r}")
        try:
            state = cls(
                migration_id=str(value["migration_id"]),
                host=str(value["host"]),
                subject_id=str(value["subject_id"]),
                control_dir=str(value["control_dir"]),
                mode=ControlMode(str(value["mode"])),
                revision=int(value["revision"]),
                created_at=str(value["created_at"]),
                updated_at=str(value["updated_at"]),
                state_sha256=str(value.get("state_sha256") or ""),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("malformed migration state") from exc
        if not state.migration_id or not state.subject_id or state.revision < 0:
            raise ValueError("invalid migration state identity or revision")
        if state.state_sha256 != state.digest:
            raise ValueError("migration state digest mismatch")
        return state

    def public_status(self, *, warning: str | None = None) -> dict[str, Any]:
        return {
            **self.to_dict(),
            "writes_local_data": self.mode.captures,
            "changes_model_context": self.mode.influences_agent,
            "makes_extra_provider_calls": False,
            "warning": warning,
        }


def fail_closed_state(path: str, *, warning: str) -> ControlState:
    """Return a non-persistent OFF state for a missing or corrupt state file."""
    return ControlState(
        migration_id="unavailable",
        host="unknown",
        subject_id="unknown",
        control_dir=str(path),
        mode=ControlMode.OFF,
        revision=0,
        created_at="",
        updated_at="",
    ).with_digest()
