from dataclasses import replace
import json

import pytest

from atmem.adapters import AtMemAdapterIdentity
from atmem.adapters.hermes import HermesMemoryBinding


class Manager:
    def __init__(self):
        self.calls = []
        self.workspaces = [{"workspace_id": "workspace", "subject_id": "owner", "agent_ids": ["agent"]}]
        self.result = {"inject": True, "context": "authorized memory", "candidate_ids": ["r1"]}

    def agent_topology(self):
        return {"workspaces": self.workspaces}

    def prepare(self, query, **kwargs):
        self.calls.append((query, kwargs))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def binding(manager, **kwargs):
    return HermesMemoryBinding(manager, AtMemAdapterIdentity(
        agent_id="agent", workspace_id="workspace", subject_id="owner",
    ), profile_id="profile", **kwargs)


def test_default_is_non_influencing():
    manager = Manager()
    adapter = binding(manager)
    assert adapter.recall("query", session_id="s", turn_id="t").reason == "inactive"
    assert adapter.observe_user("hello", session_id="s", observation_id="o")["reason"] == "inactive"
    assert manager.calls == []


def test_each_recall_prepares_again_and_never_reuses_old_context():
    manager = Manager()
    adapter = binding(manager, enabled=True)
    assert adapter.recall("query", session_id="s", turn_id="1").context
    manager.result = {"inject": False, "preview_context": "must not leak"}
    assert adapter.recall("query", session_id="s", turn_id="2").context == ""
    assert len(manager.calls) == 2


def test_revoked_topology_withholds_without_calling_retrieval():
    manager = Manager()
    adapter = binding(manager, enabled=True)
    manager.workspaces = []
    assert adapter.recall("query", session_id="s", turn_id="t").context == ""
    assert not manager.calls
    with pytest.raises(PermissionError):
        adapter.observe_user("hello", session_id="s", observation_id="o")


@pytest.mark.parametrize("result", [RuntimeError("secret"), {"inject": True, "context": "x" * 4097}, {"inject": False, "context": "forbidden"}])
def test_errors_and_oversized_results_never_return_context(result):
    manager = Manager()
    manager.result = result
    value = binding(manager, enabled=True).recall("query", session_id="s", turn_id="t")
    assert value.context == ""
    assert "secret" not in repr(value)


def test_profile_namespaces_sessions_and_scope_is_not_a_tool_argument():
    manager = Manager()
    first = binding(manager, enabled=True)
    second = HermesMemoryBinding(manager, first.identity, profile_id="other", enabled=True)
    first.recall("q", session_id="same", turn_id="1")
    second.recall("q", session_id="same", turn_id="1")
    assert manager.calls[0][1]["session_id"] != manager.calls[1][1]["session_id"]
    assert manager.calls[0][1]["subject_id"] == "owner"
    assert manager.calls[0][1]["allow_delegation"] is False
    with pytest.raises(TypeError):
        first.recall("q", session_id="same", turn_id="1", subject_id="victim")


def test_missing_authentication_is_rejected():
    manager = Manager()
    identity = replace(binding(manager).identity, authenticated_user=False)
    with pytest.raises(PermissionError):
        HermesMemoryBinding(manager, identity, profile_id="p")


def test_ambiguous_agent_or_subject_workspace_is_rejected():
    manager = Manager()
    adapter = binding(manager, enabled=True)
    manager.workspaces.append({"workspace_id": "other", "subject_id": "owner", "agent_ids": ["other-agent"]})
    assert adapter.recall("q", session_id="s", turn_id="t").context == ""
    with pytest.raises(PermissionError):
        adapter.observe_user("hello", session_id="s", observation_id="o")


def test_real_control_plane_capture_retry_and_recall(tmp_path, monkeypatch):
    from atmem.control import ControlPlaneManager
    manager = ControlPlaneManager.start(host="generic", state_path=tmp_path / "state.json",
                                        control_root=tmp_path / "control", memory_db=tmp_path / "memory.db")
    monkeypatch.setattr("atmem.control.atbot_companion.AtBotCompanionClient.propose",
                        lambda self, message: {"proposals": [], "companion": {"available": False}})
    monkeypatch.setattr("atmem.control.atbot_companion.AtBotCompanionClient.expand_query",
                        lambda self, query: {"expanded_queries": [query], "content_received": False})
    monkeypatch.setattr("atmem.control.atbot_companion.AtBotCompanionClient.query",
                        lambda self, query, candidates: {"ranked_record_ids": [row["record_id"] for row in candidates],
                                                        "companion": {"available": False}})
    workspace = manager.agent_topology()["workspaces"][0]
    adapter = HermesMemoryBinding(manager, AtMemAdapterIdentity(
        agent_id="main", workspace_id=workspace["workspace_id"], subject_id=workspace["subject_id"],
    ), profile_id="real-profile", enabled=True)
    first = adapter.observe_user("My preferred editor is Neovim.", session_id="s", observation_id="o")
    second = adapter.observe_user("My preferred editor is Neovim.", session_id="s", observation_id="o")
    assert json.loads(json.dumps(first)) == second
    assert first["result"]["captured"] > 0
    assert adapter.recall("preferred editor", session_id="s2", turn_id="t").context == ""  # shadow
    for candidate in first["result"]["candidate_ids"]:
        manager.review_memory(candidate, "approve")
    manager.activate()
    assert "Neovim" in adapter.recall("preferred editor", session_id="s2", turn_id="t").context
    from atmem.service import APIError
    with pytest.raises(APIError, match="different payload"):
        adapter.observe_user("My preferred editor is Vim.", session_id="s", observation_id="o")
