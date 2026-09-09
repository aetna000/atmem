"""FR-009: policy changes must invalidate or repair affected derived vectors."""

from __future__ import annotations

import json

from atmem import Memory
from atmem.semantic import SemanticIndex, default_index_path, inspect_semantic_health


class FixtureEmbedder:
    @property
    def identity(self):
        return {
            "provider": "sentence-transformers",
            "model": "fixture/local-model",
            "version": "fixture-1",
            "normalization": "l2",
        }

    def embed_documents(self, texts):
        return [[1.0, 0.0] for _ in texts]

    def embed_query(self, _text):
        return [1.0, 0.0]


def _seeded(tmp_path):
    database = tmp_path / "memory.db"
    memory = Memory(database)
    memory.remember(
        "u1",
        "I prefer aisle seats.",
        interpreted_fact="I prefer aisle seats.",
        interpreted_fact_key="travel.seat",
    )
    memory.close()
    return database


def _built(database):
    memory = Memory(database, auto_vectors=False)
    index = SemanticIndex(default_index_path(database), policy=memory.policy)
    index.build(memory, "u1", FixtureEmbedder())
    return memory, index


def test_epoch_records_the_policy_it_was_derived_under(tmp_path) -> None:
    database = _seeded(tmp_path)
    memory, index = _built(database)
    try:
        epoch = index.active_epoch("u1")
        assert epoch["identity"]["policy_sha256"] == index.policy_fingerprint()
    finally:
        index.close()
        memory.close()


def test_policy_fingerprint_never_contains_key_material(tmp_path) -> None:
    database = _seeded(tmp_path)
    memory, index = _built(database)
    try:
        identity = json.dumps(index.active_epoch("u1")["identity"])
        assert "key" not in json.loads(identity) or "policy_sha256" in json.loads(identity)
        # The digest is 64 hex characters and carries no readable policy detail.
        digest = index.policy_fingerprint()
        assert len(digest) == 64 and all(c in "0123456789abcdef" for c in digest)
    finally:
        index.close()
        memory.close()


def test_policy_change_marks_the_epoch_stale_and_health_explains_it(tmp_path) -> None:
    database = _seeded(tmp_path)
    memory, index = _built(database)
    try:
        assert inspect_semantic_health(index, memory, "u1").status.value == "healthy"

        # Simulate a household policy change by rewriting the recorded digest.
        epoch = index.active_epoch("u1")
        identity = dict(epoch["identity"])
        identity["policy_sha256"] = "f" * 64
        index._conn.execute(
            "UPDATE vector_epochs SET identity_json = ? WHERE epoch_id = ?",
            (json.dumps(identity, sort_keys=True, separators=(",", ":")), epoch["epoch_id"]),
        )
        index._conn.commit()

        health = inspect_semantic_health(index, memory, "u1")
        assert health.status.value == "stale"
        assert [reason.value for reason in health.reasons] == ["policy_changed"]
        assert "rebuild" in health.actions
    finally:
        index.close()
        memory.close()


def test_invalidate_for_policy_change_marks_only_mismatched_epochs(tmp_path) -> None:
    database = _seeded(tmp_path)
    memory, index = _built(database)
    try:
        unchanged = index.invalidate_for_policy_change("u1")
        assert unchanged["invalidated_epoch_ids"] == []

        epoch = index.active_epoch("u1")
        identity = dict(epoch["identity"])
        identity["policy_sha256"] = "f" * 64
        index._conn.execute(
            "UPDATE vector_epochs SET identity_json = ? WHERE epoch_id = ?",
            (json.dumps(identity, sort_keys=True, separators=(",", ":")), epoch["epoch_id"]),
        )
        index._conn.commit()

        result = index.invalidate_for_policy_change("u1")
        assert result["invalidated_epoch_ids"] == [epoch["epoch_id"]]
        assert index.active_epoch("u1")["dirty"] is True
    finally:
        index.close()
        memory.close()


def test_legacy_epoch_without_a_policy_digest_is_not_falsely_aged(tmp_path) -> None:
    database = _seeded(tmp_path)
    memory, index = _built(database)
    try:
        epoch = index.active_epoch("u1")
        identity = {
            key: value
            for key, value in epoch["identity"].items()
            if key != "policy_sha256"
        }
        index._conn.execute(
            "UPDATE vector_epochs SET identity_json = ? WHERE epoch_id = ?",
            (json.dumps(identity, sort_keys=True, separators=(",", ":")), epoch["epoch_id"]),
        )
        index._conn.commit()

        assert inspect_semantic_health(index, memory, "u1").status.value == "healthy"
        assert index.invalidate_for_policy_change("u1")["invalidated_epoch_ids"] == []
    finally:
        index.close()
        memory.close()
