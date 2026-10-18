"""Controlled native sessions, never production activation or owner trust."""
import json
import os
from pathlib import Path
import runpy
import subprocess
import tempfile

helpers = runpy.run_path(str(Path(__file__).with_name("host_process.py")))


def run_host(host, root, command, prompt, endpoint):
    root = Path(root)
    binary = os.environ.get("ATMEM_TEST_" + host.upper() + "_BINARY")
    if not binary:
        binary = helpers["cli_argv"](host)[0]
    environment = helpers["offline_environment"]()
    with tempfile.TemporaryDirectory(prefix="atmem-" + host + "-test-", ignore_cleanup_errors=True) as directory:
        home = Path(directory)
        environment.update(HOME=directory, USERPROFILE=directory, MUSE_NO_AUTO_UPDATE="1", MUSE_LOGIN="0")
        if os.name == "nt":
            for name in ("APPDATA", "LOCALAPPDATA"):
                folder = home / name
                folder.mkdir()
                environment[name] = str(folder)
            if host == "muse" and Path("C:/Program Files/Git/bin/bash.exe").is_file():
                environment["SHELL"] = "C:/Program Files/Git/bin/bash.exe"
        config = {"hooks": {"UserPromptSubmit": [{"hooks": [
            {"type": "command", "command": command, "timeout": 20}]}]}}
        if host == "muse" and os.name == "nt":
            config["hooks"]["UserPromptSubmit"][0]["hooks"][0]["commandWindows"] = command
        if host == "muse":
            hooks = root / ".muse/hooks.json"
            argv = [binary, "exec", "--provider", "meta", "--model", "muse-spark-1.3", "--base-url", endpoint.url,
                    "--api-key-stdin", "--trust-workspace", "--disable-reminders", "--no-foreign-personal-context",
                    "--no-session-log", "--disable-web-tools", "--disable-shell", "--disable-write",
                    "--max-model-steps", "1", "--reasoning-effort", "minimal", prompt]
            stdin = "offline-fixture-not-a-provider-key\n"
        else:
            grok_home = home / ".grok"
            grok_home.mkdir()
            environment.update(GROK_HOME=str(grok_home), GROK_MODELS_BASE_URL=endpoint.url,
                               XAI_API_KEY="offline-fixture-not-a-provider-key")
            (grok_home / "config.toml").write_text(
                '[cli]\nauto_update = false\n[features]\ntelemetry = false\n'
                '[model.atmem-probe]\nmodel = "atmem-probe"\napi_backend = "responses"\n'
                'base_url = ' + json.dumps(endpoint.url) + '\napi_key = "offline-fixture-not-a-provider-key"\n',
                encoding="utf-8")
            hooks = grok_home / "hooks/probe.json"
            argv = [binary, "-p", prompt, "--model", "atmem-probe", "--max-turns", "1",
                    "--disable-web-search", "--no-subagents", "--no-plan", "--output-format", "json"]
            stdin = None
        hooks.parent.mkdir(parents=True, exist_ok=True)
        hooks.write_text(json.dumps(config), encoding="utf-8")
        return subprocess.run(argv, input=stdin, cwd=root, env=environment,
                              capture_output=True, text=True, timeout=120, check=False)
