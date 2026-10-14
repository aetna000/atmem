from research.laya_memory_evidence.challenge_worker import _post_state_digest
import json

from research.laya_memory_evidence.evaluate_laya import compare, summarize


def _state_fields(operation, content="candidate"):
    records = []
    return {
        "expected_operation": operation, "expected_target_id": None,
        "canonical_state_digest": _post_state_digest(
            records, {"operation": "DUPLICATE", "target_memory_id": None,
                      "memory_class": "unknown"}, "",
        ),
        "canonical_records": records, "observation_content": content,
        "expected_post_state_digest": _post_state_digest(
            records, {"operation": operation, "target_memory_id": None,
                      "memory_class": "preference"}, content,
        ),
    }


def test_stateful_summary_requires_every_typed_answer_for_full_transition():
    rows = [
        {
            "source_transition_id": "t1", "status": "completed", "correct": True,
            "question_id": "formation.operation.v2", "expected_answer": "STORE_NEW",
            "predicted_answer": "STORE_NEW", "probabilities": {"STORE_NEW": 1.0},
            "confidence": 1.0, "latency_ms": 4.0, "abstained": False,
            **_state_fields("STORE_NEW"),
        },
        {
            "source_transition_id": "t1", "status": "completed", "correct": False,
            "question_id": "formation.memory_class.v2", "expected_answer": "preference",
            "predicted_answer": "episode", "probabilities": {"preference": 0.2, "episode": 0.8},
            "confidence": 0.8, "latency_ms": 5.0, "abstained": False,
            **_state_fields("STORE_NEW"),
        },
        {
            "source_transition_id": "t2", "status": "completed", "correct": True,
            "question_id": "formation.operation.v2", "expected_answer": "DUPLICATE",
            "predicted_answer": "DUPLICATE", "probabilities": {"DUPLICATE": 1.0},
            "confidence": 1.0, "latency_ms": 6.0, "abstained": False,
            **_state_fields("DUPLICATE"),
        },
    ]
    result = summarize(rows)
    assert result["transitions"] == 2
    assert result["fully_correct_transitions"] == 1
    assert result["fully_correct_rate"] == 0.5
    assert result["false_store_count"] == 0


def test_paired_comparison_allows_different_dynamic_question_paths(tmp_path):
    common = {
        "source_transition_id": "t1", "status": "completed", "correct": True,
        "expected_answer": "STORE_NEW", "expected_operation": "STORE_NEW",
        "predicted_answer": "STORE_NEW", "probabilities": {"STORE_NEW": 1.0},
        "confidence": 1.0, "latency_ms": 1.0, "abstained": False,
        "ruling_operation": "STORE_NEW", "ruling_target_id": None,
        "ruling_memory_class": "preference", **_state_fields("STORE_NEW"),
    }
    base_rows = [{**common, "example_id": "t1:operation", "question_id": "formation.operation.v2"}]
    tuned_rows = [
        {**common, "example_id": "t1:operation", "question_id": "formation.operation.v2"},
        {**common, "example_id": "t1:class", "question_id": "formation.memory_class.v2",
         "expected_answer": "preference", "predicted_answer": "preference",
         "probabilities": {"preference": 1.0}},
    ]
    base = tmp_path / "base.jsonl"
    tuned = tmp_path / "tuned.jsonl"
    base.write_text("".join(json.dumps(row) + "\n" for row in base_rows))
    tuned.write_text("".join(json.dumps(row) + "\n" for row in tuned_rows))
    result = compare(base, tuned, tmp_path / "comparison.json", samples=100)
    assert result["base"]["transitions"] == result["tuned"]["transitions"] == 1
