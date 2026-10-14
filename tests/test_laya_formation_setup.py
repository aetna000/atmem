from __future__ import annotations

from pathlib import Path

import pytest

from atmem.laya_formation.artifacts import ArtifactBundle, runtime_compatibility
from atmem.laya_formation.contracts import CalibrationBinding, SUPPORTED_QUESTIONS_DIGEST
from atmem.laya_formation.setup import LayaProfileManager


def bundle(root: Path) -> ArtifactBundle:
    calibration = CalibrationBinding(
        "f" * 64, SUPPORTED_QUESTIONS_DIGEST,
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


def shadow_receipt(model: ArtifactBundle) -> dict:
    return {
        "format": "atmem-laya-shadow-qualification-v2",
        "model_repo": model.repo_id, "model_revision": model.revision,
        "cases_total": 10, "cases_completed": 10,
        "unsafe_mutations": 0, "double_classifications": 0,
        "receipt_digest": "sha256:" + "a" * 64,
    }


def test_runtime_compatibility_rejects_stale_or_unbounded_shared_environments() -> None:
    valid = {
        "laya": "0.4.2", "torch": "2.14.1",
        "transformers": "4.57.6", "safetensors": "0.8.0",
        "huggingface_hub": "0.36.2", "numpy": "2.4.6",
    }
    assert runtime_compatibility(valid) == {}
    invalid = {**valid, "torch": "2.2.2", "transformers": "5.12.1"}
    errors = runtime_compatibility(invalid)
    assert "requires >=2.3.0,<3.0.0" in errors["torch"]
    assert "requires >=4.57.1,<5.0.0" in errors["transformers"]


def test_doctor_reports_exact_runtime_repair_for_incompatible_stack(tmp_path: Path) -> None:
    model = tmp_path / "model"
    model.mkdir()
    probe = {
        "available": False,
        "versions": {"laya": None, "torch": "2.2.2"},
        "compatibility_errors": {"laya": "missing", "torch": "too old"},
        "repair_command": "python -m pip install --upgrade 'atmem[laya-formation]'",
    }
    manager = LayaProfileManager(
        tmp_path / "profile", resolver=Resolver(bundle(model)),
        engine_factory=Engine, dependency_probe=lambda: probe,
    )
    manager.setup(local_dir=model, device="cpu")
    doctor = manager.doctor()
    assert doctor["ready_to_activate"] is False
    assert doctor["error_code"] == "runtime_dependencies_incompatible"
    assert doctor["compatibility_errors"] == probe["compatibility_errors"]
    assert "atmem[laya-formation]" in doctor["repair_command"]


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
    with pytest.raises(RuntimeError, match="shadow qualification"):
        manager.activate(confirmed=True)
    manager.qualify_shadow(shadow_receipt(resolver.value), confirmed=True)
    active = manager.activate(confirmed=True)
    assert active["active"] is True
    assert Engine.calls[-1] == "closed"
    rolled_back = manager.rollback(confirmed=True)
    assert rolled_back["active"] is False
    assert manager.config_path.read_bytes() != before
    assert rolled_back["shadow_qualified"] is True


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
    assert doctor["ready_to_activate"] is False
    assert manager.config_path.read_bytes() == before
    manager.qualify_shadow(shadow_receipt(resolver.value), confirmed=True)
    assert manager.doctor()["ready_to_activate"] is True
    assert doctor["calibration_state"] == "verified"


def test_selecting_deterministic_deactivates_without_deleting_staged_model(tmp_path: Path) -> None:
    model = tmp_path / "model"
    model.mkdir()
    resolver = Resolver(bundle(model))
    manager = LayaProfileManager(
        tmp_path / "profile", resolver=resolver, engine_factory=Engine,
        dependency_probe=lambda: {"available": True, "versions": {"laya": "0.4.2"}},
    )
    manager.setup(local_dir=model, device="cpu")
    manager.qualify_shadow(shadow_receipt(resolver.value), confirmed=True)
    manager.activate(confirmed=True)

    selected = manager.select_deterministic(confirmed=True)

    assert selected["active"] is False
    assert selected["profile"] == "deterministic"
    assert selected["configured_profile"] == "laya-formation-v2"
    assert manager.config_path.is_file()
    restored = manager.rollback(confirmed=True)
    assert restored["active"] is True
