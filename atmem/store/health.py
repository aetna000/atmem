"""Privacy-safe storage health and deterministic degradation decisions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class BackendHealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    MISCONFIGURED = "misconfigured"


@dataclass(frozen=True, slots=True)
class BackendHealth:
    backend_id: str
    status: BackendHealthStatus
    tls: bool | None
    lag_seconds: float | None
    reason_codes: tuple[str, ...]
    safe_action: str
    format: str = "atmem-storage-health-v1"

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["status"] = self.status.value
        value["reason_codes"] = list(self.reason_codes)
        return value


def evaluate_backend_health(
    backend_id: str,
    *,
    reachable: bool,
    tls: bool | None,
    lag_seconds: float | None = None,
    maximum_lag_seconds: float = 5.0,
    require_tls: bool = False,
) -> BackendHealth:
    if require_tls and tls is not True:
        return BackendHealth(backend_id, BackendHealthStatus.MISCONFIGURED, tls, lag_seconds, ("tls_required",), "refuse_startup")
    if not reachable:
        return BackendHealth(backend_id, BackendHealthStatus.UNAVAILABLE, tls, lag_seconds, ("connection_unavailable",), "use_local_deterministic_fallback")
    if lag_seconds is not None and lag_seconds > maximum_lag_seconds:
        return BackendHealth(backend_id, BackendHealthStatus.DEGRADED, tls, lag_seconds, ("replica_or_index_lag",), "bypass_derived_backend")
    return BackendHealth(backend_id, BackendHealthStatus.HEALTHY, tls, lag_seconds, ("verified",), "none")
