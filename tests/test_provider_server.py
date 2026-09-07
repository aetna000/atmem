from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import pytest

from atmem.delegated.contracts import DelegatedBinding, DelegatedContextRequest
from atmem.provider_adapters import lifecycle
from atmem.provider_adapters.server import create_server
from atmem.delegated.transport import load_keyring, load_secret, sign_headers


def test_server_rejects_non_loopback_before_binding() -> None:
    with pytest.raises(ValueError, match="loopback"):
        create_server(object(), "0.0.0.0", 8788)


def test_managed_service_health_signed_request_and_stop(tmp_path: Path, monkeypatch) -> None:
    module = tmp_path / "provider_fixture.py"
    module.write_text(
        "class Client:\n"
        "    def search(self, query, *, filters, top_k):\n"
        "        return [{'id': 'one', 'memory': 'User likes burgers'}]\n"
        "def client(): return Client()\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PYTHONPATH", str(tmp_path) + os.pathsep + os.getcwd())
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv("ATMEM_PROVIDER_ROOT", str(tmp_path / "providers"))
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    lifecycle.initialize(
        instance="live", kind="mem0", port=port,
        factory="provider_fixture:client",
    )
    ring = load_keyring(tmp_path / "providers/live/request-auth.json")
    active = ring["keys"][0]
    def headers_for(body):
        return {"Content-Type": "application/json", **sign_headers(secret=load_secret(active["secret_file"]),
            provider_id=ring["provider_id"], instance_id="live", key_id=active["key_id"],
            method="POST", authority=f"127.0.0.1:{port}", target="/v1/delegated-context", body=body)}
    try:
        lifecycle.start("live")
        for _ in range(40):
            state = lifecycle.doctor("live")
            if state["ok"]:
                break
            time.sleep(0.05)
        assert state["ok"] is True
        request_value = DelegatedContextRequest.create(
            binding=DelegatedBinding("r", "t", "s", "a", "u", "w"),
            query="favorite food", max_context_bytes=4096, timeout_ms=3000,
        ).to_dict()
        request = Request(
            f"http://127.0.0.1:{port}/v1/delegated-context",
            data=json.dumps(request_value).encode(),
            headers=headers_for(json.dumps(request_value).encode()), method="POST",
        )
        with urlopen(request, timeout=2) as response:
            envelope = json.loads(response.read())
        assert envelope["decision"] == "inject"
        assert envelope["source_refs"] == ["mem0:one"]
        health = lifecycle.status("live")["health"]
        assert health["last_decision"] == "inject"
        assert health["last_adapter_latency_ms"] >= 0
        assert health["attribution"] == {"adapter": "mem0", "mode": "factory"}

        # Replay the exact signed HTTP request after a genuine worker restart.
        lifecycle.stop("live")
        lifecycle.start("live")
        for _ in range(40):
            if lifecycle.status("live")["health"]:
                break
            time.sleep(0.05)
        with pytest.raises(HTTPError) as replay:
            urlopen(request, timeout=2)
        assert replay.value.code == 401
        assert lifecycle.status("live")["health"]["requests"] == 0

        def one_request(number: int) -> str:
            value = DelegatedContextRequest.create(
                binding=DelegatedBinding("r", f"turn-{number}", "s", "a", "u", "w"),
                query="favorite food", max_context_bytes=4096, timeout_ms=3000,
            ).to_dict()
            call = Request(
                f"http://127.0.0.1:{port}/v1/delegated-context",
                data=json.dumps(value).encode(),
                headers=headers_for(json.dumps(value).encode()), method="POST",
            )
            with urlopen(call, timeout=3) as response:
                return json.loads(response.read())["binding"]["turn_id"]

        with ThreadPoolExecutor(max_workers=10) as pool:
            assert sorted(pool.map(one_request, range(25))) == sorted(f"turn-{i}" for i in range(25))
    finally:
        lifecycle.stop("live")
    assert lifecycle.status("live")["running"] is False
