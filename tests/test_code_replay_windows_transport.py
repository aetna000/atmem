import ast
import json
import subprocess
import sys

from benchmarks.code_replay.windows_transport import REMOTE_LOADER, command, worker_program


def test_remote_loader_reads_json_once_and_preserves_nested_payload():
    payload = {"source": {"file.py": "quoted\nbytes"}, "private": {"role": "fixture-only"}}
    job = {"program": 'print(json.dumps(job["payload"]))', "payload": payload}
    result = subprocess.run([sys.executable, "-I", "-S", "-c", REMOTE_LOADER],
        input=json.dumps(job).encode(), capture_output=True, timeout=10)
    assert result.returncode == 0
    assert json.loads(result.stdout) == payload


def test_reused_controller_keeps_budget_and_uses_physical_disk_and_ram_spool():
    source = worker_program()
    ast.parse(source, feature_version=(3, 9))
    assert "json.load(" not in source
    assert source.count('shutil.disk_usage("/mnt/c").free') == 2
    assert source.count('tempfile.TemporaryFile(dir="/dev/shm")') == 2
    assert "8 * 1024 ** 3" in source and "8_000_000" in source
    assert "container_cleanup_failed" in source and "controller_timeout" in source


def test_ssh_uses_existing_authenticated_control_socket_and_no_tty_or_password():
    args = command()
    assert "-T" in args and "BatchMode=yes" in args
    assert "-t" not in args and "-tt" not in args
    assert args[-1].endswith('"' + REMOTE_LOADER + '"')
    assert " -u root " in args[-1]
import subprocess
import sys

from benchmarks.code_replay.windows_transport import FRAMED_LOADER, framed_input, framed_command


def test_length_framing_finishes_without_parent_stdin_eof():
    process = subprocess.Popen([sys.executable, '-I', '-c', FRAMED_LOADER], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    try:
        process.stdin.write(framed_input({'program': "import sys;sys.stdout.buffer.write(b'FRAMED_OK\\n')"})); process.stdin.flush()
        assert process.wait(timeout=3) == 0
        assert process.stdout.read() == b'FRAMED_OK\n'
        assert not process.stdin.closed
        assert FRAMED_LOADER in framed_command()[-1]
    finally:
        if process.poll() is None:
            process.kill(); process.wait(timeout=3)
        process.stdin.close(); process.stdout.close()


def test_local_wsl_transport_is_explicit_and_does_not_require_nested_ssh(monkeypatch):
    from pathlib import Path
    import benchmarks.code_replay.windows_transport as transport
    monkeypatch.setenv("ATMEM_BENCHMARK_LOCAL_WSL", "1")
    monkeypatch.setattr(transport.sys, "platform", "linux")
    monkeypatch.setattr(Path, "is_dir", lambda self: self.as_posix() == "/mnt/c")
    args = framed_command()
    assert args == [sys.executable, "-I", "-S", "-c", FRAMED_LOADER]
    monkeypatch.setattr(transport.sys, "platform", "darwin")
    with __import__("pytest").raises(ValueError):
        framed_command()

