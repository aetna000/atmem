from atmem import Memory
from atmem.graph.identity import IdentityService


def test_exact_alias_resolves_and_collision_requires_review() -> None:
    memory = Memory(":memory:")
    memory.remember("u", "My boss is Sarah.")
    identity = IdentityService(memory.store)
    resolved = identity.resolve("u", "my boss")
    assert resolved.status == "resolved"
    entity = memory.store._conn.execute("SELECT * FROM entities WHERE id=?", (resolved.entity_id,)).fetchone()
    other = "ent_ambiguous"
    with memory.store.transaction():
        memory.store._conn.execute("INSERT INTO entities(id,subject_id,canonical,normalized,kind,status,created_at) VALUES(?,?,?,?,?,'active',?)", (other, "u", "Other Sarah", "other sarah", "person", entity["created_at"]))
        memory.store._conn.execute("INSERT INTO entity_aliases(id,entity_id,subject_id,surface,normalized,trust_tier,status,created_at) VALUES(?,?,?,?,?,?,'active',?)", ("als_ambiguous", other, "u", "my boss", "my boss", "trusted_user", entity["created_at"]))
    ambiguous = identity.resolve("u", "my boss")
    assert ambiguous.status == "review_required" and len(ambiguous.candidate_ids) == 2
    memory.close()


def test_rename_preview_commit_and_rollback() -> None:
    memory = Memory(":memory:")
    memory.remember("u", "My boss is Sarah.")
    entity = next(row for row in memory.inspect_graph("u")["entities"] if row["canonical"] == "Sarah")
    service = IdentityService(memory.store)
    preview = service.preview("u", "rename", [entity["id"]], new_name="Sarah Jones")
    receipt = service.commit(preview, confirm_sha256=preview["preview_sha256"], actor="owner", reason="clarify")
    assert service.resolve("u", "Sarah Jones").entity_id == entity["id"]
    assert service.rollback(receipt.mutation_id, actor="owner").status == "rolled_back"
    assert service.resolve("u", "Sarah").entity_id == entity["id"]
    memory.close()
