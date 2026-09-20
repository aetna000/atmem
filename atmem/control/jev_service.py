"""Opt-in Jev advisory reranking for governed AtMem retrieval.

Jev never owns memory or authorization.  AtMem sends only the already eligible
candidate set, validates the returned ids, and keeps native ordering on failure.
The API key is read from an operator-selected environment variable and is never
written to the AtMem home.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from typing import Any
from urllib import error, request
from urllib.parse import urlparse

from atmem.home.layout import compatible_home_path


DEFAULT_ENDPOINT = "https://api.typesafe.ai/v1/systemone"
DEFAULT_MODEL = "jev-1.13.0"
DEFAULT_ROOT = compatible_home_path("config/jev", "jev")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _write_private(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.chmod(0o600)
    temp.replace(path)


class JevServiceManager:
    """Persist and execute an explicitly enabled Jev advisory policy."""

    def __init__(self, root: str | Path = DEFAULT_ROOT) -> None:
        self.root = Path(root).expanduser()
        self.config_path = self.root / "config.json"

    def _config(self) -> dict[str, Any]:
        try:
            value = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError):
            value = {}
        return value if isinstance(value, dict) else {}

    def status(self) -> dict[str, Any]:
        config = self._config()
        enabled = bool(config.get("enabled", False))
        endpoint = str(config.get("endpoint") or DEFAULT_ENDPOINT)
        key_env = str(config.get("api_key_env") or "JEV_API")
        configured = bool(self.config_path.exists())
        has_key = bool(os.environ.get(key_env))
        return {
            "format": "atmem-jev-status-v1",
            "enabled": enabled,
            "configured": configured,
            "provider": "jev",
            "model": str(config.get("model") or DEFAULT_MODEL),
            "endpoint": endpoint,
            "api_key_env": key_env,
            "key_present": has_key,
            "egress_class": "local" if urlparse(endpoint).hostname in {"127.0.0.1", "localhost", "::1"} else "remote",
            "timeout_seconds": float(config.get("timeout_seconds") or 8.0),
            "fallback": str(config.get("fallback") or "native"),
            "last_error": config.get("last_error"),
            "updated_at": config.get("updated_at"),
        }

    def configure(
        self,
        *,
        enabled: bool = False,
        model: str | None = None,
        endpoint: str | None = None,
        api_key_env: str | None = None,
        timeout_seconds: float | None = None,
        fallback: str = "native",
    ) -> dict[str, Any]:
        endpoint_value = str(endpoint or DEFAULT_ENDPOINT).strip().rstrip("/")
        parsed = urlparse(endpoint_value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Jev endpoint must be an HTTP(S) URL")
        if parsed.hostname not in {"127.0.0.1", "localhost", "::1"} and parsed.scheme != "https":
            raise ValueError("remote Jev endpoints must use HTTPS")
        key_name = str(api_key_env or "JEV_API").strip()
        if not key_name.replace("_", "").isalnum() or not key_name[0].isalpha() or key_name.upper() != key_name:
            raise ValueError("Jev API-key environment variable must be an uppercase identifier")
        timeout = float(timeout_seconds if timeout_seconds is not None else 8.0)
        if not 1.0 <= timeout <= 30.0:
            raise ValueError("Jev timeout must be between 1 and 30 seconds")
        if fallback not in {"native", "withhold"}:
            raise ValueError("Jev fallback must be native or withhold")
        value = {
            "format": "atmem-jev-config-v1",
            "enabled": bool(enabled),
            "model": str(model or DEFAULT_MODEL).strip() or DEFAULT_MODEL,
            "endpoint": endpoint_value,
            "api_key_env": key_name,
            "timeout_seconds": timeout,
            "fallback": fallback,
            "updated_at": _now(),
        }
        _write_private(self.config_path, value)
        return {"configured": True, "status": self.status()}

    def set_enabled(self, enabled: bool) -> dict[str, Any]:
        config = self._config()
        result = self.configure(
            enabled=enabled,
            model=str(config.get("model") or DEFAULT_MODEL),
            endpoint=str(config.get("endpoint") or DEFAULT_ENDPOINT),
            api_key_env=str(config.get("api_key_env") or "JEV_API"),
            timeout_seconds=float(config.get("timeout_seconds") or 8.0),
            fallback=str(config.get("fallback") or "native"),
        )
        return result["status"]

    def rerank(self, query: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
        """Return a validated ranking or a native fallback decision."""
        status = self.status()
        native = [str(row.get("record_id") or row.get("id")) for row in candidates]
        base = {"provider": "jev", "model": status["model"], "enabled": status["enabled"], "fallback": True}
        if not status["enabled"]:
            return {**base, "used": False, "reason": "disabled", "ranked_record_ids": native}
        api_key = os.environ.get(status["api_key_env"], "")
        if not api_key:
            return self._fallback(base, native, "missing_api_key", status)
        if not candidates:
            return {**base, "used": False, "fallback": False, "reason": "no_candidates", "ranked_record_ids": []}
        options = {str(row.get("record_id") or row.get("id")): str(row.get("content") or "") for row in candidates}
        payload = json.dumps({
            "state": {"source": "atmem", "query": query, "candidates": options},
            "model": status["model"],
            "questions": {"memory": {"type": "choice", "instructions": "Rank the supplied candidates by relevance to the query. Choose only supplied ids.", "criteria": options}},
        }, separators=(",", ":")).encode("utf-8")
        started = time.perf_counter()
        try:
            req = request.Request(status["endpoint"], data=payload, method="POST", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
            with request.urlopen(req, timeout=status["timeout_seconds"]) as response:
                value = json.loads(response.read().decode("utf-8"))
            probabilities = ((value.get("answers") or {}).get("memory") or {}).get("probabilities") or {}
            ranked = [key for key, _ in sorted(probabilities.items(), key=lambda item: (-float(item[1]), str(item[0]))) if key in options]
            if not ranked:
                raise ValueError("Jev returned no eligible candidate ids")
            ranked.extend(item for item in native if item not in ranked)
            return {**base, "used": True, "fallback": False, "reason": None, "ranked_record_ids": ranked, "latency_ms": round((time.perf_counter() - started) * 1000, 2)}
        except (OSError, ValueError, TypeError, KeyError, error.HTTPError, error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            return self._fallback(base, native, type(exc).__name__, status)

    def _fallback(self, base: dict[str, Any], native: list[str], reason: str, status: dict[str, Any]) -> dict[str, Any]:
        config = self._config()
        config["last_error"] = reason
        config["updated_at"] = _now()
        _write_private(self.config_path, config)
        if status["fallback"] == "withhold":
            return {**base, "used": False, "fallback": True, "reason": reason, "ranked_record_ids": []}
        return {**base, "used": False, "fallback": True, "reason": reason, "ranked_record_ids": native}
