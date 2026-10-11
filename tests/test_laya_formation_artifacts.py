from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

import atmem.laya_formation.artifacts as artifacts


def _write(path: Path, value: bytes | dict) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = value if isinstance(value, bytes) else (json.dumps(value, sort_keys=True) + "\n").encode()
    path.write_bytes(data)
    return {"path": path.name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def test_base_import_does_not_import_optional_laya_runtime() -> None:
    result = subprocess.run(
        [sys.executable, "-c", "import sys, atmem.laya_formation.artifacts; print('laya' in sys.modules)"],
        text=True, capture_output=True, check=True,
    )
    assert result.stdout.strip() == "False"


def test_absent_artifact_requires_explicit_download() -> None:
    with pytest.raises(RuntimeError, match="explicit setup"):
        artifacts.LayaArtifactResolver().resolve(allow_download=False)


def test_resolver_binds_inventory_model_questions_and_calibration(tmp_path: Path, monkeypatch) -> None:
    model = _write(tmp_path / "model.safetensors", b"safe")
    questions = _write(tmp_path / "questions.json", {
        "digest": artifacts.SUPPORTED_QUESTIONS_DIGEST, "questions": {"operation": {}},
    })
    calibration = _write(tmp_path / "calibration.json", {
        "digest": artifacts.CALIBRATION_DIGEST, "model_digest": model["sha256"],
        "questions_digest": artifacts.SUPPORTED_QUESTIONS_DIGEST,
        "method": "per-question-temperature-and-abstention-v1",
        "temperatures": {"by_type": [1.0, 1.0, 1.0], "by_option_bucket": {"choice:3-5": 1.0}},
        "thresholds": {"choice:3-5": 1.0},
    })
    export_digest = "1" * 64
    manifest = {
        "format": "atmem-laya-formation-export-v1", "digest": export_digest,
        "model_sha256": model["sha256"],
        "questions_digest": artifacts.SUPPORTED_QUESTIONS_DIGEST,
        "calibration_digest": artifacts.CALIBRATION_DIGEST,
        "inventory": [model, questions, calibration],
    }
    _write(tmp_path / "artifact-manifest.json", manifest)
    monkeypatch.setattr(artifacts, "MODEL_SHA256", model["sha256"])
    monkeypatch.setattr(artifacts, "EXPORT_DIGEST", export_digest)
    bundle = artifacts.LayaArtifactResolver().verify(tmp_path)
    assert bundle.model_sha256 == model["sha256"]
    assert bundle.calibration.thresholds == {"choice:3-5": 1.0}
    (tmp_path / "model.safetensors").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="inventory mismatch"):
        artifacts.LayaArtifactResolver().verify(tmp_path)


def test_laya_extra_is_optional_and_not_a_base_dependency() -> None:
    try:
        import tomllib
    except ModuleNotFoundError:  # Python 3.10 compatibility
        import tomli as tomllib
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert not any("laya" in item.casefold() for item in data["project"]["dependencies"])
    extra = data["project"]["optional-dependencies"]["laya-formation"]
    assert "laya==0.4.2" in extra
