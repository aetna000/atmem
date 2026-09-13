"""Adapter-owned interpretation profiles for host observation envelopes.

Core verification consumes these narrow declarations without learning host
session prefixes or tool-specific result shapes.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence


_SUPPORTED_BOUNDARIES = {
    "openclaw": (
        "turn.input",
        "context.disposition",
        "model.input",
        "tool.requested",
        "tool.completed",
        "model.output",
        "turn.ended",
        "capture.gap",
    )
}


def supported_boundaries(*, host: str, observed: Sequence[str]) -> tuple[str, ...]:
    """Return a declared host profile or only the boundaries actually observed."""

    return _SUPPORTED_BOUNDARIES.get(host, tuple(sorted(set(observed))))


def run_kind(*, host: str, run_id: str, session_id: str | None) -> str:
    """Classify only adapter conventions that have been explicitly verified."""

    if (
        host == "openclaw"
        and run_id.startswith("skill-workshop-review:")
        and str(session_id or "").startswith(
            "internal-session-effects-skill-workshop-review_"
        )
    ):
        return "background_skill_review"
    return "agent_run"


def equivalent_result_profile(
    *,
    host: str,
    canonical_name: str,
    request_payloads: Sequence[Mapping[str, Any]],
    completion_payloads: Sequence[Mapping[str, Any]],
) -> str | None:
    """Return a verified adapter comparison profile, never inferred equality."""

    if host != "openclaw" or canonical_name != "progress_card":
        return None
    request_names = {
        str(payload.get("tool_name") or canonical_name)
        for payload in request_payloads
    }
    completion_names = {
        str(payload.get("tool_name") or canonical_name)
        for payload in completion_payloads
    }
    comparisons = {
        payload.get("result_comparison_sha256") for payload in completion_payloads
    }
    if (
        request_names == completion_names == {"progress_card"}
        and len(completion_payloads) == 2
        and len({payload.get("params_sha256") for payload in request_payloads}) == 1
        and all(payload.get("params_sha256") for payload in request_payloads)
        and all(
            payload.get("outcome") == "completed"
            and not payload.get("error_sha256")
            and not payload.get("error_category")
            for payload in completion_payloads
        )
        and all(
            payload.get("result_comparison_profile")
            == "openclaw-progress-card-v1"
            for payload in completion_payloads
        )
        and len(comparisons) == 1
        and all(
            isinstance(value, str)
            and len(value) == 64
            and all(character in "0123456789abcdef" for character in value)
            for value in comparisons
        )
        and {
            payload.get("result_observation_shape")
            for payload in completion_payloads
        }
        == {"native_input_text", "tool_content_details"}
    ):
        return "openclaw-progress-card-v1"
    return None
