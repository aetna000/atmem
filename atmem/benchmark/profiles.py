"""Explicit benchmark execution profiles and availability diagnostics."""

from __future__ import annotations

import os
from typing import Any


_PROFILES: dict[str, dict[str, Any]] = {
    "deterministic": {
        "mode": "deterministic",
        "provider": "atmem-rules",
        "model": "deterministic-v1",
        "embedding": "atmem-hashing-v1",
        "egress_class": "none",
        "optional": False,
    },
    "local-embeddings": {
        "mode": "local-embeddings",
        "provider": "configured-local-embedder",
        "model": "configured",
        "embedding": "configured-local",
        "egress_class": "local",
        "optional": True,
        "enable_env": "ATMEM_BENCHMARK_LOCAL_EMBEDDINGS",
    },
    "local-atbot": {
        "mode": "local-atbot",
        "provider": "atbot-local",
        "model": "configured",
        "embedding": "configured",
        "egress_class": "local",
        "optional": True,
        "enable_env": "ATMEM_BENCHMARK_LOCAL_ATBOT",
    },
    "hosted-atbot": {
        "mode": "hosted-atbot",
        "provider": "atbot-hosted",
        "model": "configured",
        "embedding": "configured",
        "egress_class": "remote",
        "optional": True,
        "enable_env": "ATMEM_BENCHMARK_HOSTED_ATBOT",
    },
}


def list_profiles() -> list[dict[str, Any]]:
    return [resolve_profile(name) for name in _PROFILES]


def resolve_profile(name: str) -> dict[str, Any]:
    if name not in _PROFILES:
        raise ValueError(f"unknown benchmark profile: {name}")
    profile = dict(_PROFILES[name])
    enable_env = profile.pop("enable_env", None)
    available = not profile["optional"] or os.environ.get(str(enable_env)) == "1"
    profile["available"] = available
    profile["skip_reason"] = None if available else (
        f"set {enable_env}=1 after configuring the required local or hosted provider"
    )
    if name != "deterministic" and available:
        prefix = "ATMEM_BENCHMARK_" + name.upper().replace("-", "_")
        profile["provider"] = os.environ.get(prefix + "_PROVIDER", profile["provider"])
        profile["model"] = os.environ.get(prefix + "_MODEL", profile["model"])
        profile["embedding"] = os.environ.get(prefix + "_EMBEDDING", profile["embedding"])
        profile["endpoint"] = os.environ.get(prefix + "_ENDPOINT")
        profile["api_key_env"] = os.environ.get(prefix + "_API_KEY_ENV")
        profile["model_version"] = os.environ.get(prefix + "_MODEL_VERSION", "unverified")
    if name == "local-embeddings" and available:
        provider = os.environ.get("ATMEM_BENCHMARK_LOCAL_EMBEDDINGS_PROVIDER", "")
        model = os.environ.get("ATMEM_BENCHMARK_LOCAL_EMBEDDINGS_MODEL", "")
        if provider not in {"ollama", "openai-compatible", "sentence-transformers"} or not model:
            profile["available"] = False
            profile["skip_reason"] = (
                "set ATMEM_BENCHMARK_LOCAL_EMBEDDINGS_PROVIDER and "
                "ATMEM_BENCHMARK_LOCAL_EMBEDDINGS_MODEL after configuring the embedder"
            )
        else:
            profile["provider"] = provider
            profile["model"] = model
            profile["embedding"] = f"{provider}:{model}"
    if name in {"local-atbot", "hosted-atbot"} and available:
        from atmem.control.atbot_companion import AtBotCompanionClient
        from atmem.control.atbot_service import AtBotServiceManager

        health = AtBotCompanionClient().health()
        configured_egress = AtBotServiceManager().configured_egress_class()
        required_egress = "local" if name == "local-atbot" else "remote"
        if not health.get("available"):
            profile["available"] = False
            profile["skip_reason"] = "AtBot health check failed: " + str(health.get("reason") or "unavailable")
        elif configured_egress != required_egress:
            profile["available"] = False
            profile["skip_reason"] = (
                f"AtBot is configured for {configured_egress} egress, not {required_egress}"
            )
        else:
            providers = health.get("providers") or []
            selected = providers[0] if providers and isinstance(providers[0], dict) else {}
            profile["provider"] = str(selected.get("name") or selected.get("provider") or profile["provider"])
            profile["model"] = str(selected.get("model") or profile["model"])
            profile["health_verified"] = True
    return profile
