from pathlib import Path

from atmem import Memory
from atmem.graph.store import DerivedGraphStore


def test_graph_delete_backup_restore_and_rebuild(tmp_path: Path) -> None:
    memory = Memory(tmp_path / "memory.db")
    record = memory.remember("u", "Sarah's preferred airport is SEA.")["records"][0]
    graph = DerivedGraphStore(memory.store)
    before = graph.materialize(memory, "u")
    memory.store.backup_to(tmp_path / "backup.db")
    memory.forget_record("u", record["id"])
    assert traverse(memory, "SEA") == []
    memory.store.restore_from(tmp_path / "backup.db")
    after = graph.materialize(memory, "u", rebuild=True)
    assert before["graph_sha256"] == after["graph_sha256"]
    memory.close()


def traverse(memory, query):
    from atmem.graph.traverse import traverse_authorized
    return traverse_authorized(memory.store, "u", query)
