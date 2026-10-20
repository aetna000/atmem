"""Host-neutral coding-agent memory contracts and service."""

from .contracts import (
    CodeContextPackage,
    CodeContextRequest,
    CodeDeletionReceipt,
    CodeExposureReceipt,
    CodeMemoryCandidate,
    CodeObservation,
    CodeScope,
)

__all__ = [
    "CodeContextPackage",
    "CodeContextRequest",
    "CodeDeletionReceipt",
    "CodeExposureReceipt",
    "CodeMemoryCandidate",
    "CodeObservation",
    "CodeScope",
]
