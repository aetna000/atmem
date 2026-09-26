"""AtMem Hermes directory plugin; the host needs no AtMem Python dependency."""
import json
import os
from pathlib import Path
import stat

from .client import HermesRPCClient
from .provider import create_provider


def _private_read(path, limit):
    if os.name == "nt":
        raise RuntimeError("native Windows credential ACL qualification is pending; use a qualified WSL installation")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise PermissionError("Hermes connection files must be owner-only regular files")
        value = os.read(descriptor, limit + 1)
        if len(value) > limit:
            raise ValueError("Hermes connection file exceeds its size limit")
        return value.decode("utf-8")
    finally:
        os.close(descriptor)


SETUP_HINT = ("AtMem local CLI preview: connection is unavailable. "
              "Run atmem hermes status --hermes-home PATH for this profile. "
              "Installation alone does not activate memory; keep the current provider selected.")


def _unavailable_provider():
    from agent.memory_provider import MemoryProvider

    class UnconfiguredAtMem(MemoryProvider):
        name = "atmem"

        def is_available(self):
            return False

        def unavailable_reason(self):
            return SETUP_HINT

        def initialize(self, session_id, **kwargs):
            raise RuntimeError(SETUP_HINT)

        def get_tool_schemas(self):
            return []

        def post_setup(self, hermes_home, config):
            print(SETUP_HINT)

        def get_status_config(self, config=None):
            return {"available": False, "platform": "local CLI only", "setup": SETUP_HINT}

    return UnconfiguredAtMem()


def _configured_provider():
    home = Path(__file__).resolve().parents[2]
    private = home / ".atmem"
    if private.is_symlink():
        raise PermissionError("Hermes connection directory cannot be a symbolic link")
    info = private.stat()
    if info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise PermissionError("Hermes connection directory must be owner-only")
    config = json.loads(_private_read(private / "connection.json", 16384))
    if not isinstance(config, dict):
        raise ValueError("invalid connection")
    if config.get("format") != "atmem-hermes-connection-v1":
        raise ValueError("unsupported AtMem Hermes connection")
    if Path(config["hermes_home"]).resolve() != home:
        raise PermissionError("AtMem connection belongs to another Hermes profile")
    client = HermesRPCClient(config["endpoint"], _private_read(private / "credential", 256).strip(),
                             profile_id=config["profile_id"], user_id=config.get("user_id"), timeout=1.0)
    return create_provider(client, hermes_home=str(home))


def register(ctx):
    try:
        provider = _configured_provider() if os.name != "nt" else _unavailable_provider()
    except Exception:
        # Discovery must remain possible, but never echo credential/config data.
        provider = _unavailable_provider()
    ctx.register_memory_provider(provider)
