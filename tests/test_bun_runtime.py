from __future__ import annotations

from hashlib import sha256
import io
import json
import os
from pathlib import Path
from zipfile import ZipFile

import pytest

from atmem import bun_runtime


def _archive() -> bytes:
    output = io.BytesIO()
    name = "bun.exe" if os.name == "nt" else "bun"
    with ZipFile(output, "w") as bundle:
        bundle.writestr(f"bun-test/{name}", b"test-bun-binary")
    return output.getvalue()


def test_ensure_bun_downloads_verifies_and_keeps_runtime_private(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    archive = _archive()
    digest = sha256(archive).hexdigest()
    monkeypatch.setenv("ATMEM_HOME", str(tmp_path))
    monkeypatch.setattr(bun_runtime, "find_bun", lambda: None)
    monkeypatch.setattr(bun_runtime, "_asset", lambda: ("bun-test.zip", digest))
    monkeypatch.setattr(bun_runtime, "urlopen", lambda *_args, **_kwargs: io.BytesIO(archive))
    monkeypatch.setattr(
        bun_runtime,
        "_inspect",
        lambda path, *, managed: {
            "path": str(path), "version": bun_runtime.BUN_VERSION, "managed": managed
        } if path.is_file() else None,
    )
    original_path = os.environ.get("PATH")

    result = bun_runtime.ensure_bun()

    assert result["managed"] is True
    assert Path(result["path"]).read_bytes() == b"test-bun-binary"
    assert os.environ.get("PATH") == original_path
    message = capsys.readouterr().err
    assert "downloading official Bun" in message
    assert "pinned SHA-256" in message
    assert "global PATH was not changed" in message


def test_ensure_bun_rejects_digest_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = _archive()
    monkeypatch.setenv("ATMEM_HOME", str(tmp_path))
    monkeypatch.setattr(bun_runtime, "find_bun", lambda: None)
    monkeypatch.setattr(bun_runtime, "_asset", lambda: ("bun-test.zip", "0" * 64))
    monkeypatch.setattr(bun_runtime, "urlopen", lambda *_args, **_kwargs: io.BytesIO(archive))

    with pytest.raises(RuntimeError, match="SHA-256 verification"):
        bun_runtime.ensure_bun()

    assert not bun_runtime._managed_executable().exists()


def test_find_bun_rejects_changed_managed_executable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ATMEM_HOME", str(tmp_path))
    monkeypatch.setattr(bun_runtime.shutil, "which", lambda _name: None)
    target = bun_runtime._managed_executable()
    target.parent.mkdir(parents=True)
    target.write_bytes(b"original")
    target.with_name("install.json").write_text(
        json.dumps({
            "format": "atmem-managed-bun-v1",
            "version": bun_runtime.BUN_VERSION,
            "executable_sha256": sha256(b"original").hexdigest(),
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        bun_runtime,
        "_inspect",
        lambda path, *, managed: {
            "path": str(path), "version": bun_runtime.BUN_VERSION, "managed": managed
        },
    )

    assert bun_runtime.find_bun() is not None
    target.write_bytes(b"changed")
    assert bun_runtime.find_bun() is None
