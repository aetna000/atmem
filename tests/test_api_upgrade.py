from atmem.store.sqlite import MIGRATION_REGISTRY,SQLiteStore
def test_api_receipt_migration_is_upgrade_safe(tmp_path):
    store=SQLiteStore(tmp_path/"upgrade.db"); ids=[m[0] for m in MIGRATION_REGISTRY]; assert ids==sorted(ids) and "0120_api_idempotency_receipts" in ids; store.close(); reopened=SQLiteStore(tmp_path/"upgrade.db"); assert reopened.applied_migrations().count("0120_api_idempotency_receipts")==1; reopened.close()
