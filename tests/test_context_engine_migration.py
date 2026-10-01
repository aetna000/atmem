from __future__ import annotations

import sqlite3

import pytest

from atmem.context_engine.formation import FormationManager, SourceEpisode, SourcePart
from atmem.contracts.models import AuthorityScope
from atmem.store.sqlite import MIGRATION_REGISTRY, SQLiteStore


SCOPE = AuthorityScope(subject_id="person-1", agent_id="agent-a", workspace_id="work-1")


def test_published_plaintext_store_gets_inert_v3_schema_on_upgrade(tmp_path) -> None:
    path = tmp_path / "published.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE episodes(id TEXT PRIMARY KEY, subject_id TEXT NOT NULL, session_id TEXT, turn_id TEXT, message TEXT NOT NULL, source_type TEXT NOT NULL, created_at TEXT NOT NULL, raw TEXT NOT NULL DEFAULT '{}')")
    store = SQLiteStore(path)
    try:
        assert "0400_context_engine_generations" in store.applied_migrations()
        assert store.context_engine_storage_ready()["ready"] is False
        assert store.context_engine_storage_ready()["reason"] == "encrypted_household_required"
    finally:
        store.close()


def test_generation_activation_requires_verified_complete_generation() -> None:
    store = SQLiteStore(":memory:")
    try:
        manager = FormationManager(store)
        generation = manager.begin_generation(SCOPE, profile_id="context-fast")
        with pytest.raises(RuntimeError, match="verified"):
            manager.activate_generation(generation)
        manager.verify_generation(generation)
        manager.activate_generation(generation)
        assert manager.active_generation(SCOPE)["generation_id"] == generation
    finally:
        store.close()


def test_rebuild_preserves_unit_and_range_identity_but_not_generation_identity() -> None:
    store = SQLiteStore(":memory:")
    try:
        manager = FormationManager(store)
        source = manager.retain_source(SourceEpisode(
            episode_id="episode-rebuild", scope=SCOPE,
            parts=(SourcePart("text", 0, "text", "text/plain", b"age is 45"),),
        ))
        generation = manager.begin_generation(SCOPE, profile_id="context-fast")
        evidence_range = manager.add_range(source, "text", 0, 9)
        unit = manager.add_unit(
            generation, kind="fact", ranges=(evidence_range,),
            compact_value={"subject": "person-1", "relation": "age", "value": 45},
        )
        manager.verify_generation(generation)
        rebuilt = manager.rebuild_generation(generation)
        assert rebuilt != generation
        assert manager.get_unit(unit, generation_id=rebuilt)["ranges"][0]["range_id"] == evidence_range.range_id
        manager.verify_generation(rebuilt)
    finally:
        store.close()


def test_interrupted_backfill_resumes_without_duplicate_source() -> None:
    store = SQLiteStore(":memory:")
    try:
        episode_id = store.insert_episode(
            subject_id=SCOPE.subject_id,
            session_id="session-1",
            turn_id="turn-1",
            message="remember this exactly",
            source_type="test",
        )
        manager = FormationManager(store)
        assert manager.backfill_legacy_sources(SCOPE, limit=1)["processed"] == 1
        assert manager.backfill_legacy_sources(SCOPE, limit=1)["processed"] == 0
        rows = store._conn.execute(
            "SELECT COUNT(*) AS n FROM context_source_episodes WHERE legacy_episode_id=?",
            (episode_id,),
        ).fetchone()
        assert int(rows["n"]) == 1
    finally:
        store.close()


def test_context_engine_migrations_are_append_only_and_ordered() -> None:
    identifiers = [item[0] for item in MIGRATION_REGISTRY]
    assert identifiers == sorted(identifiers)
    assert identifiers[-1] == "0400_context_engine_generations"
