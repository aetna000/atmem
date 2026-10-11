"""Lazy, immutable resolution of the optional AtMem Laya model artifact."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
from typing import Any

from .contracts import CalibrationBinding, SUPPORTED_QUESTIONS_DIGEST


MODEL_REPO = "atmem/atmem-laya-formation-model-v1"
MODEL_REVISION = "1698278c4b158fac30e4eb2fefd10ef8b8f873b3"
MODEL_SHA256 = "f2ba3dd7679da45aabab4cac30e9a079baeb2dc98229ff3b1618e6a06fc6d683"
CALIBRATION_DIGEST = "b165d4b7d554cdbda5a889baf7059c3f43ba2774d68754e4fa3aeb63f5f0e067"
EXPORT_DIGEST = "6f7d53c18431c27baa617ab95ebcc4cad669917a6508145fa001eb7c8e799900"


@dataclass(frozen=True, slots=True)
class ArtifactBundle:
    root: Path
    repo_id: str
    revision: str
    model_sha256: str
    questions_digest: str
    calibration_digest: str
    export_digest: str
    calibration: CalibrationBinding
    questions: dict[str, Any]


def dependency_status() -> dict[str, Any]:
    required = ("laya", "torch", "transformers", "safetensors", "huggingface_hub", "numpy")
    versions = {}
    for name in required:
        if importlib.util.find_spec(name) is None:
            versions[name] = None
        else:
            try:
                versions[name] = importlib.metadata.version(name.replace("_", "-"))
            except importlib.metadata.PackageNotFoundError:
                versions[name] = "installed-unversioned"
    return {"available": all(value is not None for value in versions.values()), "versions": versions}


class LayaArtifactResolver:
    def __init__(self, *, repo_id: str = MODEL_REPO, revision: str = MODEL_REVISION) -> None:
        if repo_id != MODEL_REPO or revision != MODEL_REVISION:
            raise ValueError("the v1 Laya profile requires the pinned repository revision")
        self.repo_id = repo_id
        self.revision = revision

    def resolve(
        self, *, local_dir: Path | None = None, allow_download: bool = False,
        token: str | None = None,
    ) -> ArtifactBundle:
        configured = local_dir or (Path(os.environ["ATMEM_LAYA_MODEL_DIR"]) if os.environ.get("ATMEM_LAYA_MODEL_DIR") else None)
        if configured is None:
            if not allow_download:
                raise RuntimeError("Laya artifact is absent; explicit setup/download is required")
            if importlib.util.find_spec("huggingface_hub") is None:
                raise RuntimeError("install atmem[laya-formation] before downloading the Laya artifact")
            from huggingface_hub import snapshot_download
            configured = Path(snapshot_download(
                repo_id=self.repo_id, revision=self.revision, token=token,
                allow_patterns=[
                    "artifact-manifest.json", "calibration.json", "encoder/*", "model.safetensors",
                    "questions.json", "rl_agent_config.json", "tokenizer/*", "training-manifest.json",
                ],
            ))
        return self.verify(configured.resolve())

    def verify(self, root: Path) -> ArtifactBundle:
        manifest_path = root / "artifact-manifest.json"
        if not manifest_path.is_file():
            raise ValueError("Laya artifact manifest is missing")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("format") != "atmem-laya-formation-export-v1" or manifest.get("digest") != EXPORT_DIGEST:
            raise ValueError("Laya artifact export identity mismatch")
        for item in manifest.get("inventory", []):
            path = root / item["path"]
            if not path.is_file() or path.stat().st_size != item["size"]:
                raise ValueError(f"Laya artifact inventory mismatch: {item['path']}")
            hasher = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    hasher.update(block)
            if hasher.hexdigest() != item["sha256"]:
                raise ValueError(f"Laya artifact digest mismatch: {item['path']}")
        if manifest.get("model_sha256") != MODEL_SHA256 or manifest.get("questions_digest") != SUPPORTED_QUESTIONS_DIGEST:
            raise ValueError("Laya model or question binding mismatch")
        if manifest.get("calibration_digest") != CALIBRATION_DIGEST:
            raise ValueError("Laya calibration binding mismatch")
        questions = json.loads((root / "questions.json").read_text(encoding="utf-8"))
        if questions.get("digest") != SUPPORTED_QUESTIONS_DIGEST:
            raise ValueError("question definition digest mismatch")
        calibration_value = json.loads((root / "calibration.json").read_text(encoding="utf-8"))
        if calibration_value.get("digest") != CALIBRATION_DIGEST:
            raise ValueError("calibration bundle digest mismatch")
        calibration = CalibrationBinding(
            model_sha256=calibration_value["model_digest"],
            questions_digest=calibration_value["questions_digest"],
            calibration_digest=calibration_value["digest"], method=calibration_value["method"],
            temperatures=tuple(calibration_value["temperatures"]["by_type"]),
            temperature_by_options=dict(calibration_value["temperatures"]["by_option_bucket"]),
            thresholds=dict(calibration_value["thresholds"]),
        )
        calibration.validate()
        return ArtifactBundle(
            root=root, repo_id=self.repo_id, revision=self.revision,
            model_sha256=MODEL_SHA256, questions_digest=SUPPORTED_QUESTIONS_DIGEST,
            calibration_digest=CALIBRATION_DIGEST, export_digest=EXPORT_DIGEST,
            calibration=calibration, questions=questions["questions"],
        )

    def load_checkpoint(self, bundle: ArtifactBundle) -> tuple[Any, Any, Any]:
        status = dependency_status()
        if not status["available"]:
            raise RuntimeError("install atmem[laya-formation] before loading the optional model")
        if importlib.metadata.version("laya") != "0.4.2":
            raise RuntimeError("Laya runtime version mismatch")
        import laya.train as train
        return train.load_checkpoint(str(bundle.root))
