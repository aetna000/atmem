"""Run with an installed wheel interpreter: python -I this_file HERMES_SOURCE.

This checks wheel contents and the native provider ABI, not the full agent loop.
"""
import importlib.util
from importlib.metadata import version
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace

import atmem
from atmem.adapters.hermes.package import plugin_files
from atmem.hermes_install import install, inspect_install


def main():
    assert "site-packages" in str(Path(atmem.__file__).resolve())
    assert "agent.memory_provider" not in sys.modules
    payload = plugin_files()
    assert set(payload) == {"__init__.py", "provider.py", "client.py", "plugin.yaml"}
    assert f"version: {version('atmem')}" in payload["plugin.yaml"].decode()
    sys.path.insert(0, str(Path(sys.argv[1]).resolve()))
    from agent.memory_provider import MemoryProvider
    with tempfile.TemporaryDirectory(prefix="installed-hermes-payload-") as temporary:
        home = Path(temporary).resolve()
        plugin = home / "plugins" / "atmem"
        assert install(home, apply=True)["applied"]
        if len(sys.argv) > 2:
            script = Path(__file__).with_name("native_hermes_probe.py").resolve()
            source = str(Path(sys.argv[1]).resolve())
            bootstrap = ("import sys,os,runpy; from pathlib import Path; source=sys.argv.pop(1); "
                         "sys.path.insert(0,source); import hermes_bootstrap; "
                         "os.environ['HERMES_HOME']=sys.argv.pop(1); "
                         "runpy.run_path(sys.argv.pop(1),run_name='__main__')")
            result = subprocess.run([sys.argv[2], "-I", "-c", bootstrap, source, str(home), str(script), "discovery"],
                                    env={**os.environ, "HERMES_HOME": str(Path(source).parent),
                                         "HERMES_ENABLE_PROJECT_PLUGINS": "0"},
                                    capture_output=True, text=True, timeout=60, cwd=home)
            assert result.returncode == 0, result.stdout + result.stderr
            assert '"native_discovery": true' in result.stdout
            assert inspect_install(home)["state"] == "installed"
        private = home / ".atmem"
        private.mkdir(mode=0o700)
        config = {"format": "atmem-hermes-connection-v1", "hermes_home": str(home),
                  "endpoint": "http://127.0.0.1:9", "profile_id": "installed-payload"}
        (private / "connection.json").write_text(json.dumps(config))
        (private / "connection.json").chmod(0o600)
        (private / "credential").write_text("hermes_test.credential")
        (private / "credential").chmod(0o600)
        spec = importlib.util.spec_from_file_location("hermes_installed_atmem", plugin / "__init__.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        providers = []
        module.register(SimpleNamespace(register_memory_provider=providers.append))
        assert isinstance(providers[0], MemoryProvider)
        assert providers[0].is_available() is False
        providers[0].shutdown()
    print(json.dumps({"check": "installed-wheel-provider-payload", "passed": True,
                      "native_discovery_checked": len(sys.argv) > 2,
                      "package_version": version("atmem"), "full_agent_run": False}))


if __name__ == "__main__":
    main()
