import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from atmem.adapters.hermes.package import plugin_files


@pytest.fixture
def plugin(tmp_path, monkeypatch):
    source = os.environ.get("HERMES_SOURCE")
    if not source:
        pytest.skip("HERMES_SOURCE required for native provider package checks")
    monkeypatch.syspath_prepend(str(Path(source).resolve()))
    home = tmp_path / "hermes"
    target = home / "plugins" / "atmem"
    target.mkdir(parents=True)
    for name, content in plugin_files().items():
        (target / name).write_bytes(content)
    private = home / ".atmem"
    private.mkdir(mode=0o700)
    config = {"format": "atmem-hermes-connection-v1", "hermes_home": str(home),
              "endpoint": "http://127.0.0.1:9", "profile_id": "test"}
    (private / "connection.json").write_text(json.dumps(config))
    (private / "connection.json").chmod(0o600)
    (private / "credential").write_text("hermes_test.credential")
    (private / "credential").chmod(0o600)
    # Load as a directory package, the same relative-import layout Hermes uses.
    import sys
    name = "atmem_packaged_hermes_test"
    spec = importlib.util.spec_from_file_location(name, target / "__init__.py")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module, private


def test_directory_package_registers_native_provider_without_atmem_imports(plugin):
    module, _ = plugin
    providers = []
    module.register(SimpleNamespace(register_memory_provider=providers.append))
    from agent.memory_provider import MemoryProvider
    assert isinstance(providers[0], MemoryProvider)
    assert providers[0].name == "atmem"
    assert providers[0].is_available() is False
    for name, payload in plugin_files().items():
        if name in {"__init__.py", "client.py"}:
            assert b"from atmem" not in payload
    providers[0].shutdown()


@pytest.mark.skipif(os.name == "nt", reason="native Windows ACL profile not qualified")
def test_shared_or_symlinked_credentials_are_rejected(plugin):
    module, private = plugin
    (private / "credential").chmod(0o644)
    providers = []
    module.register(SimpleNamespace(register_memory_provider=providers.append))
    assert providers[-1].is_available() is False
    assert "connection is unavailable" in providers[-1].unavailable_reason()
    (private / "credential").chmod(0o600)
    (private / "credential").rename(private / "original")
    (private / "credential").symlink_to(private / "original")
    module.register(SimpleNamespace(register_memory_provider=providers.append))
    assert providers[-1].is_available() is False


def test_missing_configuration_is_discoverable_without_network(plugin, monkeypatch):
    module, private = plugin
    (private / "connection.json").unlink()
    monkeypatch.setattr(module.HermesRPCClient, "_call", lambda *a: pytest.fail("discovery made RPC"))
    providers = []
    module.register(SimpleNamespace(register_memory_provider=providers.append))
    provider = providers[0]
    assert provider.name == "atmem"
    assert not provider.is_available()
    assert provider.get_tool_schemas() == []
    assert provider.prefetch("secret") == ""
    config = {"memory": {"provider": "builtin"}}
    provider.post_setup(str(private.parent), config)
    assert config == {"memory": {"provider": "builtin"}}
    assert provider.get_status_config({})["available"] is False
    with pytest.raises(RuntimeError):
        provider.initialize("test")


@pytest.mark.parametrize("value", ['[]', '{"endpoint":"credential-canary"}', 'invalid credential-canary'])
def test_bad_config_diagnostics_do_not_echo_secrets(plugin, value):
    module, private = plugin
    (private / "connection.json").write_text(value)
    providers = []
    module.register(SimpleNamespace(register_memory_provider=providers.append))
    assert not providers[0].is_available()
    assert "credential-canary" not in str(providers[0].get_status_config({}))


@pytest.mark.parametrize("failure", ["integer_endpoint", "recursive_json", "fifo", "missing_directory"])
def test_discovery_survives_all_invalid_connection_shapes(plugin, failure):
    module, private = plugin
    config = private / "connection.json"
    if failure == "integer_endpoint":
        value = json.loads(config.read_text())
        value["endpoint"] = 9
        config.write_text(json.dumps(value))
    elif failure == "recursive_json":
        config.write_text("[" * 2000 + "]" * 2000)
    elif failure == "fifo":
        if not hasattr(os, "mkfifo"):
            pytest.skip("POSIX FIFO check")
        config.unlink()
        os.mkfifo(config, 0o600)
    else:
        config.unlink()
        (private / "credential").unlink()
        private.rmdir()
    providers = []
    module.register(SimpleNamespace(register_memory_provider=providers.append))
    assert not providers[0].is_available()
