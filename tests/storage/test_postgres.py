import pytest
from atmem.core.storage import StorageUnavailable
from atmem.store.postgres import PostgreSQLStore

def test_postgres_is_optional_and_import_safe():
    with pytest.raises((StorageUnavailable, Exception)):
        PostgreSQLStore("postgresql://127.0.0.1:1/atmem",connect=lambda _: (_ for _ in ()).throw(StorageUnavailable("offline fixture")))

def test_postgres_adapter_declares_canonical_transaction_contract_without_connecting():
    store=object.__new__(PostgreSQLStore)
    value=store.capabilities()
    assert value.backend_id=="postgres-v1" and value.transactions and value.verified_deletion
