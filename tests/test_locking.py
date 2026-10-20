from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

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


def test_windows_descriptor_preserves_requested_lock_mode(tmp_path: Path, monkeypatch) -> None:
    events = []
    monkeypatch.setattr(locking, "_windows_range_lock", lambda descriptor, **kwargs: events.append(kwargs))
    monkeypatch.setattr(locking, "_is_windows", lambda: True)
    descriptor = os.open(tmp_path / "windows.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        locking._lock_descriptor(descriptor, exclusive=False, blocking=False)
        locking._lock_descriptor(descriptor, exclusive=True, blocking=True)
        locking._unlock_descriptor(descriptor)
        assert events == [{"exclusive": False, "blocking": False}, {"exclusive": True, "blocking": True}, {"unlock": True}]
    finally:
        os.close(descriptor)


@pytest.mark.parametrize("parent_exclusive,child_exclusive,allowed", [(False, False, True), (False, True, False),
                                                                     (True, False, False), (True, True, False)])
def test_cross_process_shared_and_exclusive_matrix(tmp_path, parent_exclusive, child_exclusive, allowed):
    path = tmp_path / "shared.lock"
    with locking.ProcessFileLock(path, exclusive=parent_exclusive):
        program = """
import sys
from atmem.locking import ProcessFileLock
try:
    with ProcessFileLock(sys.argv[1], exclusive=sys.argv[2] == 'True'):
        pass
except BlockingIOError:
    raise SystemExit(9)
"""
        result = subprocess.run([sys.executable, "-c", program, str(path), str(child_exclusive)], timeout=10)
        assert result.returncode == (0 if allowed else 9)
    # Releasing the parent must actually release the kernel lock.
    result = subprocess.run([sys.executable, "-c", program, str(path), "True"], timeout=10)
    assert result.returncode == 0
