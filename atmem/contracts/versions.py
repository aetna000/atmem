"""Protocol capability negotiation."""

from __future__ import annotations

from typing import Any


PROTOCOL_VERSION = "1"


def capabilities() -> dict[str, Any]:
    # Derived, not asserted. AtMem cannot stop a host action, so enforcement is
    # reported only while an adapter has registered a real, evidence-backed
    # blocking boundary. Editing a constant cannot turn this on.
    from atmem.task_state.enforcement import (
        agent_delta_tool_adapters,
        enforcing_adapters,
        guard_enforcement_available,
        host_proposal_adapters,
        session_binding_adapters,
    )

    enforcement = guard_enforcement_available()
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
            # It cannot stop a host action. Only an adapter that registers a
            # real blocking boundary flips this, and none does today.
            "governed_task_guard_enforcement": enforcement,
            # Amendment A. These say the runtime implements the capability;
            # whether a given host has it is per-adapter data below, because
            # one adapter may supply a reset signal or register the delta tool
            # while another does not, and one flag cannot describe both.
            "governed_task_session_binding": bool(session_binding_adapters()),
            "governed_task_host_proposal": bool(host_proposal_adapters()),
            "governed_task_agent_delta_tool": bool(agent_delta_tool_adapters()),
        },
        "default_vector_provider": "hashing-local-v1",
        "context_serializer": "atmem-context-utf8-v1",
        "task_context_serializer": "atmem-task-context-utf8-v1",
        "governed_task_profiles": ["general-v1"],
        "governed_task_enforcing_adapters": list(enforcing_adapters()),
        # Adapter-keyed, following the enforcing-adapters pattern above. An
        # adapter response derives its own availability from these rather than
        # from the global flags.
        "governed_task_session_binding_adapters": list(session_binding_adapters()),
        "governed_task_host_proposal_adapters": list(host_proposal_adapters()),
        "governed_task_agent_delta_tool_adapters": list(agent_delta_tool_adapters()),
    }
