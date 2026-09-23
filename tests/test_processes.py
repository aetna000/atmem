from __future__ import annotations

import os

from atmem.processes import _linux_pid_state, pid_is_running


def test_pid_is_running_recognizes_current_process() -> None:
    assert pid_is_running(os.getpid()) is True


def test_pid_is_running_rejects_non_positive_pid() -> None:
    assert pid_is_running(0) is False
    assert pid_is_running(-1) is False


def test_pid_is_running_rejects_unallocated_pid() -> None:
    # Windows PIDs are DWORDs, but this value is not a valid process ID on
    # supported platforms and avoids relying on a recently exited child.
    assert pid_is_running(0xFFFFFFFF) is False


def test_linux_pid_state_handles_parentheses_in_process_name(
    tmp_path, monkeypatch
) -> None:
    stat = tmp_path / "stat"
    stat.write_text("123 (worker) child) Z 1 2 3\n", encoding="ascii")
    monkeypatch.setattr(
        "atmem.processes.Path",
        lambda _value: stat,
    )

    assert _linux_pid_state(123) == "Z"


def test_linux_pid_state_fails_open_when_procfs_is_unavailable(monkeypatch) -> None:
    def unavailable(*_args, **_kwargs):
        raise OSError("procfs unavailable")

    monkeypatch.setattr("atmem.processes.Path.read_text", unavailable)

    assert _linux_pid_state(123) is None
