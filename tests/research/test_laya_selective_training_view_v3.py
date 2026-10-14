from __future__ import annotations

import hashlib

from research.laya_memory_evidence.selective_v3 import (
    convert_transition,
    materialize_training_root,
)


def _digest(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


def _row(operation: str = "STORE_NEW", target: str | None = None) -> dict:
    observation = "I prefer concise answers."
    memories = []
    if target:
        memories = [{
            "id": target, "content": "I prefer short replies.",
            "lifecycle": "active", "source_digest": _digest("source"),
            "content_digest": _digest("I prefer short replies."),
            "retrieval_score": 0.9, "memory_class": "preference",
        }]
    return {
        "transition_id": "transition-1:formation.operation.v2",
        "trajectory_id": "trajectory-1", "partition": "train",
        "expected_operation": operation, "expected_target_id": target,
        "expected_post_state_digest": _digest("post"),
        "provenance": {"content_digest": _digest(observation)},
        "request": {
            "request_id": "old", "scope_id": "scope-1",
            "canonical_generation": 2,
            "observation": {
                "id": "observation-1", "content": observation,
                "speaker_role": "user", "source_digest": _digest(observation),
            },
            "retrieved_memories": memories,
            "retrieval_receipt": {"retriever_revision": "retriever-v2"},
        },
        "viewer": {"language": "english"},
    }


def test_projection_does_not_change_authentic_observation() -> None:
    source = _row()
    converted, reason = convert_transition([source])
    assert reason is None
    assert converted is not None
    assert converted["request"]["observation"] == source["request"]["observation"]
    assert converted["derivation"]["synthetic_content"] is False
    assert converted["expected_operation"] == "STORE_NEW"
    assert converted["expected_response"]["choice"] == "option_000"


def test_relational_target_is_bound_but_hidden_from_model_request() -> None:
    source = _row("UPDATE_EXISTING", "canonical-secret-id")
    converted, reason = convert_transition([source])
    assert reason is None
    assert converted is not None
    assert converted["expected_target_id"] == "canonical-secret-id"
    assert converted["request"]["retrieved_memories"][0]["id"] == "target_00"
    assert "canonical-secret-id" not in str(converted["request"])
    selected = converted["expected_response"]["choice"]
    binding = next(
        item for item in converted["v3_option_bindings"]
        if item["option_id"] == selected
    )
    assert binding["operation"] == "UPDATE_EXISTING"
    assert binding["target_memory_id"] == "canonical-secret-id"


def test_review_is_not_converted_to_a_learned_action() -> None:
    converted, reason = convert_transition([_row("REVIEW")])
    assert converted is None
    assert reason == "expected_review_is_not_a_learned_action"


def test_training_root_excludes_sealed_test(tmp_path) -> None:
    projected = tmp_path / "projected"
    projected.mkdir()
    for split in ("train", "validation", "calibration"):
        (projected / f"{split}.jsonl").write_text('{"x":1}\n')
    (projected / "coverage.json").write_text('{"activation_eligible":false}\n')
    source = tmp_path / "source.json"
    source.write_text(
        '{"manifest_digest":"sha256:abc","synthetic_conversation_rows":0,'
        '"locomo_rows":0}\n'
    )
    root = tmp_path / "root"
    manifest = materialize_training_root(
        source_manifest=source, projected_dir=projected, output_root=root,
        learned_operations=("STORE_NEW", "DO_NOT_STORE"),
    )
    assert manifest["sealed_test_rows_included"] == 0
    assert not (root / "records" / "decisions-test.jsonl").exists()
    assert (root / "records" / "decisions-train.jsonl").is_file()
