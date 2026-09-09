from __future__ import annotations

from typing import Any

from atmem.core.storage import CanonicalStore


def assert_canonical_conformance(store: Any) -> None:
    assert isinstance(store, CanonicalStore)
    capability = store.capabilities()
    assert capability.role == "canonical"
    assert capability.transactions
    assert capability.verified_deletion
    assert store.record_generation("conformance-empty") == 0
    assert store.get_record("conformance-empty", "missing") is None
    assert store.list_records("conformance-empty") == []
