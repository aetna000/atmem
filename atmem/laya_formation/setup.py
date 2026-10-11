"""Explicit, reversible setup state for the optional Laya formation profile."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Callable

from atmem.home.layout import compatible_home_path

from .artifacts import LayaArtifactResolver, MODEL_REPO, MODEL_REVISION, dependency_status
from .runtime import LayaDecisionEngine, select_device


DEFAULT_ROOT = compatible_home_path("config/laya-formation", "laya-formation")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _write_private(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        temporary.chmod(0o600)
    except OSError:
        pass
    temporary.replace(path)


class LayaProfileManager:
    def __init__(
        self,
        root: str | Path = DEFAULT_ROOT,
        *,
        resolver: Any | None = None,
        engine_factory: Callable[..., Any] = LayaDecisionEngine,
        dependency_probe: Callable[[], dict[str, Any]] = dependency_status,
    ) -> None:
        self.root = Path(root).expanduser()
        self.config_path = self.root / "profile.json"
        self.rollback_path = self.root / "rollback.json"
        self.resolver = resolver or LayaArtifactResolver()
        self.engine_factory = engine_factory
        self.dependency_probe = dependency_probe

    def _read(self) -> dict[str, Any] | None:
        if not self.config_path.is_file():
            return None
        value = json.loads(self.config_path.read_text(encoding="utf-8"))
        if value.get("format") != "atmem-laya-formation-profile-v1":
            raise ValueError("unsupported Laya formation profile state")
        return value

    def preview(
        self, *, local_dir: str | Path | None = None, device: str = "auto",
        escalation_enabled: bool = False, allow_download: bool = False,
    ) -> dict[str, Any]:
        selected = select_device(device)
        return {
            "format": "atmem-laya-formation-profile-preview-v1",
            "current": self.status(),
            "changes": {
                "profile": "laya-formation-v1", "active": False,
                "model_repo": MODEL_REPO, "model_revision": MODEL_REVISION,
                "model_dir": str(Path(local_dir).expanduser().resolve()) if local_dir else None,
                "download_requested": bool(allow_download), "device": selected,
                "escalation_enabled": bool(escalation_enabled),
                "default_behavior_changes": False,
            },
            "activation_required": True,
        }

    def setup(
        self, *, local_dir: str | Path | None = None, allow_download: bool = False,
        device: str = "auto", escalation_enabled: bool = False,
    ) -> dict[str, Any]:
        selected = select_device(device)
        bundle = self.resolver.resolve(
            local_dir=Path(local_dir).expanduser() if local_dir is not None else None,
            allow_download=bool(allow_download), token=None,
        )
        dependencies = self.dependency_probe()
        value = {
            "format": "atmem-laya-formation-profile-v1",
            "profile": "laya-formation-v1", "active": False, "verified": True,
            "model_repo": bundle.repo_id, "model_revision": bundle.revision,
            "model_sha256": bundle.model_sha256,
            "questions_digest": bundle.questions_digest,
            "calibration_digest": bundle.calibration_digest,
            "export_digest": bundle.export_digest,
            "model_dir": str(bundle.root.resolve()), "device": selected,
            "calibration_state": "verified", "fallback_ready": True,
            "escalation": {
                "enabled": bool(escalation_enabled), "max_calls": 1,
                "max_input_tokens": 2048, "max_output_tokens": 128,
                "timeout_seconds": 15.0, "retries": 0,
                "remote_egress_allowed": False, "max_cost_usd": 0.0,
            },
            "runtime_dependencies_available": bool(dependencies.get("available")),
            "updated_at": _now(),
        }
        _write_private(self.config_path, value)
        return dict(value)

    def activate(self, *, confirmed: bool) -> dict[str, Any]:
        if not confirmed:
            raise ValueError("explicit confirmation is required to activate the Laya profile")
        current = self._read()
        if current is None:
            raise ValueError("run Laya formation setup before activation")
        dependencies = self.dependency_probe()
        if not dependencies.get("available"):
            raise RuntimeError("install atmem[laya-formation] before activation")
        bundle = self.resolver.verify(Path(current["model_dir"]))
        engine = self.engine_factory(bundle, device=current["device"])
        try:
            actual_device = str(getattr(engine, "device", current["device"]))
        finally:
            close = getattr(engine, "close", None)
            if callable(close):
                close()
        _write_private(self.rollback_path, {"format": "atmem-laya-formation-rollback-v1", "previous": current})
        active = {**current, "active": True, "device": actual_device, "activated_at": _now(), "updated_at": _now()}
        _write_private(self.config_path, active)
        return active

    def rollback(self, *, confirmed: bool) -> dict[str, Any]:
        if not confirmed:
            raise ValueError("explicit confirmation is required to roll back the Laya profile")
        if not self.rollback_path.is_file():
            raise ValueError("no Laya profile activation rollback is available")
        record = json.loads(self.rollback_path.read_text(encoding="utf-8"))
        previous = record.get("previous")
        if not isinstance(previous, dict):
            raise ValueError("Laya profile rollback record is invalid")
        _write_private(self.config_path, previous)
        self.rollback_path.unlink(missing_ok=True)
        return dict(previous)

    def status(self) -> dict[str, Any]:
        value = self._read()
        if value is None:
            return {
                "format": "atmem-laya-formation-profile-status-v1",
                "configured": False, "active": False, "profile": "deterministic",
                "model_repo": MODEL_REPO, "model_revision": MODEL_REVISION,
                "device": None, "calibration_state": "not_configured",
                "fallback_ready": True, "escalation_enabled": False,
                "setup_action": "Install the optional extra, then run `atmem formation setup`.",
            }
        return {
            "format": "atmem-laya-formation-profile-status-v1",
            "configured": True, "active": bool(value.get("active")),
            "profile": value.get("profile"), "model_repo": value.get("model_repo"),
            "model_revision": value.get("model_revision"), "model_sha256": value.get("model_sha256"),
            "questions_digest": value.get("questions_digest"),
            "calibration_digest": value.get("calibration_digest"),
            "device": value.get("device"), "calibration_state": value.get("calibration_state"),
            "fallback_ready": bool(value.get("fallback_ready")),
            "escalation_enabled": bool((value.get("escalation") or {}).get("enabled")),
            "runtime_dependencies_available": bool(value.get("runtime_dependencies_available")),
            "rollback_available": self.rollback_path.is_file(),
        }

    def doctor(self) -> dict[str, Any]:
        status = self.status()
        checks: dict[str, bool] = {
            "configured": bool(status["configured"]),
            "fallback_ready": bool(status["fallback_ready"]),
            "dependencies": bool(self.dependency_probe().get("available")),
            "artifact": False,
        }
        error_code = None
        value = self._read()
        if value is not None:
            try:
                bundle = self.resolver.verify(Path(value["model_dir"]))
                checks["artifact"] = (
                    bundle.revision == value["model_revision"]
                    and bundle.calibration_digest == value["calibration_digest"]
                )
            except (OSError, KeyError, TypeError, ValueError, RuntimeError):
                error_code = "artifact_verification_failed"
        ready = all(checks.values())
        return {
            "format": "atmem-laya-formation-doctor-v1", "status": status,
            "checks": checks, "ready_to_activate": ready,
            "active_healthy": ready and bool(status.get("active")),
            "calibration_state": "verified" if checks["artifact"] else "unverified",
            "fallback_ready": checks["fallback_ready"], "error_code": error_code,
        }
