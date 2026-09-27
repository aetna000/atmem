"""Native provider ABC checks against the pinned Hermes checkout, no model calls."""
import os
from pathlib import Path

import pytest

from atmem.adapters.hermes.provider import create_provider
from test_hermes_binding import Manager, binding


@pytest.fixture
def provider(tmp_path, monkeypatch):
    source = os.environ.get("HERMES_SOURCE")
    if not source:
        pytest.skip("HERMES_SOURCE is required for native provider checks")
    monkeypatch.syspath_prepend(str(Path(source).resolve()))
    manager = Manager()
    backend = binding(manager, enabled=True)
    writes = []
    monkeypatch.setattr(backend, "observe_user", lambda text, **kw: writes.append((text, kw)) or {"result": {"captured": 1}})
    value = create_provider(backend, hermes_home=str(tmp_path))
    value.initialize("session", hermes_home=str(tmp_path), platform="cli")
    yield value, manager, writes
    value.shutdown()


def test_native_hooks_recall_and_capture_only_user(provider):
    value, manager, writes = provider
    value.on_turn_start(1, "My editor is Neovim")
    recalled = value.prefetch("editor", session_id="session")
    assert "authorized memory" in recalled
    assert "current user's scope" in recalled
    assert "first-person questions" in recalled
    assert '<atmem-subject role="current_user">' in recalled
    assert recalled.endswith("authorized memory\n</atmem-subject>")
    context_event = next(row for row in manager.events if row["event_type"] == "context.disposition")
    assert context_event["payload"]["disposition"] == "injected"
    assert context_event["context_receipt_id"] == "ctxp_real"
    value.sync_turn("My editor is Neovim", "invented assistant fact", session_id="session")
    output = next(row for row in manager.events if row["event_type"] == "model.output")
    assert output["context_receipt_id"] == "ctxp_real"
    assert output["run_id"] == context_event["run_id"]
    assert manager.calls[-1][1]["host_run_id"] == context_event["run_id"]
    assert value.flush()
    assert [row[0] for row in writes] == ["My editor is Neovim"]
    assert value.get_tool_schemas() == []
    assert value.system_prompt_block() == ""
    manager.result = {"inject": False}
    assert value.prefetch("editor", session_id="session") == ""
    assert value.recall_status() is None
    context_event = [row for row in manager.events if row["event_type"] == "context.disposition"][-1]
    assert context_event["payload"]["disposition"] == "withheld_by_policy"
    assert context_event["context_receipt_id"] is None


def test_evidence_transport_failure_does_not_remove_recalled_context_or_capture(provider, monkeypatch):
    value, manager, writes = provider
    def fail_evidence(**kwargs):
        raise RuntimeError("evidence unavailable")
    monkeypatch.setattr(manager, "record_blackbox_event", fail_evidence)
    value.on_turn_start(1, "My editor is Neovim")
    assert "authorized memory" in value.prefetch("editor", session_id="session")
    value.sync_turn("My editor is Neovim", "Neovim", session_id="session")
    assert value.flush()
    assert [row[0] for row in writes] == ["My editor is Neovim"]


def test_other_session_and_bot_do_not_write(provider):
    value, manager, writes = provider
    value.on_turn_start(1, "bot", author_is_bot=True)
    assert value.prefetch("private memory", session_id="session") == ""
    value.sync_turn("bot", "answer", session_id="session")
    assert value.flush()
    assert writes == []
    assert value.prefetch("query", session_id="other") == ""


def test_invalid_reinitialize_removes_access(provider, tmp_path):
    value, manager, writes = provider
    with pytest.raises(PermissionError):
        value.initialize("session", hermes_home=str(tmp_path / "other"))
    assert value.prefetch("query", session_id="session") == ""


def test_local_tui_uses_the_same_scoped_provider(provider, tmp_path):
    value, manager, _ = provider
    value.initialize("tui-session", hermes_home=str(tmp_path), platform="tui")
    value.on_turn_start(1, "How old am I?", model="local-model")
    recalled = value.prefetch("How old am I?", session_id="tui-session")
    assert "authorized memory" in recalled
    assert "current user's scope" in recalled
    assert '<atmem-subject role="current_user">' in recalled
    assert manager.calls[-1][1]["agent_id"] == "agent"


def test_remote_messaging_surface_is_not_silently_authorized(provider, tmp_path):
    value, _, _ = provider
    with pytest.raises(PermissionError, match="local CLI and TUI"):
        value.initialize("remote", hermes_home=str(tmp_path), platform="telegram")


def test_session_switch_flushes_and_resets_turn_identity(provider):
    value, manager, writes = provider
    value.on_turn_start(1, "first")
    value.sync_turn("first", "answer", session_id="session")
    value.on_session_switch("new")
    assert writes[0][1]["session_id"] == "session"
    with pytest.raises(ValueError, match="on_turn_start"):
        value.sync_turn("next", "answer", session_id="new")


def test_late_sync_keeps_its_original_turn_identity(provider):
    value, manager, writes = provider
    value.on_turn_start(1, "first input")
    value.on_turn_start(2, "second input")
    value.sync_turn("first input", "answer", session_id="session")
    value.sync_turn("second input", "answer", session_id="session")
    assert value.flush()
    assert [row[1]["observation_id"].split(":")[0] for row in writes] == ["1", "2"]


def test_skipped_and_interrupted_turns_do_not_permanently_fill_tracking(provider):
    value, _, writes = provider
    for turn in range(200):
        value.on_turn_start(turn, "bot", author_is_bot=True)
    assert len(value._turns) == 0
    for turn in range(200):
        value.on_turn_start(turn, "interrupted")
    assert value.get_status_config()["unmatched_turns"] == 72
    value.on_turn_start(201, "completed")
    value.sync_turn("completed", "answer", session_id="session")
    assert value.flush()
    assert writes[0][0] == "completed"
    value.on_session_switch("new")
    assert len(value._turns) == 0


def test_reused_turn_counter_with_different_source_has_distinct_operation(provider):
    value, _, writes = provider
    for text in ("first", "second"):
        value.on_turn_start(1, text)
        value.sync_turn(text, "answer", session_id="session")
    assert value.flush()
    assert writes[0][1]["observation_id"] != writes[1][1]["observation_id"]


def test_bot_cannot_consume_an_earlier_identical_human_source(provider):
    value, _, writes = provider
    value.on_turn_start(1, "same text")
    value.on_turn_start(2, "same text", author_is_bot=True)
    value.sync_turn("same text", "answer", session_id="session")
    assert value.flush()
    assert writes == []
    assert value.get_status_config()["withheld_syncs"] == 1


def test_status_failure_is_visible_without_holding_capture_lock(provider, monkeypatch):
    from atmem.adapters.hermes.binding import HermesMemoryBinding
    value, _, _ = provider
    def offline(self):
        assert value._lock.acquire(blocking=False)
        value._lock.release()
        raise RuntimeError("private connection detail")
    monkeypatch.setattr(HermesMemoryBinding, "status", offline)
    result = value.get_status_config()
    assert result["service_available"] is False
    assert result["enabled"] is False
    assert "private" not in str(result)


@pytest.mark.parametrize("normalized", ["actual instruction", ""])
def test_skill_normalization_matches_sync_source(provider, monkeypatch, normalized):
    import sys
    from types import ModuleType
    normalizer = ModuleType("agent.skill_commands")
    normalizer.extract_user_instruction_from_skill_message = lambda text: normalized
    monkeypatch.setitem(sys.modules, "agent.skill_commands", normalizer)
    value, _, writes = provider
    value.on_turn_start(1, "[IMPORTANT: The user has invoked the skill wrapper")
    value.sync_turn(normalized, "answer", session_id="session")
    assert value.flush()
    assert [row[0] for row in writes] == ([normalized] if normalized else [])
