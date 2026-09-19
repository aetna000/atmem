from __future__ import annotations

import json

import pytest

from atmem.control.jev_service import JevServiceManager


def test_jev_is_disabled_by_default_and_does_not_call_network(tmp_path) -> None:
    service = JevServiceManager(tmp_path)
    status = service.status()
    assert status["enabled"] is False
    assert service.rerank("which city", [{"id": "a", "content": "Paris"}]) == {
        "provider": "jev",
        "model": "jev-1.13.0",
        "enabled": False,
        "fallback": True,
        "used": False,
        "reason": "disabled",
        "ranked_record_ids": ["a"],
    }


def test_jev_configuration_never_persists_secret_and_enable_is_explicit(tmp_path, monkeypatch) -> None:
    service = JevServiceManager(tmp_path)
    configured = service.configure(enabled=False, api_key_env="TEST_JEV_API")
    assert configured["status"]["enabled"] is False
    service.set_enabled(True)
    assert service.status()["enabled"] is True
    monkeypatch.setenv("TEST_JEV_API", "secret-not-written")
    payload = json.loads((tmp_path / "config.json").read_text())
    assert "secret-not-written" not in json.dumps(payload)
    assert payload["api_key_env"] == "TEST_JEV_API"


def test_jev_rejects_insecure_remote_endpoint(tmp_path) -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        JevServiceManager(tmp_path).configure(endpoint="http://remote.example/jev")


def test_jev_missing_key_falls_back_to_native(tmp_path) -> None:
    service = JevServiceManager(tmp_path)
    service.configure(enabled=True, api_key_env="MISSING_JEV_KEY", fallback="native")
    result = service.rerank("which city", [{"id": "a", "content": "Paris"}])
    assert result["fallback"] is True
    assert result["ranked_record_ids"] == ["a"]
    assert result["reason"] == "missing_api_key"
