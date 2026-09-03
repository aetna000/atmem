from __future__ import annotations

import base64
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atmem.control.manager import ControlPlaneManager
from atmem.delegated.config import DelegatedConfigStore, DelegatedRegistration
from atmem.delegated.service import DelegatedContextService


def _active_manager(tmp_path: Path):
    manager = ControlPlaneManager.start(
        host="generic",
        state_path=tmp_path / "state.json",
        control_root=tmp_path / "control",
    )
    topology = manager.configure_agent_topology(
        [{"agent_id": "main", "workspace": "workspace", "is_default": True}]
    )
    candidate = manager.capture(
        "Remember that my editor is Neovim.",
        authenticated_user=True,
        agent_id="main",
    )
    manager.review_memory(candidate["candidate_ids"][0], "approve")
    manager.activate()
    return manager, topology["agents"][0]["workspace_id"]


def _enable(tmp_path: Path, monkeypatch, workspace_id: str, *, fallback: bool = False):
    path = tmp_path / "delegated.json"
    monkeypatch.setenv("ATMEM_DELEGATED_CONFIG", str(path))
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    DelegatedConfigStore(path).register(
        DelegatedRegistration(
            provider_id="storizon",
            provider_version="test",
            provider_instance_id="local",
            key_id="primary",
            public_key_base64=base64.b64encode(public).decode("ascii"),
            endpoint="http://127.0.0.1:8788/v1/delegated-context",
            workspace_ids=(workspace_id,),
            agent_ids=("main",),
            user_ids=("owner",),
            enabled=False,
            native_fallback_on_failure=fallback,
        )
    )
    DelegatedConfigStore(path).set_enabled("storizon:local", True)


def _binding_args(workspace_id: str) -> dict[str, str]:
    return {
        "session_id": "session-1",
        "host_run_id": "run-1",
        "turn_id": "turn-1",
        "agent_id": "main",
        "user_id": "owner",
        "workspace_id": workspace_id,
    }


def test_native_default_remains_unchanged(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ATMEM_DELEGATED_CONFIG", str(tmp_path / "absent.json"))
    manager, _workspace_id = _active_manager(tmp_path)
    result = manager.prepare("Which editor?", agent_id="main")
    assert result["authority"] == "atmem"
    assert result["inject"] is True
    assert "Neovim" in result["context"]


def test_delegated_inject_is_exclusive_and_exact(tmp_path: Path, monkeypatch) -> None:
    manager, workspace_id = _active_manager(tmp_path)
    _enable(tmp_path, monkeypatch, workspace_id)
    exact = "Reviewed context 🧠\r\nKeep these bytes."

    def delegated(self, **kwargs):
        return {
            "handled": True,
            "authority": "delegated",
            "decision": "inject",
            "inject": True,
            "context": exact,
            "context_sha256": "b" * 64,
            "context_byte_length": len(exact.encode()),
            "result_sha256": "c" * 64,
            "receipt": {"id": "receipt-1", "sha256": "d" * 64},
            "native_fallback": False,
            "exposure_id": "delivery-1",
        }

    monkeypatch.setattr(DelegatedContextService, "prepare", delegated)
    monkeypatch.setattr(
        manager,
        "_hybrid_memory_candidates",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("native retrieval ran")),
    )
    result = manager.prepare("Which editor?", **_binding_args(workspace_id))
    assert result["context"].encode() == exact.encode()
    assert result["authority"] == "delegated"
    assert result["candidate_ids"] == []


def test_delegated_withhold_and_missing_identity_fail_closed(tmp_path: Path, monkeypatch) -> None:
    manager, workspace_id = _active_manager(tmp_path)
    _enable(tmp_path, monkeypatch, workspace_id)
    monkeypatch.setattr(
        DelegatedContextService,
        "prepare",
        lambda self, **kwargs: {
            "handled": True,
            "authority": "delegated",
            "decision": "withhold",
            "inject": False,
            "context": "",
            "withhold_reason": {"code": "POLICY_DENIED", "retryable": False},
            "native_fallback": False,
        },
    )
    withheld = manager.prepare("Which editor?", **_binding_args(workspace_id))
    assert withheld["inject"] is False
    assert withheld["reason"] == "POLICY_DENIED"
    missing = manager.prepare(
        "Which editor?",
        **{**_binding_args(workspace_id), "user_id": None},
    )
    assert missing["inject"] is False
    assert "missing user_id" in missing["reason"]


def test_explicit_failure_fallback_is_labeled(tmp_path: Path, monkeypatch) -> None:
    manager, workspace_id = _active_manager(tmp_path)
    _enable(tmp_path, monkeypatch, workspace_id, fallback=True)
    monkeypatch.setattr(
        DelegatedContextService,
        "prepare",
        lambda self, **kwargs: {
            "handled": True,
            "authority": "atmem_fallback",
            "decision": "provider_failure",
            "inject": False,
            "context": "",
            "native_fallback": True,
            "failure_code": "TimeoutError",
        },
    )
    result = manager.prepare("Which editor?", **_binding_args(workspace_id))
    assert result["authority"] == "atmem_fallback"
    assert result["native_fallback"] is True
    assert "Neovim" in result["context"]


def test_default_provider_failure_suppresses_native_retrieval(
    tmp_path: Path, monkeypatch
) -> None:
    manager, workspace_id = _active_manager(tmp_path)
    _enable(tmp_path, monkeypatch, workspace_id)
    monkeypatch.setattr(
        DelegatedContextService,
        "prepare",
        lambda self, **kwargs: {
            "handled": True,
            "authority": "delegated",
            "decision": "provider_failure",
            "inject": False,
            "context": "",
            "native_fallback": False,
            "failure_code": "TimeoutError",
            "failure_reason": "provider timed out",
        },
    )
    monkeypatch.setattr(
        manager,
        "_hybrid_memory_candidates",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("native retrieval ran after delegated failure")
        ),
    )
    result = manager.prepare("Which editor?", **_binding_args(workspace_id))
    assert result["authority"] == "delegated"
    assert result["decision"] == "provider_failure"
    assert result["inject"] is False
    assert result["context"] == ""
