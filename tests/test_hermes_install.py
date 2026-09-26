import json
import os
from pathlib import Path

import pytest

from atmem.hermes_install import RECEIPT, _publish, inspect_install, install

pytestmark = pytest.mark.skipif(os.name != "posix", reason="inactive installer not native Windows qualified")


def snapshot(home):
    return {str(p.relative_to(home)): p.read_bytes() for p in home.rglob("*") if p.is_file()}


def test_preview_and_install_preserve_native_files(tmp_path):
    home = tmp_path.resolve() / "hermes"
    home.mkdir()
    (home / "config.yaml").write_text("memory:\n  provider: builtin\n")
    (home / ".env").write_text("DO_NOT_READ_OR_CHANGE=canary")
    (home / "MEMORY.md").write_text("original")
    before = snapshot(home)
    assert not install(home)["applied"]
    assert snapshot(home) == before
    assert not (home / "plugins").exists()
    assert install(home, apply=True)["applied"]
    for name, content in before.items():
        assert (home / name).read_bytes() == content
    assert not install(home, apply=True)["applied"]
    assert not (home / ".atmem").exists()


def test_modified_unmanaged_and_extra_sources_refuse(tmp_path):
    home = tmp_path.resolve()
    target = home / "plugins" / "atmem"
    target.mkdir(parents=True)
    assert inspect_install(home)["state"] == "conflict"
    with pytest.raises(ValueError):
        install(home, apply=True)
    target.rmdir()
    install(home, apply=True)
    (target / "extra.py").write_text("malicious = True")
    with pytest.raises(ValueError):
        install(home, apply=True)
    (target / "extra.py").unlink()
    (target / "client.py").write_text("edited")
    assert inspect_install(home)["state"] == "conflict"


def test_cache_and_intact_old_payload(tmp_path):
    home = tmp_path.resolve()
    install(home, apply=True)
    target = home / "plugins" / "atmem"
    cache = target / "__pycache__"
    cache.mkdir()
    (cache / "client.cpython-314.pyc").write_bytes(b"cache")
    assert inspect_install(home)["state"] == "installed"
    import hashlib
    (target / "client.py").write_bytes(b"old installed version")
    receipt = json.loads((target / RECEIPT).read_text())
    receipt["sha256"]["client.py"] = hashlib.sha256(b"old installed version").hexdigest()
    (target / RECEIPT).write_text(json.dumps(receipt))
    assert inspect_install(home)["state"] == "upgrade_required"


def test_unsafe_parent_and_target_refuse(tmp_path):
    home = tmp_path.resolve()
    parent = home / "plugins"
    parent.mkdir()
    parent.chmod(0o777)
    with pytest.raises(ValueError):
        install(home, apply=True)
    parent.chmod(0o700)
    (parent / "atmem").symlink_to(home)
    with pytest.raises(ValueError):
        install(home, apply=True)


def test_publication_never_replaces_even_empty_directory(tmp_path):
    stage, target = tmp_path / "stage", tmp_path / "target"
    stage.mkdir()
    target.mkdir()
    with pytest.raises(OSError):
        _publish(stage, target)
    assert stage.is_dir() and target.is_dir()


def test_interrupted_publication_is_invisible_and_retryable(tmp_path, monkeypatch):
    import atmem.hermes_install as module
    home = tmp_path.resolve()
    publish = module._publish
    monkeypatch.setattr(module, "_publish", lambda *a: (_ for _ in ()).throw(RuntimeError("interrupted")))
    with pytest.raises(RuntimeError):
        install(home, apply=True)
    assert not (home / "plugins" / "atmem").exists()
    stages = list((home / "plugins").glob("__atmem_stage_*"))
    assert len(stages) == 1 and (stages[0] / RECEIPT).exists()
    monkeypatch.setattr(module, "_publish", publish)
    assert install(home, apply=True)["applied"]
    assert stages[0].exists()  # Unknown/interrupted stages never auto-deleted.


def test_failure_after_publication_keeps_valid_install(tmp_path, monkeypatch):
    import atmem.hermes_install as module
    home = tmp_path.resolve()
    sync = module._sync_directory
    def interrupted(path):
        if path.name == "plugins":
            raise RuntimeError("interrupted after rename")
        sync(path)
    monkeypatch.setattr(module, "_sync_directory", interrupted)
    with pytest.raises(RuntimeError):
        install(home, apply=True)
    assert inspect_install(home)["state"] == "installed"


def test_bad_home_and_lock_paths(tmp_path):
    home = tmp_path.resolve() / "hermes"
    home.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(home)
    for path in (alias, Path.home(), Path("/")):
        with pytest.raises(ValueError):
            install(path, apply=True)
    home.chmod(0o770)
    with pytest.raises(ValueError):
        install(home, apply=True)
    home.chmod(0o700)
    parent = home / "plugins"
    parent.mkdir()
    (parent / ".atmem-install.lock").symlink_to(home / "config.yaml")
    with pytest.raises(OSError):
        install(home, apply=True)
    assert not (home / "config.yaml").exists()


def test_cli_preview_status_and_apply(tmp_path):
    import subprocess
    import sys
    home = tmp_path.resolve() / "hermes"
    home.mkdir()
    absent_atmem = tmp_path / "absent_atmem"
    env = {**os.environ, "ATMEM_HOME": str(absent_atmem)}
    base = [sys.executable, "-m", "atmem.cli", "hermes"]
    def run(command, *options):
        return subprocess.run(base + [command, "--hermes-home", str(home), "--json", *options],
                              env=env, capture_output=True, text=True, timeout=20)
    for command in ("status", "install"):
        result = run(command)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["applied"] is False
    assert not list(home.iterdir())
    assert not absent_atmem.exists()
    assert run("status", "--apply").returncode != 0
    assert json.loads(run("install", "--apply").stdout)["applied"] is True
    assert json.loads(run("status").stdout)["state"] == "installed"
    assert not absent_atmem.exists()
