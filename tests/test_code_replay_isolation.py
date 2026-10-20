"""Native shell sandbox checks, no model invocation or inference credit."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from benchmarks.code_replay.sandbox import permission_arguments, shell_probe

pytestmark = pytest.mark.skipif(sys.platform != "darwin" or shutil.which("codex") is None,
                                reason="native macOS Codex sandbox qualification only")


def test_native_shell_cannot_open_future_grader_other_arm_or_owner_canaries(tmp_path):
    workspace = tmp_path / "atmem-click-isolation"
    workspace.mkdir()
    denied = []
    for name in ("future-object", "sealed-grader", "other-arm-memory", "owner-credential"):
        path = tmp_path / name
        path.write_text("PLANTED_READ_BARRIER_" + name)
        denied.append(path)
    assert shell_probe(workspace, denied_paths=tuple(denied))["passed"]
    with pytest.raises(ValueError):
        permission_arguments((Path.home(),))


def test_native_tool_network_denial_has_a_working_local_positive_control(tmp_path):
    workspace = tmp_path / "atmem-click-network"
    workspace.mkdir()
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass
        def do_GET(self):
            requests.append(self.path)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"LOCAL_SANDBOX_CONTROL")
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        args = ["codex", "sandbox", "-C", str(workspace), "-P", "click-replay", *permission_arguments()]
        tool = ["/usr/bin/curl", "--silent", "--show-error", "--connect-timeout", "1", "--max-time", "2",
                f"http://127.0.0.1:{server.server_port}/local-only"]
        enabled = subprocess.run([*args, "-c", "permissions.click-replay.network.enabled=true", *tool], capture_output=True, timeout=10)
        assert enabled.returncode == 0 and enabled.stdout == b"LOCAL_SANDBOX_CONTROL"
        assert len(requests) == 1
        disabled = subprocess.run([*args, *tool], capture_output=True, timeout=10)
        assert disabled.returncode != 0
        assert len(requests) == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_native_local_git_works_without_reading_ambient_owner_configuration(tmp_path):
    workspace = tmp_path / "atmem-click-git"
    workspace.mkdir()
    environment = {"PATH": "/usr/bin:/bin", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}
    subprocess.run(["/usr/bin/git", "init", str(workspace)], env=environment, capture_output=True, check=True)
    (workspace / "README").write_text("permitted tree")
    native = Path(subprocess.check_output(["/usr/bin/xcrun", "--find", "git"], text=True).strip())
    runtime = tmp_path / "atmem-click-git-runtime"
    runtime.mkdir()
    shutil.copy2(native, runtime / "git")
    result = subprocess.run([shutil.which("codex"), "sandbox", "-C", str(workspace), "-P", "click-replay", *permission_arguments((runtime,)),
                             str(runtime / "git"), "status", "--porcelain"], env=environment, capture_output=True, timeout=10)
    assert result.returncode == 0 and b"README" in result.stdout
