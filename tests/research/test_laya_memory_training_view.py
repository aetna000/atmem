from atmem.laya_formation.formation_v2 import evaluation_request, operation_question
from research.laya_memory_evidence.training_view import option_ids, to_laya_rows
from research.laya_formation.training.run import _balance_training_rows


def _row():
    question = operation_question()
    request = evaluation_request(
        request_id="request-1", scope_id="scope-1", canonical_generation=4,
        observation={
            "id": "observation-1", "content": "Call me Sara.",
            "speaker_role": "user", "source_digest": "sha256:" + "a" * 64,
        },
        retrieved_memories=[], question=question,
    )
    return {
        "transition_id": "transition-1:operation", "partition": "train",
        "request": request,
        "expected_response": {
            "format": "laya-choice-response-v2", "schema_version": "2.0.0",
            "request_id": "request-1", "question_id": question["question_id"],
            "type": "choice", "choice": "STORE_NEW",
            "probabilities": {
                item["id"]: float(item["id"] == "STORE_NEW")
                for item in question["options"]
            },
            "confidence": 1.0,
        },
    }


def test_stateful_transition_converts_to_upstream_laya_shape():
    row = _row()
    converted = to_laya_rows([row])
    assert converted[0]["expected"] == {"formation.operation.v2": "STORE_NEW"}
    assert converted[0]["state"]["observation"]["content"] == "Call me Sara."
    assert set(converted[0]["state"]) == {"observation", "retrieved_memories"}
    assert converted[0]["questions"]["formation.operation.v2"]["type"] == "choice"
    assert option_ids(row)[0] == "STORE_NEW"


def test_soft_or_malformed_gold_is_rejected():
    row = _row()
    row["expected_response"]["probabilities"]["STORE_NEW"] = 0.8
    row["expected_response"]["probabilities"]["DO_NOT_STORE"] = 0.2
    try:
        to_laya_rows([row])
    except ValueError as exc:
        assert "unique probability argmax" not in str(exc)
    else:
        raise AssertionError("non-one-hot adjudicated target should not be accepted")


def test_training_balance_reuses_only_existing_authentic_rows_with_a_cap():
    common = _row()
    rows = []
    for index in range(10):
        row = {**common, "transition_id": f"majority-{index}"}
        rows.append(row)
    minority = _row()
    minority = {**minority, "transition_id": "minority"}
    minority["expected_response"] = {
        **minority["expected_response"], "choice": "DUPLICATE",
        "probabilities": {
            key: float(key == "DUPLICATE")
            for key in minority["expected_response"]["probabilities"]
        },
    }
    balanced, report = _balance_training_rows([*rows, minority], seed=1)
    assert {row["transition_id"] for row in balanced} <= {
        *(row["transition_id"] for row in rows), "minority",
    }
    sampled = report["formation.operation.v2"]["sampled"]
    assert sampled["DUPLICATE"] == 8
    assert sampled["STORE_NEW"] == 10
