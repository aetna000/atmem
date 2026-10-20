"""Bounded native-host probes. Run directly; not a successful activation test.

All homes, hooks, model traffic and receipts are confined to the output directory.
No genuine provider keys or owner configuration are used.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import platform
import runpy
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
helpers = runpy.run_path(str(HERE / "host_process.py"))
Endpoint = runpy.run_path(str(HERE / "responses_endpoint.py"))["ResponsesEndpoint"]


def probe(host, binary, output, timeout):
    root = output / host
    root.mkdir(parents=True, exist_ok=False)
    home = root / "home"
    home.mkdir()
    project = root / "project with spaces"
    project.mkdir()
    environment = helpers["offline_environment"]()
    environment.update(HOME=str(home), USERPROFILE=str(home), MUSE_NO_AUTO_UPDATE="1",
                       MUSE_LOGIN="0", GROK_HOME=str(home / ".grok"))
    # An isolated HOME alone is insufficient on native Windows.
    if os.name == "nt":
        for name in ("APPDATA", "LOCALAPPDATA"):
            folder = home / name
            folder.mkdir()
            environment[name] = str(folder)
    command = helpers["hook_command"]([sys.executable, str(HERE / "grok_muse_hook.py")])
    config = {"hooks": {event: [{"hooks": [{"type": "command", "command": command,
                      "timeout": 10}]}] for event in ("UserPromptSubmit", "PreLLMCall", "Stop")}}
    if host == "muse" and os.name == "nt":
        for groups in config["hooks"].values():
            groups[0]["hooks"][0]["commandWindows"] = command
    hooks = (home / ".grok/hooks/probe.json") if host == "grok" else (project / ".muse/hooks.json")
    hooks.parent.mkdir(parents=True, exist_ok=True)
    hooks.write_text(json.dumps(config), encoding="utf-8")
    result = {"host": host, "binary": binary, "platform": platform.platform(),
              "python": platform.python_version(), "timeout_seconds": timeout,
              "scope": "isolated global Grok hooks or trusted Muse project; local fixed-response endpoint",
              "automatic_activation_qualified": False}
    with Endpoint() as endpoint:
        if host == "grok":
            environment.update(XAI_API_KEY="offline-probe-not-a-provider-key",
                               GROK_MODELS_BASE_URL=endpoint.url)
            (home / ".grok/config.toml").write_text(
                '[cli]\nauto_update = false\n[features]\ntelemetry = false\n'
                '[model.atmem-probe]\nmodel = "atmem-probe"\napi_backend = "responses"\n'
                'base_url = ' + json.dumps(endpoint.url) + '\napi_key = "offline-probe-not-a-provider-key"\n',
                encoding="utf-8")
            argv = [binary, "-p", "Reply probe complete.", "--model", "atmem-probe", "--max-turns", "1",
                    "--disable-web-search", "--no-subagents", "--no-plan", "--output-format", "json"]
            stdin = None
        else:
            argv = [binary, "exec", "--json", "--provider", "meta", "--model", "muse-spark-1.3", "--base-url", endpoint.url,
                    "--api-key-stdin", "--trust-workspace", "--disable-reminders", "--no-foreign-personal-context",
                    "--no-session-log", "--disable-web-tools", "--disable-shell", "--disable-write",
                    "--max-model-steps", "1", "--reasoning-effort", "minimal", "Reply probe complete."]
            stdin = "offline-probe-not-a-provider-key\n"
        started = time.monotonic()
        try:
            completed = subprocess.run(argv, input=stdin, cwd=project, env=environment,
                                       capture_output=True, text=True, timeout=timeout, check=False)
            result.update(returncode=completed.returncode, timed_out=False)
            stdout, stderr = completed.stdout, completed.stderr
        except subprocess.TimeoutExpired as error:
            result.update(returncode=None, timed_out=True)
            stdout, stderr = error.stdout or b"", error.stderr or b""
        result["elapsed_seconds"] = round(time.monotonic() - started, 3)
        for name, value in (("stdout", stdout), ("stderr", stderr)):
            if isinstance(value, bytes):
                value = value.decode("utf-8", errors="replace")
            (root / (name + ".txt")).write_text(value, encoding="utf-8")
            result[name + "_tail"] = value[-3000:]
        (root / "model-requests.json").write_text(json.dumps(endpoint.requests, indent=2), encoding="utf-8")
        result["model_requests"] = len(endpoint.requests)
        result["canary_in_model_request"] = "ATMEM_CODE_CANARY_7e46a92f" in json.dumps(endpoint.requests)
    log = project / "probe-hooks.jsonl"
    payloads = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []
    result["hook_events"] = [item.get("hook_event_name") for item in payloads]
    result["prompt_payload_keys"] = [sorted(item) for item in payloads if item.get("hook_event_name") in {"UserPromptSubmit", "user_prompt_submit"}]
    (root / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result), flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--grok", required=True)
    parser.add_argument("--muse", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(probe, host, binary, args.output, args.timeout)
                   for host, binary in (("grok", args.grok), ("muse", args.muse))]
        results = [future.result() for future in futures]
    (args.output / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
