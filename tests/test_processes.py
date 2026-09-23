from __future__ import annotations

import os

from atmem.processes import pid_is_running


def test_pid_is_running_recognizes_current_process() -> None:
    assert pid_is_running(os.getpid()) is True


def test_pid_is_running_rejects_non_positive_pid() -> None:
    assert pid_is_running(0) is False
    assert pid_is_running(-1) is False


def test_pid_is_running_rejects_unallocated_pid() -> None:
    # Windows PIDs are DWORDs, but this value is not a valid process ID on
    # supported platforms and avoids relying on a recently exited child.
    assert pid_is_running(0xFFFFFFFF) is False
