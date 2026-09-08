from atmem.store.sqlite import MIGRATION_REGISTRY,SQLiteStore
def test_lifecycle_migration_reopens_without_replay(tmp_path):
    path=tmp_path/"old.db"; first=SQLiteStore(path); first.close(); second=SQLiteStore(path); assert "0150_memory_lifecycle" in second.applied_migrations(); assert [x[0] for x in MIGRATION_REGISTRY]==sorted(x[0] for x in MIGRATION_REGISTRY); second.close()
