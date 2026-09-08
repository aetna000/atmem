from atmem.store.health import evaluate_backend_health
from atmem.invariants.registry import REGISTRY
def test_local_fallback_and_upgrade_baseline():
    assert evaluate_backend_health("remote",reachable=False,tls=True).safe_action == "use_local_deterministic_fallback"
    for item in ("INV-010","INV-011"): assert REGISTRY.by_id(item).assertions
