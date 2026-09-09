from atmem.store.health import BackendHealthStatus, evaluate_backend_health


def test_tls_outage_and_lag_fail_safely() -> None:
    assert evaluate_backend_health("postgres", reachable=True, tls=False, require_tls=True).status is BackendHealthStatus.MISCONFIGURED
    outage = evaluate_backend_health("postgres", reachable=False, tls=True)
    assert outage.safe_action == "use_local_deterministic_fallback"
    lag = evaluate_backend_health("qdrant", reachable=True, tls=True, lag_seconds=9, maximum_lag_seconds=5)
    assert lag.status is BackendHealthStatus.DEGRADED
    assert lag.safe_action == "bypass_derived_backend"
