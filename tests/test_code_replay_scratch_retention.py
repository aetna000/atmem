import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile

import pytest

from benchmarks.code_replay.scratch_retention import inventory, compressed_snapshot


def test_compressed_scratch_preserves_bytes_directories_and_link_without_following(tmp_path):
    root = tmp_path / "scratch"
    root.mkdir()
    (root / "empty").mkdir()
    (root / "source.py").write_bytes(b"exact\r\nbytes")
    (root / "outside-link").symlink_to(tmp_path / "not-archived")
    before = inventory(root)
    raw = compressed_snapshot(root, before)
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
        assert archive.extractfile("scratch/source.py").read() == b"exact\r\nbytes"
        assert archive.getmember("scratch/outside-link").issym()
        assert archive.getmember("scratch/empty").isdir()
    assert before["source.py"][0:2] == ["file", 12]


def test_mutated_scratch_is_not_accepted(tmp_path):
    (tmp_path / "a").write_bytes(b"before")
    before = inventory(tmp_path)
    (tmp_path / "a").write_bytes(b"after")
    with pytest.raises(ValueError, match="changed"):
        compressed_snapshot(tmp_path, before)


def test_source_root_must_not_be_link(tmp_path):
    root = tmp_path / "alias"
    root.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match="regular source"):
        inventory(root)


def test_cli_archive_and_fresh_process_recovery_without_source(tmp_path):
    source = tmp_path / "retired"
    source.mkdir()
    planted = b"scratch-fixture-private-data"
    (source / "sample.py").write_bytes(planted)
    keys = tmp_path / "keys"
    output = tmp_path / "encrypted-output"
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"sources": [str(source)], "key_root": str(keys),
                              "archive_root": str(output), "run_id": "scratch-fixture"}))
    command = [sys.executable, "-m", "benchmarks.code_replay.scratch_retention"]
    subprocess.run(command + ["--plan", str(plan)], check=True, capture_output=True, timeout=30)
    manifest = keys / "manifest.encrypted.json"
    for path in [manifest, *output.iterdir()]:
        assert planted not in path.read_bytes()
        assert b"sample.py" not in path.read_bytes()
    (source / "sample.py").unlink()
    source.rmdir()
    result = subprocess.run(command + ["--recover", str(manifest)], check=True,
                            capture_output=True, timeout=30)
    assert json.loads(result.stdout)["archives_verified"] == 1
    bundle = output / "0.encrypted.json"
    value = json.loads(bundle.read_bytes())
    value["run_id"] = "wrong-identity"
    bundle.write_text(json.dumps(value))
    rejected = subprocess.run(command + ["--recover", str(manifest)], capture_output=True, timeout=30)
    assert rejected.returncode != 0
