#!/usr/bin/env python3
"""Exercise delegated-context primitives from an installed AtMem wheel."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile

from atmem.control.store import ControlStore, SCHEMA_VERSION
from atmem.delegated import (
    DelegatedBinding,
    DelegatedConfigStore,
    DelegatedContextRequest,
    DelegatedRegistration,
    parse_and_verify_envelope,
)


FIXTURES = (
    Path(__file__).parents[1] / "docs" / "contracts" / "delegated-context-provider-v1"
)


def main() -> None:
    trust = json.loads((FIXTURES / "trust.json").read_text(encoding="utf-8"))
    trust.pop("fixture_key_only")
    registration = DelegatedRegistration(
        provider_id=trust["provider_id"],
        provider_version=trust["provider_version"],
        provider_instance_id=trust["provider_instance_id"],
        key_id=trust["key_id"],
        public_key_base64=trust["public_key_base64"],
        endpoint="http://127.0.0.1:8788/v1/delegated-context",
        workspace_ids=tuple(trust["workspace_ids"]),
        agent_ids=tuple(trust["agent_ids"]),
        user_ids=tuple(trust["user_ids"]),
    )
    envelope = (FIXTURES / "inject.valid.json").read_bytes()
    binding = DelegatedBinding.from_dict(json.loads(envelope)["binding"])
    verified = parse_and_verify_envelope(
        envelope,
        expected_binding=binding,
        trust=registration,
        now=datetime(2026, 9, 1, 12, 1, tzinfo=timezone.utc),
    )
    assert verified.context_bytes == "Reviewed context 🧠\r\nKeep these bytes.".encode()
    request = DelegatedContextRequest.create(
        binding=binding,
        query="installed wheel delegated smoke",
        max_context_bytes=registration.max_context_bytes,
        timeout_ms=registration.timeout_ms,
    ).to_dict()
    assert set(request) == {
        "contract_id", "binding", "query", "query_sha256",
        "max_context_bytes", "deadline",
    }

    with tempfile.TemporaryDirectory(prefix="atmem-delegated-wheel-") as temp:
        root = Path(temp)
        config = DelegatedConfigStore(root / "delegated.json")
        saved = config.register(registration)
        assert config.status()["authority_default"] == "atmem"
        assert config.status()["enabled"] is False
        assert "public_key_base64" not in json.dumps(saved)
        store = ControlStore(root / "control.db")
        try:
            assert SCHEMA_VERSION == 5
        finally:
            store.close()

    print("installed delegated-context wheel smoke test passed")


if __name__ == "__main__":
    main()
