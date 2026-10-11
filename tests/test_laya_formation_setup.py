from __future__ import annotations

from pathlib import Path

import pytest

from atmem.laya_formation.artifacts import ArtifactBundle
from atmem.laya_formation.contracts import CalibrationBinding
from atmem.laya_formation.setup import LayaProfileManager


def bundle(root: Path) -> ArtifactBundle:
    calibration = CalibrationBinding(
        "f" * 64, "7a3cd0e13d99db02a1e53e51a63fad921e754ac5bbc2376b8a888c1033900f0e",
        "b165d4b7d554cdbda5a889baf7059c3f43ba2774d68754e4fa3aeb63f5f0e067",
        "per-question-temperature-and-abstention-v1", (1.0, 1.0, 1.0),
        {"choice:3-5": 1.0}, {"choice:3-5": 1.0},
    )
    return ArtifactBundle(
        root=root, repo_id="atmem/atmem-laya-formation-model-v1", revision="1" * 40,
        model_sha256=calibration.model_sha256, questions_digest=calibration.questions_digest,
        calibration_digest=calibration.calibration_digest, export_digest="e" * 64,
        calibration=calibration, questions={"operation": {}},
    )


class Resolver:
    def __init__(self, value): self.value, self.calls = value, []
    def resolve(self, **kwargs): self.calls.append(kwargs); return self.value
    def verify(self, root): self.calls.append({"verify": root}); return self.value


class Engine:
    calls = []
    def __init__(self, value, *, device): self.calls.append((value, device)); self.device = device
    def close(self): self.calls.append("closed")


def test_setup_is_previewed_inactive_then_explicitly_activated_and_exactly_rolled_back(tmp_path: Path) -> None:
    model = tmp_path / "model"
    model.mkdir()
    resolver = Resolver(bundle(model))
    manager = LayaProfileManager(
        tmp_path / "profile", resolver=resolver, engine_factory=Engine,
        dependency_probe=lambda: {"available": True, "versions": {"laya": "0.4.2"}},
    )
    preview = manager.preview(local_dir=model, device="cpu", escalation_enabled=False)
    assert preview["changes"]["active"] is False
    assert manager.status()["configured"] is False

    staged = manager.setup(local_dir=model, allow_download=False, device="cpu", escalation_enabled=False)
    assert staged["active"] is False and staged["verified"] is True
    before = manager.config_path.read_bytes()
    with pytest.raises(ValueError, match="explicit confirmation"):
        manager.activate(confirmed=False)
    active = manager.activate(confirmed=True)
    assert active["active"] is True
    assert Engine.calls[-1] == "closed"
    rolled_back = manager.rollback(confirmed=True)
    assert rolled_back["active"] is False
    assert manager.config_path.read_bytes() == before


def test_status_and_doctor_are_read_only_and_report_fallback_readiness(tmp_path: Path) -> None:
    model = tmp_path / "model"
    model.mkdir()
    resolver = Resolver(bundle(model))
    manager = LayaProfileManager(
        tmp_path / "profile", resolver=resolver, engine_factory=Engine,
        dependency_probe=lambda: {"available": True, "versions": {"laya": "0.4.2"}},
    )
    manager.setup(local_dir=model, allow_download=False, device="cpu", escalation_enabled=True)
    before = manager.config_path.read_bytes()
    status = manager.status()
    doctor = manager.doctor()
    assert status["model_revision"] == "1" * 40
    assert status["fallback_ready"] is True
    assert doctor["ready_to_activate"] is True
    assert doctor["calibration_state"] == "verified"
    assert manager.config_path.read_bytes() == before
