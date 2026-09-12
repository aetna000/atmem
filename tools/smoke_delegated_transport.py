#!/usr/bin/env python3
"""Installed-artifact HMAC smoke and synthetic provider for the OpenClaw harness.

Run outside the checkout with an installed Python. --serve ROOT keeps an isolated
provider/control fixture alive until stdin closes; no private Storizon is used.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from atmem.control.manager import ControlPlaneManager
from atmem.delegated.client import authentication_headers, request_health, request_context
from atmem.delegated.config import DelegatedRegistration, DelegatedConfigStore
from atmem.delegated.contracts import DelegatedBinding, DelegatedContextRequest
from atmem.delegated.service import DelegatedContextService
from atmem.delegated.transport import RequestAuthenticator, configure_keyring
from atmem.delegated.validation import parse_and_verify_envelope
from atmem.provider_adapters.models import ContextItem, ProviderProposal, ProviderRuntimeIdentity
from atmem.provider_adapters.runtime import ProviderRuntime
from atmem.provider_adapters.server import create_server
from atmem.provider_adapters.signing import generate_keypair, load_private_key

EXACT = "Memory: Reviewed trip 🧠\r\nKeep these bytes.\n"


@contextmanager
def fixture(root: Path, *, provider_factory=None):
    root = root.resolve()
    os.environ["ATMEM_DELEGATED_CONFIG"] = str(root / "delegated.json")
    os.environ["ATMEM_CONTROL_STATE"] = str(root / "control.json")
    workspace = root / "workspace"
    workspace.mkdir()
    manager = ControlPlaneManager.start(host="generic", state_path=root / "control.json",
        control_root=root / "control", memory_db=root / "memories.db")
    topology = manager.configure_agent_topology([{"agent_id": "main", "workspace": str(workspace), "is_default": True}])
    manager.activate()
    key = configure_keyring(root / "request-auth.json", provider_id="fixture-provider", instance_id="local")
    public = generate_keypair(root / "private.key", root / "public.key")
    class Provider:
        def decide(self, request):
            if "withhold" in request.query:
                return ProviderProposal.withhold()
            return ProviderProposal.inject([ContextItem("Reviewed trip 🧠\r\nKeep these bytes.", "fixture:trip")])
    provider = provider_factory(root, topology) if provider_factory else Provider()
    runtime = ProviderRuntime(provider=provider, identity=ProviderRuntimeIdentity("fixture-provider", "test", "local", "primary"),
        private_key=load_private_key(root / "private.key"), adapter_kind="fixture")
    runtime.request_authenticator = RequestAuthenticator(root / "request-auth.json", root / "request-nonces.db")
    server = create_server(runtime, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    registration = DelegatedRegistration(provider_id="fixture-provider", provider_version="test", provider_instance_id="local",
        key_id="primary", public_key_base64=public, endpoint=f"http://127.0.0.1:{server.server_port}/v1/delegated-context",
        workspace_ids=(topology["primary_workspace_id"],), agent_ids=("main",), user_ids=("owner",),
        request_key_id=key["request_key_id"], request_secret_file=key["request_secret_file"])
    config = DelegatedConfigStore()
    config.register(registration)
    config.set_enabled(registration.registration_id, True)
    try:
        yield manager, registration, {"state_path": str(root / "control.json"), "workspace": str(workspace),
            "memory_db": str(root / "memories.db"), "subject": manager.state().subject_id,
            "config_path": str(config.path), "exact": EXACT, "endpoint": registration.endpoint}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)


def smoke(root: Path) -> None:
    with fixture(root) as (manager, registration, _):
        before = request_health(registration)["requests"]
        for endpoint, body in ((registration.endpoint, b"{}"), (registration.endpoint.replace("/v1/delegated-context", "/health"), None)):
            try:
                urlopen(Request(endpoint, data=body, headers={"Content-Type": "application/json"}), timeout=2)
            except HTTPError as error:
                assert error.code == 401
            else:
                raise AssertionError("unsigned request was accepted")
        assert request_health(registration)["requests"] == before
        assert DelegatedContextService().doctor()["ready"] is True
        for query, turn in (("synthetic query", "inject"), ("withhold", "withhold")):
            binding = DelegatedBinding("run-" + turn, turn, "session", "main", "owner", registration.workspace_ids[0])
            raw = request_context(registration, binding=binding, query=query)
            verified = parse_and_verify_envelope(raw, expected_binding=binding, trust=registration)
            assert verified.context_text == (EXACT if turn == "inject" else "")
        body = json.dumps(DelegatedContextRequest.create(binding=binding, query="artifact replay",
            max_context_bytes=4096, timeout_ms=3000).to_dict()).encode()
        request = Request(registration.endpoint, data=body, headers={"Content-Type": "application/json",
            **authentication_headers(registration, "POST", registration.endpoint, body)})
        before = request_health(registration)["requests"]
        with urlopen(request, timeout=2) as response:
            assert response.status == 200
        try:
            urlopen(request, timeout=2)
        except HTTPError as error:
            assert error.code == 401
        else:
            raise AssertionError("identical authenticated request replay was accepted")
        assert request_health(registration)["requests"] == before + 1
        result = manager.prepare("synthetic query", host_run_id="manager-run", turn_id="manager-turn",
            session_id="manager-session", agent_id="main", user_id="owner", workspace_id=registration.workspace_ids[0])
        assert result["authority"] == "delegated" and result["context"] == EXACT
        assert manager.confirm_exposure(result["exposure_id"])
        for database in root.rglob("*.db"):
            data = database.read_bytes()
            assert b"synthetic query" not in data and EXACT.encode() not in data
    print("installed HMAC transport, replay rejection, authenticated health, inject/withhold, delivery and privacy passed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", type=Path)
    args = parser.parse_args()
    if args.serve:
        with fixture(args.serve) as (_, _, details):
            print(json.dumps(details), flush=True)
            sys.stdin.read()
    else:
        with tempfile.TemporaryDirectory(prefix="atmem-hmac-wheel-") as directory:
            smoke(Path(directory))


if __name__ == "__main__":
    main()
