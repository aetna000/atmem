from pathlib import Path

from atmem import Memory
from atmem.store.sqlite import MIGRATION_REGISTRY, SQLiteStore
from tests.storage.conformance import assert_canonical_conformance


def test_sqlite_conformance_and_append_only_registry() -> None:
    store = SQLiteStore(":memory:")
    assert_canonical_conformance(store)
    identifiers = [item[0] for item in MIGRATION_REGISTRY]
    assert identifiers == sorted(identifiers)
    assert identifiers[0] == "0000_pre_registry_baseline"
    assert set(store.applied_migrations()) == set(identifiers)
    store.close()


def test_sqlite_backup_restore_round_trip(tmp_path: Path) -> None:
    original = Memory(tmp_path / "original.db")
    record = original.remember("alice", "My city is Sydney.")["records"][0]
    receipt = original.store.backup_to(tmp_path / "backup.db")
    assert receipt["integrity"] == "ok"
    restored = SQLiteStore(tmp_path / "restored.db")
    outcome = restored.restore_from(tmp_path / "backup.db")
    assert outcome["integrity"] == "ok"
    assert restored.get_record("alice", record["id"])["content"] == record["content"]
    restored.close()
    original.close()
