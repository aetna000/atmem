"""Construct only adapters whose activation probe can run on this host."""

from hashlib import sha256
import os
import platform
import re
from pathlib import Path
import shlex
import sys

from atmem.code.adapters.claude import ClaudeAdapter
from atmem.code.adapters.probe import claude_probe
from atmem.code.hook import enroll_store
from atmem.evidence.crypto import load_existing_key


def verified_adapter(store, *, subject: str, project: str, root: str, host: str):
    if (host not in {"claude", "copilot"} or (host == "claude" and os.name == "nt")
            or (host == "copilot" and platform.system() not in {"Darwin", "Windows"})):
        raise RuntimeError(f"{host} automatic adapter is not yet verified on this platform")
    from atmem.code import hook
    directory = Path(store.path).resolve().parent / ".code-credentials"
    lane = store.code_document(subject, project, "host-scope", host) or {"profile_id": "shared", "agent_id": host}
    key = sha256((subject + project + host + lane["profile_id"] + lane["agent_id"]).encode()).hexdigest()
    credential_file = directory / (key + ".key")
    enroll_store(store, subject=subject, project=project, root=root, profile=lane["profile_id"], agent=lane["agent_id"],
                 host=host, credential_file=str(credential_file))
    argv = [sys.executable, str(Path(hook.__file__).resolve()), "--db", str(Path(store.path).resolve()),
            "--subject", subject, "--project-id", project, "--credential-file", str(credential_file)]
    command = shlex.join(argv)
    if host == "copilot":
        from atmem.code.adapters.copilot import CopilotAdapter
        from atmem.code.adapters.copilot_events import QUALIFIED_VERSIONS, require_workspace_trust
        require_workspace_trust(root)
        adapter = CopilotAdapter(root, command, argv=argv)
    else:
        adapter = ClaudeAdapter(root, command)
    initial = adapter.probe()
    if initial.version == "unavailable":
        raise RuntimeError(f"{host} is not installed")
    verifier = claude_probe
    if host == "copilot":
        from atmem.code.adapters.copilot_probe import copilot_probe
        qualified = QUALIFIED_VERSIONS if platform.system() == 'Darwin' else ('1.0.98',)
        if not any(re.search(r"\b" + re.escape(version) + r"\b", initial.version) for version in qualified):
            raise RuntimeError("Copilot version is not qualified; expected " + ", ".join(qualified))
        verifier = copilot_probe
    adapter.verifier = lambda: verifier(store=store, subject=subject, project=project,
                                            root=Path(root).resolve(), credential=load_existing_key(credential_file), initial=initial,
                                            command=command, **({"argv": argv} if host == "copilot" else {}))
    return adapter
