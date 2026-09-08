from atmem.invariants.registry import REGISTRY
def test_canonical_authority_authorization_and_revalidation_have_owners():
    for item in ("INV-001","INV-002","INV-003"): assert REGISTRY.by_id(item).assertions
