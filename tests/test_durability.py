from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import atmem.durability as durability


def test_directory_fsync_is_skipped_on_windows(
    tmp_path: Path, monkeypatch,
) -> None:
    def unexpected_open(*args, **kwargs):
        raise AssertionError("Windows must not open a directory with os.open")

    fake_os = SimpleNamespace(name="nt", O_RDONLY=0, open=unexpected_open)
    monkeypatch.setattr(durability, "os", fake_os)

    durability.fsync_directory(tmp_path)


def test_directory_fsync_is_applied_on_posix(
    tmp_path: Path, monkeypatch,
) -> None:
    calls: list[tuple[str, object]] = []

    fake_os = SimpleNamespace(
        name="posix",
        O_RDONLY=17,
        open=lambda path, flags: calls.append(("open", (path, flags))) or 42,
        fsync=lambda descriptor: calls.append(("fsync", descriptor)),
        close=lambda descriptor: calls.append(("close", descriptor)),
    )
    monkeypatch.setattr(durability, "os", fake_os)

    durability.fsync_directory(tmp_path)

    assert calls == [
        ("open", (tmp_path, 17)),
        ("fsync", 42),
        ("close", 42),
    ]
