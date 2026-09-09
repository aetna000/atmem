from __future__ import annotations

import pytest

from atmem.retrieve.support import (
    SUPPORT_AGGREGATION_VERSION,
    aggregate_supporting_evidence,
    aggregation_signal_digest,
)


SCOPE = {
    "subject_id": "user-1",
    "workspace_id": "workspace-1",
    "agent_id": "agent-1",
}


def _aggregate(rows, **scope):
    return aggregate_supporting_evidence(rows, **(scope or SCOPE))


def test_supporting_peers_can_lift_evidence_above_singleton_decoy() -> None:
    rows = _aggregate(
        [
            {"record_id": "supported", "score": 0.80, "source_session_id": "s1"},
            {"record_id": "peer-a", "score": 0.75, "source_session_id": "s1"},
            {"record_id": "peer-b", "score": 0.70, "source_session_id": "s1"},
            {"record_id": "decoy", "score": 0.81, "source_session_id": "s2"},
        ]
    )
    assert [row["record_id"] for row in rows[:2]] == ["supported", "decoy"]
    signals = rows[0]["signals"]
    assert signals["support_aggregation_version"] == SUPPORT_AGGREGATION_VERSION
    assert signals["record_score"] == 0.8
    assert signals["support_score"] == 0.725
    assert signals["aggregate_score"] == 0.82175
    assert signals["eligible_support_count"] == 2


def test_singleton_is_unchanged_and_session_identifier_is_removed() -> None:
    row = _aggregate(
        [{"record_id": "only", "score": 0.7, "source_session_id": "secret-session"}]
    )[0]
    assert row["score"] == 0.7
    assert row["signals"]["support_score"] == 0.0
    assert row["signals"]["eligible_support_count"] == 0
    assert "source_session_id" not in row
    assert "secret-session" not in str(row)


def test_only_two_strongest_peers_contribute() -> None:
    rows = _aggregate(
        [
            {"record_id": "target", "score": 0.5, "source_session_id": "s"},
            {"record_id": "one", "score": 0.9, "source_session_id": "s"},
            {"record_id": "two", "score": 0.7, "source_session_id": "s"},
            {"record_id": "ignored", "score": 0.1, "source_session_id": "s"},
        ]
    )
    target = next(row for row in rows if row["record_id"] == "target")
    assert target["signals"]["support_score"] == 0.8
    assert target["signals"]["eligible_support_count"] == 3


def test_scores_are_clamped_and_ties_are_deterministic() -> None:
    rows = _aggregate(
        [
            {"record_id": "high", "score": 2.0},
            {"record_id": "low", "score": -4.0},
            {"record_id": "tie-b", "score": 0.5},
            {"record_id": "tie-a", "score": 0.5},
        ]
    )
    assert rows[0]["score"] == 1.0
    assert rows[-1]["score"] == 0.0
    assert [row["record_id"] for row in rows[1:3]] == ["tie-b", "tie-a"]


@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), "bad"])
def test_invalid_scores_fail_closed(value) -> None:
    with pytest.raises(ValueError, match="finite number"):
        _aggregate([{"record_id": "bad", "score": value}])


def test_group_ids_are_opaque_and_scope_bound() -> None:
    base = [{"record_id": "one", "score": 0.5, "source_session_id": "session-raw"}]
    first = _aggregate(base)[0]["signals"]["support_group_id"]
    second = _aggregate(base, **{**SCOPE, "workspace_id": "workspace-2"})[0]["signals"][
        "support_group_id"
    ]
    assert first.startswith("sgrp_")
    assert "session-raw" not in first
    assert first != second


def test_signal_digest_excludes_content_and_is_repeatable() -> None:
    rows = _aggregate(
        [{"record_id": "one", "score": 0.5, "content": "private text"}]
    )
    first = aggregation_signal_digest(rows)
    second = aggregation_signal_digest(rows)
    assert first == second
    assert "private" not in first
