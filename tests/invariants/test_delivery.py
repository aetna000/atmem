from atmem.adapters.base import CONTEXT_PREAMBLE
from atmem.invariants.registry import REGISTRY
def test_explicit_delivery_receipt_and_history_baseline():
    assert "governed memory" in CONTEXT_PREAMBLE
    for item in ("INV-004","INV-005","INV-006"): assert REGISTRY.by_id(item).assertions
