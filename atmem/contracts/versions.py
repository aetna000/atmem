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
            # Governed Task State (Spec 007). This response is the single
            # authority for what the runtime can actually do: schemas, adapter
            # replies, docs, and tests mirror it and never contradict it.
            "governed_task_state": True,
            # Delivery requires an adapter that can prove exact model-boundary
            # placement and confirm exposure. The generic contract can.
            "governed_task_state_delivery": True,
            # AtMem sees repeated equivalent actions and unmet gates.
            "governed_task_guard_detection": True,
            # It cannot stop a host action. Only an adapter that reports having
            # blocked one may claim enforcement, and none does today.
            "governed_task_guard_enforcement": False,
        },
        "default_vector_provider": "hashing-local-v1",
        "context_serializer": "atmem-context-utf8-v1",
        "task_context_serializer": "atmem-task-context-utf8-v1",
        "governed_task_profiles": ["general-v1"],
    }
