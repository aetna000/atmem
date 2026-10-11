from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from research.laya_formation.training.contracts import canonical_digest
from research.laya_formation.training.sealed import (
    FORMAT_FREEZE,
    FORMAT_PACKET,
    freeze,
    prepare_audit,
)
from research.laya_formation.training.smoke import QUESTION_INSTRUCTIONS


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path) -> dict[str, Path]:
    run_id = "rlcd-410239-test"
    run = tmp_path / run_id
    model = run / "model" / "model.safetensors"
    model.parent.mkdir(parents=True)
    model.write_bytes(b"safe model")
    questions_digest = "1" * 64
    calibration = {
        "model_digest": _sha(model), "questions_digest": questions_digest,
        "digest": "2" * 64,
    }
    _write_json(run / "calibration-bundle.json", calibration)
    _write_json(run / "training-manifest.json", {"questions_digest": questions_digest})
    selection = {
        "selected_run_id": run_id, "selected_objective": "rlcd",
        "policy_digest": "3" * 64,
    }
    selection_path = tmp_path / "selection.json"
    _write_json(selection_path, selection)
    inputs, labels = [], []
    for question_id in QUESTION_INSTRUCTIONS:
        for index in range(80):
            example_id = f"{question_id}-{index:03d}"
            inputs.append({
                "example_id": example_id, "question_id": question_id,
                "authorized_input": {"proposal": "fictional"},
                "choice_ids": ["a", "b"],
            })
            labels.append({
                "example_id": example_id, "expected_choice_ids": ["a"],
                "oracle_receipt": {"rule": "fixture"},
            })
    sealed = tmp_path / "sealed"
    sealed.mkdir()
    inputs_path, labels_path = sealed / "test-inputs.jsonl", sealed / "test-labels.jsonl"
    inputs_path.write_text("".join(json.dumps(row) + "\n" for row in inputs), encoding="utf-8")
    labels_path.write_text("".join(json.dumps(row) + "\n" for row in labels), encoding="utf-8")
    dataset_manifest = tmp_path / "dataset-manifest.json"
    _write_json(dataset_manifest, {"files": [
        {"path": "sealed/test-inputs.jsonl", "size": inputs_path.stat().st_size, "sha256": _sha(inputs_path)},
        {"path": "sealed/test-labels.jsonl", "size": labels_path.stat().st_size, "sha256": _sha(labels_path)},
    ]})
    return {
        "selection": selection_path, "run": run, "dataset_manifest": dataset_manifest,
        "inputs": inputs_path, "labels": labels_path,
    }


def test_freeze_binds_selected_artifacts_without_parsing_sealed_jsonl(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    # Valid sizes and manifest digests are sufficient at freeze time: parsing and
    # byte verification are deliberately deferred until after the one-shot marker.
    fixture["inputs"].write_bytes(b"x" * fixture["inputs"].stat().st_size)
    output = tmp_path / "freeze.json"
    result = freeze(
        selection_path=fixture["selection"], run_root=fixture["run"],
        dataset_manifest_path=fixture["dataset_manifest"],
        sealed_inputs_path=fixture["inputs"], sealed_labels_path=fixture["labels"],
        output_path=output,
    )
    assert result["format"] == FORMAT_FREEZE
    assert result["digest"] == canonical_digest({key: value for key, value in result.items() if key != "digest"})


def test_sealed_audit_is_balanced_and_cannot_be_prepared_twice(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    frozen = tmp_path / "freeze.json"
    freeze(
        selection_path=fixture["selection"], run_root=fixture["run"],
        dataset_manifest_path=fixture["dataset_manifest"],
        sealed_inputs_path=fixture["inputs"], sealed_labels_path=fixture["labels"],
        output_path=frozen,
    )
    packet_path, answer_path, marker = tmp_path / "packet.json", tmp_path / "answer.json", tmp_path / "opened.json"
    packet, answer = prepare_audit(
        freeze_path=frozen, packet_path=packet_path,
        answer_key_path=answer_path, marker_path=marker,
    )
    assert packet["format"] == FORMAT_PACKET
    assert packet["sample_size"] == 400
    assert set(packet["question_counts"].values()) == {80}
    assert all("expected_choice_ids" not in row for row in packet["rows"])
    assert len(answer["rows"]) == 400
    with pytest.raises(FileExistsError):
        prepare_audit(
            freeze_path=frozen, packet_path=tmp_path / "packet-2.json",
            answer_key_path=tmp_path / "answer-2.json", marker_path=marker,
        )
