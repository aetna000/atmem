from __future__ import annotations

import errno
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from atmem import locking


def test_nested_compatible_locks_share_one_os_lock(tmp_path: Path, monkeypatch) -> None:
    events: list[tuple[str, int]] = []
    monkeypatch.setattr(
        locking,
        "_lock_descriptor",
        lambda descriptor, **_options: events.append(("lock", descriptor)),
    )
    monkeypatch.setattr(
        locking,
        "_unlock_descriptor",
        lambda descriptor: events.append(("unlock", descriptor)),
    )
    first = locking.ProcessFileLock(tmp_path / "memory.db.lock", exclusive=False).acquire()
    second = locking.ProcessFileLock(tmp_path / "memory.db.lock", exclusive=False).acquire()

    assert [event[0] for event in events] == ["lock"]
    second.close()
    assert [event[0] for event in events] == ["lock"]
    first.close()
    assert [event[0] for event in events] == ["lock", "unlock"]
    assert events[0][1] == events[1][1]


def test_nested_lock_cannot_change_mode(tmp_path: Path) -> None:
    shared = locking.ProcessFileLock(tmp_path / "memory.db.lock", exclusive=False).acquire()
    try:
        with pytest.raises(BlockingIOError):
            locking.ProcessFileLock(tmp_path / "memory.db.lock", exclusive=True).acquire()
    finally:
        shared.close()


def test_exclusive_lock_blocks_another_process(tmp_path: Path) -> None:
    path = tmp_path / "memory.db.lock"
    parent = locking.ProcessFileLock(path, exclusive=False).acquire()
    program = """
import sys
from atmem.locking import ProcessFileLock
try:
    ProcessFileLock(sys.argv[1], exclusive=True).acquire()
except BlockingIOError:
    raise SystemExit(0)
raise SystemExit(1)
"""
    try:
        child = subprocess.run([sys.executable, "-c", program, str(path)], check=False)
        assert child.returncode == 0
    finally:
        parent.close()


def test_windows_denied_lock_is_reported_as_contention(
    tmp_path: Path, monkeypatch
) -> None:
    def deny(_descriptor: int, _operation: int, _length: int) -> None:
        raise PermissionError(errno.EACCES, "denied")

    fake_msvcrt = SimpleNamespace(
        LK_LOCK=1,
        LK_NBLCK=2,
        LK_UNLCK=3,
        locking=deny,
    )
    monkeypatch.setitem(sys.modules, "msvcrt", fake_msvcrt)
    monkeypatch.setattr(locking, "_is_windows", lambda: True)
    descriptor = os.open(tmp_path / "windows.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        with pytest.raises(BlockingIOError) as caught:
            locking._lock_descriptor(descriptor, exclusive=False, blocking=False)
        assert caught.value.errno == errno.EWOULDBLOCK
    finally:
        os.close(descriptor)
