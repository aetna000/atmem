"""Small subscription-only CLI connectivity probe in a volatile session home.

Not a task trial, adapter qualification or benchmark result. No API key is used.
"""
import argparse
import base64
from pathlib import Path
import json
import os
import plistlib
import shutil
import subprocess
from uuid import uuid4

from atmem.evidence import EvidencePrincipal, EvidenceRole, EvidenceScope
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.sandbox import permission_arguments


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ram-root", type=Path, required=True)
    parser.add_argument("--auth-file", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.ram_root.resolve(strict=True)
    if root.parent != Path("/Volumes") or not root.name.startswith("AtMemReplayRAM-20261017"):
        raise ValueError("explicit benchmark volatile volume required")
    # Verify this is still the RAM-backed image we created, not an arbitrary
    # mounted disk with a coincidentally matching name.
    info = plistlib.loads(subprocess.check_output(["hdiutil", "info", "-plist"]))
    if not any(str(image.get("image-path", "")).startswith("ram://") and any(
            entity.get("mount-point") == str(root) for entity in image.get("system-entities", []))
            for image in info.get("images", [])):
        raise RuntimeError("volatile benchmark image is unavailable")
    auth = args.auth_file
    if auth.is_symlink() or not auth.is_file() or auth.stat().st_size > 65536:
        raise ValueError("existing regular CLI authentication file required")
    auth_value = json.loads(auth.read_bytes())
    if (auth_value.get("auth_mode") not in (None, "chatgpt") or auth_value.get("OPENAI_API_KEY")
            or not isinstance(auth_value.get("tokens"), dict)):
        raise ValueError("probe requires existing ChatGPT subscription authentication, not an API key")
    runtime = root / "atmem-click-cli-runtime"
    runtime.mkdir(mode=0o700, exist_ok=True)
    executable = runtime / "codex"
    if not executable.exists():
        shutil.copy2(Path(shutil.which("codex")).resolve(strict=True), executable)
    trial = root / ("probe-" + uuid4().hex)
    cli_home, workspace = trial / "cli-home", trial / "atmem-click-probe"
    cli_home.mkdir(mode=0o700, parents=True)
    workspace.mkdir(mode=0o700)
    temporary = trial / "tmp"
    temporary.mkdir(mode=0o700)
    shutil.copyfile(auth, cli_home / "auth.json")
    (cli_home / "auth.json").chmod(0o600)
    command = [str(executable), "exec", "--ignore-user-config", "--ignore-rules", "--strict-config",
               "--ephemeral", "--json", "-m", "gpt-6-luna", "-C", str(workspace), "--skip-git-repo-check",
               "-c", 'default_permissions="click-replay"', "-c", 'approval_policy="never"',
               "-c", 'web_search="disabled"', *permission_arguments((runtime,)),
               "Connectivity probe only: reply exactly READY. Do not use any tools."]
    env = {"PATH": "/usr/bin:/bin:/opt/homebrew/bin", "CODEX_HOME": str(cli_home),
           "LANG": "en_US.UTF-8", "TMPDIR": str(temporary)}
    completed = subprocess.run(command, env=env, capture_output=True, timeout=120)
    scope = EvidenceScope("benchmark", "local-operator", "click-20261017")
    evidence = ReplayEvidence(args.evidence_root, vault_id="click-20261017", scope=scope)
    principal = EvidencePrincipal("local-benchmark-operator", EvidenceRole.ADMINISTRATOR, scope)
    retained = evidence.capture(run_id="connectivity-" + trial.name, kind="cli.connectivity_probe", principal=principal,
                                payload={"command_without_auth": command, "exit_code": completed.returncode,
                                         "stdout_base64": base64.b64encode(completed.stdout).decode(),
                                         "stderr_base64": base64.b64encode(completed.stderr).decode(),
                                         "real_solver_task": False})
    events = []
    for line in completed.stdout.splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            pass
    ready = any(e.get("type") == "item.completed" and e.get("item", {}).get("text", "").strip() == "READY" for e in events)
    print(json.dumps({"exit_code": completed.returncode, "ready": ready, "model": "gpt-6-luna",
                      "event_types": sorted({e.get("type", "unknown") for e in events}),
                      "evidence": retained, "task_trial": False}))


if __name__ == "__main__":
    main()
