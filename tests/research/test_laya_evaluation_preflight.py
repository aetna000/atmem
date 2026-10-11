from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks.laya_formation.preflight import (
    PER_QUESTION, QUESTION_INSTRUCTIONS, freeze_cases, public_manifest, write_frozen,
)


def make_files(tmp_path: Path) -> tuple[Path, Path]:
    inputs, labels = [], []
    for index in range(PER_QUESTION + 1):
        for question_id in QUESTION_INSTRUCTIONS:
            example_id = f"scenario-{index:03d}:{question_id}"
            inputs.append({
                "example_id": example_id, "scenario_id": example_id.split(":")[0],
                "question_id": question_id, "authorized_input": {"index": index},
                "choice_ids": ["A", "B"],
            })
            labels.append({"example_id": example_id, "expected_choice_ids": ["A"]})
    inputs_path, labels_path = tmp_path / "inputs.jsonl", tmp_path / "labels.jsonl"
    inputs_path.write_text("".join(json.dumps(row) + "\n" for row in inputs))
    labels_path.write_text("".join(json.dumps(row) + "\n" for row in labels))
    return inputs_path, labels_path


def test_freeze_is_deterministic_balanced_and_keeps_answers_separate(tmp_path: Path) -> None:
    inputs, labels = make_files(tmp_path)
    first, first_key = freeze_cases(inputs, labels)
    second, second_key = freeze_cases(inputs, labels)
    assert first == second and first_key == second_key
    assert first["case_count"] == PER_QUESTION * len(QUESTION_INSTRUCTIONS)
    assert first["scenario_count"] == PER_QUESTION
    assert set(first["question_counts"].values()) == {PER_QUESTION}
    assert all("expected" not in row for row in first["cases"])
    manifest = public_manifest(first, first_key)
    assert manifest["packet_digest"] == first["digest"]
    assert "labels" not in manifest


def test_frozen_output_is_exclusive(tmp_path: Path) -> None:
    inputs, labels = make_files(tmp_path)
    packet, key = freeze_cases(inputs, labels)
    packet_path, key_path = tmp_path / "packet.json", tmp_path / "key.json"
    write_frozen(packet_path, key_path, packet, key)
    with pytest.raises(FileExistsError):
        write_frozen(packet_path, key_path, packet, key)


def test_mismatched_label_identity_fails_closed(tmp_path: Path) -> None:
    inputs, labels = make_files(tmp_path)
    rows = labels.read_text().splitlines()
    labels.write_text("\n".join(rows[:-1]) + "\n")
    with pytest.raises(ValueError, match="identities differ"):
        freeze_cases(inputs, labels)
