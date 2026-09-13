"""Portable home manifest, inspection, adoption and migration services."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import socket
import tempfile
import uuid
from typing import Any

from atmem.home.layout import DIRECTORIES, HomeLayout
from atmem.store.sqlite import utc_now


MANIFEST_FORMAT = "atmem-home-manifest-v1"
LAYOUT_VERSION = 1


def _digest_path(path: Path) -> tuple[str, int, int]:
    digest = sha256()
    files = 0
    byte_count = 0
    candidates = [path] if path.is_file() else sorted(item for item in path.rglob("*") if item.is_file())
    for candidate in candidates:
        if candidate.is_symlink():
            raise ValueError("legacy migration refuses symbolic links")
        relative = candidate.name if path.is_file() else str(candidate.relative_to(path))
        digest.update(sha256(relative.encode("utf-8")).digest())
        with candidate.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                byte_count += len(chunk)
        files += 1
    return digest.hexdigest(), files, byte_count


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except (OSError, PermissionError):
        return False
    return True


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


class HomeService:
    def __init__(self, root: str | Path | None = None) -> None:
        self.layout = HomeLayout.selected(root)

    def initialize(self) -> dict[str, Any]:
        self.layout.initialize_directories()
        if self.layout.manifest.exists():
            return self.manifest()
        now = utc_now()
        value = {
            "format": MANIFEST_FORMAT,
            "layout_version": LAYOUT_VERSION,
            "atmem_compatibility": {"minimum": "2.3.0", "maximum_major": 2},
            "instance_id": f"home_{uuid.uuid4().hex}",
            "created_at": now,
            "updated_at": now,
            "capture_mode": "full",
            "inventory": {name: {"present": True} for name in DIRECTORIES},
        }
        _atomic_json(self.layout.manifest, value)
        return value

    def manifest(self) -> dict[str, Any]:
        value = json.loads(self.layout.manifest.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("format") != MANIFEST_FORMAT:
            raise ValueError("unsupported AtMem Home manifest")
        if int(value.get("layout_version") or 0) != LAYOUT_VERSION:
            raise ValueError("AtMem Home layout is not compatible with this AtMem version")
        return value

    def status(self) -> dict[str, Any]:
        exists = self.layout.root.is_dir()
        manifest = None
        warning = None
        if exists and self.layout.manifest.is_file():
            try:
                manifest = self.manifest()
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                warning = str(exc)
        elif exists:
            warning = "legacy AtMem layout: run `atmem home migrate` to create a portable generation"
        return {
            "format": "atmem-home-status-v1",
            "home": str(self.layout.root),
            "exists": exists,
            "portable": manifest is not None,
            "read_only": not os.access(self.layout.root, os.W_OK) if exists else False,
            "instance_id": manifest.get("instance_id") if manifest else None,
            "layout_version": manifest.get("layout_version") if manifest else None,
            "warning": warning,
        }

    def verify(self) -> dict[str, Any]:
        manifest = self.manifest()
        missing = [name for name in DIRECTORIES if not self.layout.path(name).is_dir()]
        # This is intentionally structural and content-free. Encrypted artifact and
        # database verification occurs only after application authentication.
        return {
            **self.status(),
            "verified": not missing,
            "missing_directories": missing,
            "pre_authentication": True,
            "content_disclosed": False,
            "manifest_sha256": sha256(self.layout.manifest.read_bytes()).hexdigest(),
            "instance_id": manifest["instance_id"],
        }

    def active_writer(self) -> dict[str, Any] | None:
        """Return a live local dashboard writer bound to this home, if any."""

        for candidate in (
            self.layout.path("runtime/dashboard-daemon.json"),
            self.layout.path("dashboard-daemon.json"),
        ):
            try:
                value = json.loads(candidate.read_text(encoding="utf-8"))
            except (FileNotFoundError, json.JSONDecodeError, OSError):
                continue
            if not isinstance(value, dict):
                continue
            hostname = str(value.get("hostname") or "")
            pid = int(value.get("pid") or 0)
            if hostname and hostname != socket.gethostname():
                continue
            if _pid_alive(pid):
                return {"pid": pid, "hostname": hostname or socket.gethostname(),
                        "state": str(candidate)}
        return None

    def snapshot(self, destination: str | Path) -> dict[str, Any]:
        """Create a verified copy while the selected home is quiescent."""

        source = self.layout.root
        target = HomeLayout.selected(destination).root
        if source == target:
            raise ValueError("snapshot destination must differ from its source")
        try:
            target.relative_to(source)
        except ValueError:
            pass
        else:
            raise ValueError("snapshot destination must not be inside its source")
        writer = self.active_writer()
        if writer is not None:
            raise ValueError(
                "AtMem Home has an active dashboard writer; stop it with "
                "`atmem dashboard daemon stop` before snapshotting"
            )
        if target.exists():
            raise ValueError("snapshot destination already exists")
        self.verify()
        source_digest, files, byte_count = _digest_path(source)
        shutil.copytree(source, target, symlinks=False)
        target_digest, target_files, target_bytes = _digest_path(target)
        if (source_digest, files, byte_count) != (
            target_digest, target_files, target_bytes
        ):
            shutil.rmtree(target, ignore_errors=True)
            raise ValueError("snapshot verification failed; incomplete destination removed")
        return {
            "format": "atmem-home-snapshot-v1",
            "source": str(source),
            "destination": str(target),
            "content_sha256": source_digest,
            "files": files,
            "bytes": byte_count,
            "verified": True,
            "source_preserved": True,
            "created_at": utc_now(),
        }

    def prepare_restore(self) -> dict[str, Any]:
        """Create a disposable machine-local state binding for a copied home."""

        status = self.status()
        if not status["exists"]:
            raise FileNotFoundError(f"AtMem Home does not exist: {self.layout.root}")
        state_candidates = (
            self.layout.path("config/control-plane.json"),
            self.layout.path("control-plane.json"),
        )
        source_state = next((path for path in state_candidates if path.is_file()), None)
        if source_state is None:
            raise ValueError(
                "no control-plane state was found in the copied home; run `atmem home migrate` "
                "for guided legacy conversion"
            )
        from dataclasses import replace
        from atmem.control.state import load_state, write_state

        state = load_state(source_state)
        old_control = Path(state.control_dir)
        control_candidates = (
            self.layout.path(f"migrations/{old_control.name}"),
            self.layout.path(f"migrations/legacy-control/{old_control.name}"),
        )
        control_dir = next((path for path in control_candidates if path.is_dir()), None)
        if control_dir is None:
            raise ValueError(
                "the copied home is incomplete: its referenced encrypted control directory is missing"
            )
        runtime_state = self.layout.path("runtime/restore-control-plane.json")
        self.layout.runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
        rebound = replace(state, control_dir=str(control_dir), revision=state.revision + 1)
        write_state(runtime_state, rebound)
        _atomic_json(
            self.layout.path("runtime/home-mode.json"),
            {
                "format": "atmem-home-runtime-mode-v1",
                "mode": "restore_read_only",
                "instance_id": status.get("instance_id"),
                "updated_at": utc_now(),
            },
        )
        return {
            "format": "atmem-home-restore-preflight-v1",
            "home": str(self.layout.root),
            "portable": bool(status["portable"]),
            "legacy_discovered": not bool(status["portable"]),
            "read_only_restore": True,
            "source_state": str(source_state.relative_to(self.layout.root)),
            "runtime_state": str(runtime_state),
            "control_directory": str(control_dir.relative_to(self.layout.root)),
            "content_disclosed": False,
            "login_required": True,
        }

    def adopt(
        self,
        *,
        administrator_confirmed: bool,
        allowed_writer_pid: int | None = None,
    ) -> dict[str, Any]:
        if not administrator_confirmed:
            raise PermissionError("Administrator confirmation is required to adopt a home")
        manifest = self.manifest()
        verification = self.verify()
        if not verification["verified"]:
            raise ValueError("AtMem Home must verify before adoption")
        writer = self.active_writer()
        if writer is not None and writer["pid"] != allowed_writer_pid:
            raise ValueError(
                f"AtMem Home has an active writer process ({writer['pid']}); "
                "stop it before adoption"
            )
        now = utc_now()
        binding_id = f"binding_{uuid.uuid4().hex}"
        receipt = {
            "format": "atmem-home-adoption-receipt-v1",
            "instance_id": manifest["instance_id"],
            "binding_id": binding_id,
            "historical_evidence_rewritten": False,
            "sessions_rotated": True,
            "indexes_require_rebuild": True,
            "adopted_at": now,
        }
        _atomic_json(self.layout.path(f"migrations/adoption-{binding_id}.json"), receipt)
        manifest.update({"updated_at": now, "adopted": True, "binding_id": binding_id})
        _atomic_json(self.layout.manifest, manifest)
        _atomic_json(
            self.layout.path("runtime/home-mode.json"),
            {
                "format": "atmem-home-runtime-mode-v1",
                "mode": "adopted_writable",
                "instance_id": manifest["instance_id"],
                "binding_id": binding_id,
                "updated_at": now,
            },
        )
        return receipt

    def migrate_legacy(
        self,
        destination: str | Path,
        *,
        commit: bool = False,
        rollback: bool = False,
        _interrupt_after: str | None = None,
    ) -> dict[str, Any]:
        """Copy an existing home into a canonical generation; never delete source."""

        source = self.layout.root
        target_service = HomeService(destination)
        target = target_service.layout.root
        if source == target:
            raise ValueError("migration destination must differ from the legacy source")
        try:
            target.relative_to(source)
        except ValueError:
            pass
        else:
            raise ValueError("migration destination must not be inside its source")
        if commit and rollback:
            raise ValueError("choose either migration commit or rollback")
        source_token = sha256(str(source).encode("utf-8")).hexdigest()
        journal = target / "migrations" / "legacy-migration.json"
        resume = False
        if target.exists() and any(target.iterdir()):
            if not journal.is_file():
                raise ValueError("migration destination must be empty")
            existing = json.loads(journal.read_text(encoding="utf-8"))
            if existing.get("format") != "atmem-home-migration-v1" or existing.get("source_token") != source_token:
                raise ValueError("migration destination belongs to another source")
            if rollback:
                if existing.get("phase") == "commit":
                    raise ValueError("a committed migration generation cannot be rolled back automatically")
                shutil.rmtree(target)
                return {
                    "format": "atmem-home-migration-v1",
                    "source_token": source_token,
                    "source": str(source),
                    "destination": str(target),
                    "phase": "rolled_back",
                    "source_preserved": True,
                }
            if existing.get("phase") in {"discover", "preflight", "copy"}:
                resume = True
            elif existing.get("phase") not in {"verify", "switch", "commit"}:
                raise ValueError("migration journal has an unsupported phase")
            if resume:
                pass
            else:
                if commit and existing.get("phase") != "commit":
                    existing.update({"phase": "switch", "switched_at": utc_now()})
                    _atomic_json(journal, existing)
                    if _interrupt_after == "switch":
                        raise RuntimeError("simulated migration interruption after switch")
                    existing.update({"phase": "commit", "committed_at": utc_now()})
                    _atomic_json(journal, existing)
                return {
                    **existing,
                    "source": str(source),
                    "destination": str(target),
                }
        daemon_state = source / "dashboard-daemon.json"
        if daemon_state.is_file():
            try:
                daemon = json.loads(daemon_state.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                daemon = {}
            if _pid_alive(int(daemon.get("pid") or 0)):
                raise ValueError("stop the source AtMem dashboard before migration")
        if not resume:
            target_service.initialize()
        journal = target_service.layout.path("migrations/legacy-migration.json")
        mapping: list[dict[str, Any]] = []
        candidates = {
            "control-plane.json": "config/control-plane.json",
            "memories.db": "memory/memories.db",
            "migrations": "migrations/legacy-control",
            "keys": "identity/keys",
            "atbot": "config/atbot",
            "providers": "config/providers",
            "delegated-context.json": "config/delegated-context.json",
            "onboarding.json": "config/onboarding.json",
            "backups": "backups/legacy",
            "openclaw-execution-spool.json": "runtime/openclaw-execution-spool.json",
            "openclaw-attachment-bindings": "runtime/openclaw-attachment-bindings",
            "artifacts": "artifacts",
            "identity": "identity",
            "memory": "memory",
            "evidence": "evidence",
            "config": "config",
        }
        base_journal = {
            "format": "atmem-home-migration-v1",
            "source_token": source_token,
            "destination_instance_id": target_service.manifest()["instance_id"],
            "phase": "discover",
            "source_preserved": True,
            "updated_at": utc_now(),
        }
        _atomic_json(journal, base_journal)
        if _interrupt_after == "discover":
            raise RuntimeError("simulated migration interruption after discover")
        base_journal.update({"phase": "preflight", "updated_at": utc_now()})
        _atomic_json(journal, base_journal)
        if _interrupt_after == "preflight":
            raise RuntimeError("simulated migration interruption after preflight")
        for old, new in candidates.items():
            source_path = source / old
            if not source_path.exists():
                continue
            source_digest, file_count, byte_count = _digest_path(source_path)
            destination_path = target_service.layout.path(new)
            if source_path.is_dir():
                shutil.copytree(source_path, destination_path, dirs_exist_ok=True, symlinks=False)
            elif source_path.is_file() and not source_path.is_symlink():
                destination_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                shutil.copy2(source_path, destination_path)
            else:
                raise ValueError(f"legacy source contains unsupported path: {old}")
            source_digest_after, _, _ = _digest_path(source_path)
            destination_digest, destination_files, destination_bytes = _digest_path(destination_path)
            if source_digest != source_digest_after or source_digest != destination_digest:
                raise ValueError(f"legacy source changed or failed verification while copying {old}")
            if destination_files != file_count or destination_bytes != byte_count:
                raise ValueError(f"legacy copy size verification failed for {old}")
            mapping.append({
                "source": old,
                "destination": new,
                "content_sha256": source_digest,
                "files": file_count,
                "bytes": byte_count,
            })
        copied = {
            **base_journal,
            "phase": "copy",
            "mapping": mapping,
            "updated_at": utc_now(),
        }
        _atomic_json(journal, copied)
        if _interrupt_after == "copy":
            raise RuntimeError("simulated migration interruption after copy")
        persisted = {
            "format": "atmem-home-migration-v1",
            "source_token": source_token,
            "destination_instance_id": target_service.manifest()["instance_id"],
            "phase": "verify",
            "source_preserved": True,
            "mapping": mapping,
            "updated_at": utc_now(),
        }
        _atomic_json(journal, persisted)
        if _interrupt_after == "verify":
            raise RuntimeError("simulated migration interruption after verify")
        if commit:
            persisted.update({"phase": "switch", "switched_at": utc_now()})
            _atomic_json(journal, persisted)
            if _interrupt_after == "switch":
                raise RuntimeError("simulated migration interruption after switch")
            persisted.update({"phase": "commit", "committed_at": utc_now()})
            _atomic_json(journal, persisted)
        return {**persisted, "source": str(source), "destination": str(target)}
