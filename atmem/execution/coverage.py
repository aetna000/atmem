"""Honest adapter coverage manifests for the M0 execution profile."""

from __future__ import annotations

from typing import Iterable


def coverage_manifest(
    *, adapter: str, version: str, configuration: str,
    supported: Iterable[str], observed: Iterable[str], enforced: Iterable[str] = (),
    gaps: Iterable[str] = (), verified_at: str | None = None,
) -> dict[str, object]:
    supported_set = sorted(set(supported))
    observed_set = sorted(set(observed))
    return {
        "format": "atmem-execution-coverage-v1",
        "adapter": adapter,
        "adapter_version": version,
        "configuration": configuration,
        "supported_boundaries": supported_set,
        "observed_boundaries": observed_set,
        "enforced_boundaries": sorted(set(enforced)),
        "omitted_boundaries": sorted(set(supported_set) - set(observed_set)),
        "gaps": sorted(set(gaps)),
        "verified_at": verified_at,
        "assurance": "observed" if verified_at else "declared",
    }
