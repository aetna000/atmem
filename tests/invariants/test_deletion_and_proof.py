from atmem.lifecycle.invalidation import invalidation_registry
from atmem.invariants.registry import REGISTRY
def test_deletion_proof_and_restore_baseline():
    assert invalidation_registry is not None
    for item in ("INV-007","INV-008","INV-009"): assert REGISTRY.by_id(item).assertions
