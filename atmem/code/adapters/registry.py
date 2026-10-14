"""Construct only adapters whose activation probe can run on this host."""

from hashlib import sha256
import os
from pathlib import Path
import shlex
import sys

from atmem.code.adapters.claude import ClaudeAdapter
from atmem.code.adapters.probe import claude_probe
from atmem.code.hook import enroll_store
from atmem.evidence.crypto import load_existing_key


def verified_adapter(store, *, subject: str, project: str, root: str, host: str):
    if host != "claude" or os.name == "nt":
        raise RuntimeError(f"{host} automatic adapter is not yet verified on this platform")
    from atmem.code import hook
    directory = Path(store.path).resolve().parent / ".code-credentials"
    lane = store.code_document(subject, project, "host-scope", host) or {"profile_id": "shared", "agent_id": host}
    key = sha256((subject + project + host + lane["profile_id"] + lane["agent_id"]).encode()).hexdigest()
    credential_file = directory / (key + ".key")
    enroll_store(store, subject=subject, project=project, root=root, profile=lane["profile_id"], agent=lane["agent_id"],
                 host=host, credential_file=str(credential_file))
    command = shlex.join([sys.executable, str(Path(hook.__file__).resolve()), "--db", str(Path(store.path).resolve()),
                          "--subject", subject, "--project-id", project, "--credential-file", str(credential_file)])
    adapter = ClaudeAdapter(root, command)
    initial = adapter.probe()
    if initial.version == "unavailable":
        raise RuntimeError("Claude Code is not installed")
    adapter.verifier = lambda: claude_probe(store=store, subject=subject, project=project,
                                            root=Path(root).resolve(), credential=load_existing_key(credential_file), initial=initial,
                                            command=command)
    return adapter
