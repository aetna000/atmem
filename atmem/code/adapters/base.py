"""Fail-closed host adapter contract and exact config restoration."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path
import tempfile
from typing import Protocol


@dataclass(frozen=True, slots=True)
class HostProbe:
    host: str
    version: str
    platform: str
    capture_verified: bool
    context_verified: bool
    assurance: str
    evidence_digest: str | None

    @property
    def automatic(self) -> bool:
        return self.capture_verified and self.context_verified and bool(self.evidence_digest)


@dataclass(frozen=True, slots=True)
class ConfigSnapshot:
    path: Path
    existed: bool
    content: bytes | None
    mode: int | None
    sha256: str | None


class HostAdapter(Protocol):
    host: str

    def probe(self) -> HostProbe: ...
    def verify_installed(self) -> HostProbe: ...
    def configuration_path(self) -> Path: ...
    def planned_configuration(self, previous: bytes | None) -> bytes: ...


def snapshot_configuration(path: str | Path) -> ConfigSnapshot:
    target = Path(path).expanduser()
    if target.is_symlink():
        raise ValueError("host configuration symlink is not supported")
    if not target.exists():
        return ConfigSnapshot(target, False, None, None, None)
    if not target.is_file():
        raise ValueError("host configuration must be a regular file")
    content = target.read_bytes()
    mode = target.stat().st_mode & 0o777
    return ConfigSnapshot(target, True, content, mode, sha256(content).hexdigest())


def _atomic_write(path: Path, content: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise ValueError("host configuration changed to a symlink")
    descriptor, temporary = tempfile.mkstemp(prefix=".atmem-code-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


class HostConfigTransaction:
    def __init__(self, adapter: HostAdapter) -> None:
        self.adapter = adapter
        self.initial_probe = adapter.probe()
        self.before = snapshot_configuration(adapter.configuration_path())
        self.after_digest: str | None = None

    def preview(self) -> dict:
        planned = self.adapter.planned_configuration(self.before.content)
        if not isinstance(planned, bytes) or len(planned) > 1_000_000:
            raise ValueError("host configuration must be bounded bytes")
        return {"host": self.adapter.host, "path": str(self.before.path),
                "host_version": self.initial_probe.version,
                "before_sha256": self.before.sha256,
                "planned_sha256": sha256(planned).hexdigest(),
                "existed": self.before.existed}

    def apply(self) -> dict:
        probe = self.adapter.probe()
        if probe.version != self.initial_probe.version or probe.platform != self.initial_probe.platform:
            raise RuntimeError("host version or platform changed since preview")
        current = snapshot_configuration(self.before.path)
        if current.sha256 != self.before.sha256 or current.existed != self.before.existed:
            raise RuntimeError("host configuration changed since preview")
        planned = self.adapter.planned_configuration(self.before.content)
        if not isinstance(planned, bytes) or len(planned) > 1_000_000:
            raise ValueError("host configuration must be bounded bytes")
        _atomic_write(self.before.path, planned, self.before.mode or 0o600)
        self.after_digest = sha256(planned).hexdigest()
        try:
            verified = self.adapter.verify_installed()
            if (verified.version != probe.version or verified.platform != probe.platform
                    or not verified.automatic):
                raise RuntimeError("installed host capture/context probe did not verify")
        except BaseException:
            # Explicit enable may briefly install the hook for its canary
            # probe, but no failed probe may leave the config activated.
            self.restore()
            raise
        return {"applied": True, "path": str(self.before.path),
                "before_sha256": self.before.sha256, "after_sha256": self.after_digest,
                "probe_evidence_sha256": verified.evidence_digest}

    def restore(self) -> dict:
        if self.after_digest is None:
            raise RuntimeError("host configuration was not applied by this transaction")
        return restore_configuration(self.before, self.after_digest)


def restore_configuration(before: ConfigSnapshot, installed_digest: str) -> dict:
    """Restore a persisted snapshot only if installed bytes still match."""
    current = snapshot_configuration(before.path)
    if current.sha256 != installed_digest:
        raise RuntimeError("host configuration changed after activation; refusing overwrite")
    if before.existed:
        assert before.content is not None and before.mode is not None
        if sha256(before.content).hexdigest() != before.sha256:
            raise ValueError("stored host configuration snapshot is corrupt")
        _atomic_write(before.path, before.content, before.mode)
    else:
        before.path.unlink()
    return {"restored": True, "path": str(before.path),
            "restored_sha256": before.sha256}
