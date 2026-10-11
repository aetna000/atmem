from __future__ import annotations

import json
from types import SimpleNamespace

from research.laya_formation.dataset.audit import verify_audit_review
from research.laya_formation.dataset.openai_review import review_packet


class FakeResponses:
    def __init__(self) -> None:
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        rows = json.loads(kwargs["input"])["rows"]
        output = {
            "rows": [
                {
                    "example_id": row["example_id"],
                    "selected_choice_ids": [row["choice_ids"][0]],
                    "critical_findings": [],
                }
                for row in rows
            ]
        }
        usage = SimpleNamespace(to_dict=lambda: {"input_tokens": 10, "output_tokens": 5})
        return SimpleNamespace(
            id=f"response-{len(self.calls)}",
            status="completed",
            output_text=json.dumps(output),
            usage=usage,
        )


def test_openai_reviewer_is_chunked_blinded_and_signed() -> None:
    packet = {
        "format": "atmem-laya-blinded-audit-packet-v1",
        "rows": [
            {
                "example_id": f"example-{index}",
                "question_id": "operation",
                "authorized_input": {"initial_state": {}, "evidence": []},
                "choice_ids": ["ADD", "REJECT"],
                "safety_tags": ["synthetic"],
            }
            for index in range(5)
        ],
    }
    responses = FakeResponses()
    client = SimpleNamespace(responses=responses)
    review = review_packet(packet, client=client, model="review-model", chunk_size=2)
    verify_audit_review(review)
    assert len(responses.calls) == 3
    assert len(review["rows"]) == 5
    assert review["reviewer"]["answer_key_accessed"] is False
    assert all(call["store"] is False for call in responses.calls)
    assert all("expected_choice_ids" not in call["input"] for call in responses.calls)
