from __future__ import annotations

from pathlib import Path

import pytest

from benchmarks.laya_formation.retrieval_run import POOL_SIZE, freeze_retrieval_packet, write_frozen_retrieval


def test_retrieval_freeze_is_deterministic_fixed_membership_and_blinded() -> None:
    ids = [f"scenario-{index:06d}" for index in range(20)]
    packet, key = freeze_retrieval_packet(ids)
    again, again_key = freeze_retrieval_packet(ids)
    assert (packet, key) == (again, again_key)
    assert all(len(row["candidate_pool"]) == POOL_SIZE for row in packet["cases"])
    assert all(row["scenario_id"] in row["candidate_pool"] for row in packet["cases"])
    assert "evidence_ids" not in str(packet)
    assert any(row["evidence_ids"] for row in key["labels"])


def test_retrieval_freeze_refuses_overwrite(tmp_path: Path) -> None:
    packet, key = freeze_retrieval_packet([f"scenario-{index:06d}" for index in range(20)])
    root = tmp_path / "frozen"
    write_frozen_retrieval(root, packet, key)
    with pytest.raises(FileExistsError):
        write_frozen_retrieval(root, packet, key)
