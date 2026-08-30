"""Protocol capability negotiation."""

from __future__ import annotations

from typing import Any


PROTOCOL_VERSION = "1"


def capabilities() -> dict[str, Any]:
    return {
        "format": "atmem-capabilities-v1",
        "protocol_versions": [PROTOCOL_VERSION],
        "features": {
            "source_capture": True,
            "proposal_admission": True,
            "governed_recall": True,
            "stable_context": True,
            "exposure_receipts": True,
            "default_local_vectors": True,
            "external_reranking": False,
            "external_cleanup_acknowledgement": False,
        },
        "default_vector_provider": "hashing-local-v1",
        "context_serializer": "atmem-context-utf8-v1",
    }
