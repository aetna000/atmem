import sqlite3

import pytest

from research.laya_memory_evidence.freeze_snapshot import _split_scope_manifest


def _work_db(path, groups, prefixes=()):
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE scale_group(
          group_id TEXT PRIMARY KEY, split_family TEXT NOT NULL,
          scope_id TEXT NOT NULL, history_count INTEGER NOT NULL,
          challenge_count INTEGER NOT NULL
        );
        CREATE TABLE baseline_observation(
          observation_id TEXT PRIMARY KEY, group_id TEXT NOT NULL,
          scope_id TEXT NOT NULL
        );
        """
    )
    connection.executemany("INSERT INTO scale_group VALUES (?,?,?,?,?)", groups)
    connection.executemany("INSERT INTO baseline_observation VALUES (?,?,?)", prefixes)
    connection.commit()
    connection.close()


def test_split_scope_manifest_binds_prefix_to_one_family(tmp_path):
    path = tmp_path / "work.sqlite3"
    _work_db(
        path,
        [("g1", "train", "scope-1", 1, 1), ("g2", "sealed_test", "scope-2", 0, 1)],
        [("b1", "g1", "scope-1")],
    )
    result = _split_scope_manifest(path)
    assert result["scope_count"] == 2
    assert result["conflict_count"] == 0


def test_split_scope_manifest_rejects_scope_crossing_families(tmp_path):
    path = tmp_path / "work.sqlite3"
    _work_db(
        path,
        [("g1", "train", "scope-1", 0, 1), ("g2", "sealed_test", "scope-1", 0, 1)],
    )
    with pytest.raises(RuntimeError, match="scope/split-family isolation"):
        _split_scope_manifest(path)


def test_split_scope_manifest_rejects_mismatched_prefix_scope(tmp_path):
    path = tmp_path / "work.sqlite3"
    _work_db(
        path,
        [("g1", "train", "scope-1", 1, 1)],
        [("b1", "g1", "scope-other")],
    )
    with pytest.raises(RuntimeError, match="scope/split-family isolation"):
        _split_scope_manifest(path)
