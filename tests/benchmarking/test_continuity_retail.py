"""Offline native retail parity: requires a separately pinned upstream checkout."""
import json
import hashlib
import multiprocessing as mp
import os
from pathlib import Path

import pytest

from benchmarks.agent_continuity.retail import LOCK, RetailProcess, pilot_task, reference_parity, verify_checkout, send_json


@pytest.fixture
def upstream():
    value = os.environ.get("CONTINUITY_TAU_ROOT")
    if not value:
        pytest.skip("set CONTINUITY_TAU_ROOT to the pinned tau2 checkout")
    return Path(value)


def test_heldout_replay_rejected_before_data_read(tmp_path):
    task_id = json.loads(LOCK.read_text())["split"]["heldout_ids"][0]
    with pytest.raises(ValueError, match="restricted"):
        pilot_task(tmp_path / "does-not-exist", task_id)


def test_pinned_native_and_process_tools_match(upstream):
    report = reference_parity(upstream, "0")
    assert report["matched"], report
    assert report["calls"] > 0
    assert not report["agent_evaluation"]
    assert not report["production_claims_allowed"]
    assert report["egress_attempts"] == []
    assert report["tool_errors"] == 0
    assert report["state_changed"]


def test_tool_boundary_rejects_oracle_requests_and_preserves_native_errors(upstream):
    with RetailProcess(upstream) as remote:
        assert remote.info["pid"] != os.getpid()
        send_json(remote.public, {"method": "snapshot"})
        assert remote._receive(remote.public) == {"error": "unknown public request"}
        send_json(remote.public, ["invalid-request"])
        assert remote._receive(remote.public) == {"error": "unknown public request"}
        result = remote.call({"id": "bad-call", "name": "not_a_tool", "arguments": {}})
        assert result["error"] is True
        assert remote.snapshot()["egress_attempts"] == []


def test_tree_verification_records_policy_and_source(upstream):
    stamp = verify_checkout(upstream)
    assert all(len(stamp[key]) == 64 for key in ("policy_sha256", "tools_sha256", "tree_sha256"))


def test_self_consistent_git_tree_still_needs_independent_pin(upstream, tmp_path, monkeypatch):
    from benchmarks.agent_continuity import retail
    lock = json.loads(retail.SOURCE_LOCK.read_text())
    lock["tree_sha256"] = "0" * 64
    path = tmp_path / "different-pin.json"
    path.write_text(json.dumps(lock))
    monkeypatch.setattr(retail, "SOURCE_LOCK", path)
    with pytest.raises(ValueError, match="independent source lock"):
        retail.verify_checkout(upstream)


def _guard_probe(connection):
    import socket
    from benchmarks.agent_continuity.retail import offline_guard
    os.environ["OPENAI_API_KEY"] = "fixture-not-a-real-key"
    attempts = offline_guard(Path("/nonexistent-fixture"))
    for address in ("example.invalid", "127.0.0.1"):
        try:
            socket.getaddrinfo(address, 443)
        except PermissionError:
            pass
    import subprocess
    with socket.socket() as connection_socket:
        try:
            connection_socket.connect(("127.0.0.1", 1))
        except PermissionError:
            pass
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
        try:
            udp.sendto(b"fixture", ("127.0.0.1", 1))
        except PermissionError:
            pass
    try:
        subprocess.run(["echo", "forbidden"], check=True)
    except PermissionError:
        pass
    connection.send({"attempts": attempts, "credentials_removed": "OPENAI_API_KEY" not in os.environ,
                     "dotenv_disabled": os.environ["PYTHON_DOTENV_DISABLED"] == "1"})
    connection.close()


def test_offline_guard_blocks_even_loopback_and_removes_credentials():
    ctx = mp.get_context("spawn")
    parent, child = ctx.Pipe(False)
    process = ctx.Process(target=_guard_probe, args=(child,))
    process.start()
    child.close()
    try:
        assert parent.poll(15)
        assert parent.recv() == {"attempts": ["socket.getaddrinfo", "socket.getaddrinfo", "socket.connect",
                                              "socket.sendto", "subprocess.Popen"],
                                 "credentials_removed": True, "dotenv_disabled": True}
    finally:
        process.join(5)
        if process.is_alive():
            process.kill()
            process.join(5)
        parent.close()


def test_source_bytes_not_just_commit_are_checked(tmp_path, monkeypatch):
    from benchmarks.agent_continuity import retail
    relative = "src/tau2/example.py"
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    path.write_bytes(b"modified")
    original = b"original"
    blob = hashlib.sha1(b"blob 8\0" + original).hexdigest()
    monkeypatch.setattr(retail, "git_head", lambda _: retail.UPSTREAM_COMMIT)
    monkeypatch.setattr(retail.subprocess, "check_output", lambda *a, **k:
                        f"100644 blob {blob}\t{relative}\0".encode())
    with pytest.raises(ValueError, match="modified upstream"):
        retail.verify_checkout(tmp_path)


@pytest.mark.parametrize("extra", ["module", "shadow", "symlink"])
def test_untracked_modules_shadow_packages_and_symlinks_rejected(tmp_path, monkeypatch, extra):
    from benchmarks.agent_continuity import retail
    tracked = tmp_path / "src/tau2/__init__.py"
    tracked.parent.mkdir(parents=True)
    tracked.write_bytes(b"original")
    blob = hashlib.sha1(b"blob 8\0original").hexdigest()
    monkeypatch.setattr(retail, "git_head", lambda _: retail.UPSTREAM_COMMIT)
    monkeypatch.setattr(retail.subprocess, "check_output", lambda *a, **k:
                        f"100644 blob {blob}\tsrc/tau2/__init__.py\0".encode())
    if extra == "module":
        (tracked.parent / "extra.py").write_text("pass")
    elif extra == "shadow":
        (tmp_path / "src/loguru.py").write_text("pass")
    else:
        (tracked.parent / "alias.py").symlink_to(tracked)
    with pytest.raises(ValueError, match="untracked|shadow|redirected"):
        retail.verify_checkout(tmp_path)


def _cache_probe(root, connection):
    from benchmarks.agent_continuity.retail import _load_environment, offline_guard
    offline_guard(Path(root))
    connection.send(_load_environment(Path(root)))
    connection.close()


def test_import_ignores_matching_but_poisoned_in_tree_bytecode(tmp_path):
    import py_compile
    root = tmp_path / "upstream"
    directory = root / "src/tau2/domains/retail"
    directory.mkdir(parents=True)
    for part in [root / "src/tau2", root / "src/tau2/domains", directory]:
        (part / "__init__.py").write_text("")
    module = directory / "environment.py"
    module.write_text("def get_environment(): return 'poisoned'\n")
    stamp = module.stat()
    py_compile.compile(str(module), doraise=True)
    module.write_text("def get_environment(): return 'original'\n")
    os.utime(module, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    ctx = mp.get_context("spawn")
    parent, child = ctx.Pipe(False)
    process = ctx.Process(target=_cache_probe, args=(str(root), child))
    process.start()
    child.close()
    try:
        assert parent.poll(20)
        assert parent.recv() == "original"
    finally:
        process.join(5)
        if process.is_alive():
            process.kill()
            process.join(5)
        parent.close()
