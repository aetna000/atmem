from __future__ import annotations

import json

import pytest

from research.laya_formation.jev_protocol import (
    resolve_model_identity,
    validate_openapi,
    verify_response_model,
)


def test_resolves_one_concrete_model_without_network() -> None:
    payload = {
        "models": [
            {"name": "jev-1.13.0", "description": "pinned", "release_date": "2026-09-15"},
            {"name": "jev-latest", "description": "moving", "release_date": "2026-09-15"},
        ]
    }
    receipt = resolve_model_identity(payload, requested_model="jev-1.13.0")
    assert receipt.resolved_model == "jev-1.13.0"
    assert receipt.models_payload_sha256.startswith("sha256:")
    verify_response_model(receipt, {"model": "jev-1.13.0", "answers": {}, "usage": {}})


@pytest.mark.parametrize("name", ["jev-latest", "latest", "jev-custom", ""])
def test_rejects_alias_or_unversioned_identity(name: str) -> None:
    with pytest.raises(ValueError, match="concrete versioned"):
        resolve_model_identity({"models": []}, requested_model=name)


def test_rejects_missing_or_mismatched_response_identity() -> None:
    receipt = resolve_model_identity(
        {"models": [{"name": "jev-1.13.0", "description": "pinned", "release_date": "2026-09-15"}]},
        requested_model="jev-1.13.0",
    )
    with pytest.raises(ValueError, match="differs"):
        verify_response_model(receipt, {"model": "jev-latest", "answers": {}, "usage": {}})


def test_pinned_openapi_shape() -> None:
    document = json.loads(
        """{"openapi":"3.1.0","info":{"version":"0.2.0"},"paths":{"/v1/models":{},"/v1/systemone":{}}}"""
    )
    validate_openapi(document)
