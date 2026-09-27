"""Invoked in the real managed Hermes interpreter, with a disposable Home.

No AtMem imports or benchmark code: exercise the shipped directory provider.
"""
import json
import os
from pathlib import Path
import sys

from plugins.memory import discover_memory_providers, find_provider_dir, load_memory_provider

home = Path(os.environ["HERMES_HOME"]).resolve()
mode = sys.argv[1]
assert find_provider_dir("atmem").resolve() == home / "plugins" / "atmem"
provider = load_memory_provider("atmem")
assert provider is not None and provider.name == "atmem"

if mode == "discovery":
    from hermes_cli.web_server_memory import _discover_memory_provider_statuses, _require_memory_provider_ready
    from fastapi import HTTPException
    from hermes_cli.memory_setup import _post_setup_hook
    row = next(row for row in _discover_memory_provider_statuses() if row["name"] == "atmem")
    assert row["status"] == "unavailable" and row["available"] is False
    assert "CLI" in row["description"]
    assert any(name == "atmem" and not ready for name, _, ready in discover_memory_providers())
    try:
        _require_memory_provider_ready("atmem")
    except HTTPException as error:
        assert error.status_code == 400
    else:
        raise AssertionError("unconfigured provider passed dashboard activation gate")
    config = {"memory": {"provider": "builtin"}}
    assert _post_setup_hook(provider, config)
    assert config == {"memory": {"provider": "builtin"}}
    assert not provider.is_available()
    assert provider.get_status_config({})["available"] is False
    print(json.dumps({"native_discovery": True, "dashboard_status": row["status"],
                      "resolved_directory": str(find_provider_dir("atmem")), "setup_no_write": True}))
elif mode == "capture":
    assert provider.is_available()
    provider.initialize("capture-session", hermes_home=str(home), platform="cli")
    provider.on_turn_start(1, "My preferred editor is Neovim.")
    provider.sync_turn("My preferred editor is Neovim.", "Noted.", session_id="capture-session")
    assert provider.flush()
    assert provider.get_status_config({})["write_errors"] == 0
    provider.shutdown()
    print(json.dumps({"capture_flushed": True}))
elif mode == "recall":
    assert provider.is_available()
    provider.initialize("fresh-session", hermes_home=str(home), platform="cli")
    provider.on_turn_start(1, "What is my preferred editor?")
    assert "Neovim" in provider.prefetch("preferred editor", session_id="fresh-session")
    provider.shutdown()
    print(json.dumps({"new_process_new_session_recall": True}))
elif mode == "unsupported":
    assert provider.is_available()
    try:
        provider.initialize("gateway-session", hermes_home=str(home), platform="telegram")
    except PermissionError:
        pass
    else:
        raise AssertionError("unsupported host mode accepted")
    provider.on_turn_start(1, "My preferred editor is Neovim.")
    provider.sync_turn("My preferred editor is Neovim.", "", session_id="gateway-session")
    assert provider.prefetch("preferred editor", session_id="gateway-session") == ""
    assert provider.get_tool_schemas() == []
    assert provider.flush()
    provider.shutdown()
    print(json.dumps({"unsupported_mode_withholds": True}))
elif mode == "forced_selection":
    # The host picker writes selection directly; provider code cannot veto it.
    from hermes_cli.plugins_cmd import _save_memory_provider
    from hermes_cli.config import load_config
    _save_memory_provider("atmem")
    config = load_config()
    assert config["memory"]["provider"] == "atmem"
    from types import SimpleNamespace
    from agent.agent_init import _init_memory
    agent = SimpleNamespace(enabled_toolsets=["memory"], disabled_toolsets=[], tools=[])
    _init_memory(agent, config, False, "cli")
    assert agent._memory_manager is None
    assert agent._memory_store is not None
    assert not provider.is_available()
    print(json.dumps({"host_forced_selection_falls_back": True, "atmem_active": False}))
else:
    raise AssertionError("unknown test mode")
