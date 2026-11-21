"""Process identity failures never authorize termination or erase recovery state."""
import subprocess

import pytest

from atmem.provider_adapters import lifecycle


def test_windows_identity_read_retries_transient_timeout_without_changing_query(monkeypatch):
    calls = []
    def run(command, **kwargs):
        calls.append((command, kwargs["timeout"]))
        if len(calls) == 1:
            raise subprocess.TimeoutExpired(command, kwargs["timeout"], output="PRIVATE exception text")
        return subprocess.CompletedProcess(command, 0, stdout="python -m atmem.provider_adapters.worker live", stderr="")
    monkeypatch.setattr(lifecycle.subprocess, "run", run)
    assert "atmem.provider_adapters.worker live" in lifecycle._windows_pid_command(123)
    assert [timeout for _,timeout in calls] == [5, 10] and calls[0][0] == calls[1][0]


def test_permanent_identity_failure_is_bounded_and_contains_no_provider_exception(monkeypatch):
    attempts = []
    def run(command, **kwargs):
        attempts.append(kwargs["timeout"])
        raise subprocess.TimeoutExpired(["PRIVATE command or token"], kwargs["timeout"])
    monkeypatch.setattr(lifecycle.subprocess, "run", run)
    with pytest.raises(ValueError, match="process left running and ownership retained") as failure:
        lifecycle._windows_pid_command(123)
    assert attempts == [5, 10] and "PRIVATE" not in str(failure.value)
    assert lifecycle._windows_pid_command("123;untrusted") == ""


def test_stop_preserves_pid_until_exit_is_actually_confirmed(tmp_path, monkeypatch):
    pid_file = tmp_path/"service.pid"
    pid_file.write_text("123\n")
    signals = []
    monkeypatch.setattr(lifecycle, "load_config", lambda instance:(tmp_path, {}))
    monkeypatch.setattr(lifecycle, "_live_pid", lambda root:123)
    monkeypatch.setattr(lifecycle, "_pid_command", lambda pid:"python -m atmem.provider_adapters.worker live")
    monkeypatch.setattr(lifecycle.os, "kill", lambda pid, sig:signals.append(pid))
    monkeypatch.setattr(lifecycle.time, "sleep", lambda duration:None)
    monkeypatch.setattr(lifecycle, "_pid_exists", lambda pid:True)
    monkeypatch.setattr(lifecycle, "status", lambda instance:{"running":True, "pid":123})
    result = lifecycle.stop("live")
    assert result["stop_pending"] and result["running"] and pid_file.read_text() == "123\n"
    assert signals == [123]
    monkeypatch.setattr(lifecycle, "_pid_exists", lambda pid:False)
    monkeypatch.setattr(lifecycle, "status", lambda instance:{"running":False, "pid":None})
    stopped = lifecycle.stop("live")
    assert not stopped["running"] and "stop_pending" not in stopped and not pid_file.exists()


def test_unverified_identity_never_signals_or_discards_pid(tmp_path, monkeypatch):
    pid_file = tmp_path/"service.pid"
    pid_file.write_text("123\n")
    signals = []
    monkeypatch.setattr(lifecycle, "load_config", lambda instance:(tmp_path, {}))
    monkeypatch.setattr(lifecycle, "_live_pid", lambda root:123)
    monkeypatch.setattr(lifecycle.os, "kill", lambda pid, sig:signals.append(pid))
    def unavailable(pid):
        raise ValueError("process identity unavailable")
    monkeypatch.setattr(lifecycle, "_pid_command", unavailable)
    with pytest.raises(ValueError, match="identity unavailable"):
        lifecycle.stop("live")
    assert signals == [] and pid_file.is_file()
    monkeypatch.setattr(lifecycle, "_pid_command", lambda pid:"python -m atmem.provider_adapters.worker live2")
    with pytest.raises(ValueError, match="does not belong"):
        lifecycle.stop("live")
    assert signals == [] and pid_file.is_file()
