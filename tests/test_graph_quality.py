from atmem import Memory
from atmem.graph.store import DerivedGraphStore
from atmem.graph.traverse import traverse_authorized


def test_bounded_authorized_multihop_and_generation_rebuild() -> None:
    memory = Memory(":memory:")
    memory.remember("u", "My boss is Sarah.")
    target = memory.remember("u", "Sarah's preferred airport is SEA.")["records"][0]
    graph = DerivedGraphStore(memory.store)
    first = graph.materialize(memory, "u")
    paths = traverse_authorized(memory.store, "u", "my boss airport", max_hops=2, max_candidates=8, max_bytes=1000)
    assert target["id"] in {record_id for path in paths for record_id in path.record_ids}
    second = graph.materialize(memory, "u", rebuild=True)
    assert first["generation_id"] == second["generation_id"]
    memory.close()


def test_cross_scope_and_cycles_do_not_leak() -> None:
    memory = Memory(":memory:")
    memory.remember("one", "My boss is Sarah.")
    memory.remember("two", "Sarah's preferred airport is SECRET.")
    assert "SECRET" not in str([path.to_dict() for path in traverse_authorized(memory.store, "one", "Sarah airport")])
    memory.close()
