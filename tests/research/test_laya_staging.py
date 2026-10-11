from __future__ import annotations

import json
from pathlib import Path

import pytest

from research.laya_formation.publication.stage_dataset import validate_local


def test_staging_validator_rejects_uninventoried_files(tmp_path: Path) -> None:
    (tmp_path / "manifests").mkdir()
    (tmp_path / "manifests" / "dataset-manifest.json").write_text(json.dumps({
        "generator_version": "1.3.0", "synthetic_only": True, "files": []
    }))
    (tmp_path / "extra.txt").write_text("extra")
    with pytest.raises(ValueError, match="inventory"):
        validate_local(tmp_path)


def test_staging_validator_rejects_secret_like_content(tmp_path: Path) -> None:
    (tmp_path / "manifests").mkdir()
    text = "api_key=synthetic-but-forbidden"
    path = tmp_path / "README.md"
    path.write_text(text)
    import hashlib
    manifest = {
        "generator_version": "1.3.0",
        "synthetic_only": True,
        "files": [{"path": "README.md", "size": len(text), "sha256": hashlib.sha256(text.encode()).hexdigest()}],
    }
    (tmp_path / "manifests" / "dataset-manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="credential-like"):
        validate_local(tmp_path)


def test_staging_validator_can_ignore_declared_platform_metadata(tmp_path: Path) -> None:
    (tmp_path / "manifests").mkdir()
    (tmp_path / ".gitattributes").write_text("*.jsonl filter=lfs diff=lfs merge=lfs -text\n")
    (tmp_path / "manifests" / "dataset-manifest.json").write_text(json.dumps({
        "generator_version": "1.3.0", "synthetic_only": True, "files": []
    }))
    validate_local(tmp_path, ignored_platform_files=frozenset({".gitattributes"}))


def test_staging_validator_can_ignore_download_cache_only_when_declared(tmp_path: Path) -> None:
    (tmp_path / "manifests").mkdir()
    (tmp_path / ".cache" / "huggingface").mkdir(parents=True)
    (tmp_path / ".cache" / "huggingface" / "download.metadata").write_text("client cache")
    (tmp_path / "manifests" / "dataset-manifest.json").write_text(json.dumps({
        "generator_version": "1.3.0", "synthetic_only": True, "files": []
    }))
    with pytest.raises(ValueError, match="inventory"):
        validate_local(tmp_path)
    validate_local(tmp_path, ignore_snapshot_cache=True)
