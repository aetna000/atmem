"""Explicit macOS Codex filesystem/network profiles for replay qualification.

Shell-only probes spend no inference quota. Agent dispatch remains a separate
gated operation. No owner configuration or authentication file is modified.
"""
import json
from pathlib import Path
import subprocess


def permission_arguments(runtime_roots=()):
    files = {":root": "deny", ":minimal": "read", ":workspace_roots": {".": "write"},
             ":slash_tmp": "deny", ":tmpdir": "deny"}
    for root in runtime_roots:
        path = Path(root).resolve(strict=True)
        # Operator supplies only the dedicated interpreter/dependency roots.
        # Never accept a filesystem/home/workspace ancestor as a runtime.
        if not path.is_dir() or len(path.parts) < 4 or not path.name.startswith(("atmem-click-", "cpython-")):
            raise ValueError("dedicated benchmark runtime directory required")
        files[str(path)] = "read"
    entries = []
    for name, value in files.items():
        encoded = ("{" + ",".join(json.dumps(k) + "=" + json.dumps(v) for k, v in value.items()) + "}"
                   if isinstance(value, dict) else json.dumps(value))
        entries.append(json.dumps(name) + "=" + encoded)
    return ["-c", "permissions.click-replay.filesystem={" + ",".join(entries) + "}",
            "-c", "permissions.click-replay.network.enabled=false"]


def shell_probe(workspace: Path, *, denied_paths: tuple[Path, ...], runtime_roots=()):
    workspace = workspace.resolve(strict=True)
    if not workspace.is_dir() or not workspace.name.startswith("atmem-click-"):
        raise ValueError("dedicated benchmark workspace required")
    if not denied_paths or any(not p.is_file() for p in denied_paths):
        raise ValueError("probe requires actual existing denial canaries")
    # Test real opens, not access/stat: macOS may allow metadata for denied reads.
    command = ["codex", "sandbox", "-C", str(workspace), "-P", "click-replay", *permission_arguments(runtime_roots),
               "/bin/sh", "-c", 'for p do if /bin/cat "$p" >/dev/null 2>&1; then exit 41; fi; done; echo ISOLATION_PROBE_OK',
               "isolation-probe", *(str(p.resolve()) for p in denied_paths)]
    result = subprocess.run(command, capture_output=True, timeout=30)
    return {"format": "atmem-click-shell-isolation-probe-v1", "passed": result.returncode == 0 and
            result.stdout.strip() == b"ISOLATION_PROBE_OK", "exit_code": result.returncode,
            "denied_read_count": len(denied_paths), "qualification": "shell_read_barrier_only_not_agent_qualification"}
