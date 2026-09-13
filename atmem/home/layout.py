"""One path authority for durable AtMem state."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


DIRECTORIES = (
    "config",
    "identity",
    "memory",
    "evidence",
    "artifacts/sha256",
    "indexes",
    "migrations",
    "runtime",
    "backups",
)


def resolve_home(explicit: str | Path | None = None) -> Path:
    """Resolve CLI, environment and default home precedence."""

    selected = explicit if explicit is not None else os.environ.get("ATMEM_HOME")
    target = Path(selected or (Path.home() / ".atmem")).expanduser()
    if target.is_symlink():
        raise ValueError("AtMem Home must not be a symlink")
    return target.resolve(strict=False)


def compatible_home_path(canonical: str, legacy: str | None = None) -> Path:
    """Prefer an existing beta path until its explicit home migration commits."""

    root = resolve_home()
    canonical_path = root / canonical
    legacy_path = root / legacy if legacy else None
    if legacy_path is not None and legacy_path.exists() and not canonical_path.exists():
        return legacy_path
    return canonical_path


@dataclass(frozen=True, slots=True)
class HomeLayout:
    root: Path

    @classmethod
    def selected(cls, explicit: str | Path | None = None) -> "HomeLayout":
        return cls(resolve_home(explicit))

    def path(self, relative: str | Path) -> Path:
        value = Path(relative)
        if value.is_absolute() or ".." in value.parts:
            raise ValueError("AtMem Home paths must be safe relative paths")
        target = self.root.joinpath(value)
        # Existing symlinks anywhere in the path are not allowed to redirect a
        # durable AtMem record outside its selected home.
        cursor = self.root
        for part in value.parts:
            cursor = cursor / part
            if cursor.is_symlink():
                raise ValueError(f"AtMem Home path must not traverse a symlink: {value}")
        resolved = target.resolve(strict=False)
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("AtMem Home path escapes the selected root") from exc
        return resolved

    @property
    def manifest(self) -> Path:
        return self.path("manifest.json")

    @property
    def artifacts(self) -> Path:
        return self.path("artifacts/sha256")

    @property
    def migrations(self) -> Path:
        return self.path("migrations")

    @property
    def runtime(self) -> Path:
        return self.path("runtime")

    def initialize_directories(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root.chmod(0o700)
        for relative in DIRECTORIES:
            directory = self.path(relative)
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            directory.chmod(0o700)
