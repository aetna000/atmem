"""Version-qualified Copilot event identity; no transcript ingestion."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
from uuid import UUID


QUALIFIED_VERSION = "1.0.98"
EVENTS = ("userPromptSubmitted", "postToolUse", "sessionEnd")


def copilot_home() -> Path:
    return Path(os.environ.get("COPILOT_HOME") or Path.home() / ".copilot").expanduser().resolve()


def _read_settings(path: Path) -> dict:
    # Copilot rewrites config.json as JSONC. Preserve comment-like text in
    # strings (especially paths and URLs), and accept trailing commas.
    with path.open("rb") as stream:
        raw = stream.read(1_000_001)
    if len(raw) > 1_000_000:
        raise ValueError("Copilot settings exceed limit")
    text = raw.decode("utf-8-sig")
    text = re.sub(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*[\s\S]*?\*/',
                  lambda match: match[0] if match[0].startswith('"') else " ", text)
    text = re.sub(r'"(?:\\.|[^"\\])*"|,(?=\s*[}\]])',
                  lambda match: match[0] if match[0].startswith('"') else "", text)
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("Copilot settings must be an object")
    return value


def require_workspace_trust(root: str | Path) -> None:
    try:
        value = _read_settings(copilot_home() / "config.json")
        folders = value.get("trustedFolders", [])
        trusted = isinstance(folders, list) and any(
            isinstance(folder, str) and Path(folder).expanduser().resolve() == Path(root).resolve()
            for folder in folders)
    except (OSError, ValueError, TypeError, AttributeError):
        trusted = False
    if not trusted:
        raise RuntimeError("Open copilot in this project and approve workspace trust, then retry AtMem enable")
    for path in (copilot_home() / "config.json", copilot_home() / "settings.json",
                 Path(root) / ".github/copilot/settings.json", Path(root) / ".github/copilot/settings.local.json"):
        if path.exists():
            settings = _read_settings(path)
            if settings.get("disableAllHooks") is True:
                raise RuntimeError("Copilot hooks are disabled; review disableAllHooks before AtMem enable")


def normalize_event(payload: dict) -> dict:
    event = payload.get("event")
    if event not in EVENTS:
        raise ValueError("Copilot requires an explicit supported host event")
    session = payload.get("sessionId")
    try:
        if not isinstance(session, str) or str(UUID(session)) != session:
            raise ValueError("invalid Copilot session")
    except (ValueError, AttributeError) as exc:
        raise ValueError("invalid Copilot session") from exc
    base = copilot_home()
    path = base / "session-state" / session / "events.jsonl"
    if any(part.is_symlink() for part in (path.parent.parent, path.parent, path)):
        raise ValueError("Copilot journal symlinks are not supported")
    native = {key: value for key, value in payload.items() if key != "event"}
    # Match exact input and a host-issued invocation ID, not a guessed turn ID.
    with path.open("rb") as stream:
        first = stream.readline(65537)
        if len(first) > 65536:
            raise ValueError("Copilot journal header exceeds limit")
        header = json.loads(first)
        if (not isinstance(header, dict) or not isinstance(header.get("data"), dict)
                or header.get("type") != "session.start" or header.get("data", {}).get("sessionId") != session
                or header["data"].get("copilotVersion") != QUALIFIED_VERSION):
            raise ValueError("unqualified Copilot journal version or session")
        stream.seek(0, 2)
        offset = max(0, stream.tell() - 2_000_000)
        stream.seek(offset)
        if offset:
            stream.readline()  # Discard the partial first line of the bounded tail.
        tail = stream.read(2_000_001)
    matches = set()
    completed = set()
    for line in tail.splitlines():
        try:
            value = json.loads(line)
        except ValueError:
            continue  # Concurrent writes may leave a partial unrelated final line.
        if not isinstance(value, dict) or not isinstance(value.get("data"), dict):
            continue
        data = value["data"]
        if value.get("type") == "hook.end" and isinstance(data.get("hookInvocationId"), str):
            completed.add(data["hookInvocationId"])
        if value.get("type") == "hook.start" and data.get("hookType") == event and data.get("input") == native:
            invocation = data.get("hookInvocationId")
            if isinstance(invocation, str) and str(UUID(invocation)) == invocation:
                matches.add(invocation)
    pending = matches - completed
    candidates = pending if pending else matches
    if len(candidates) != 1:
        raise ValueError("Copilot event has no unique journal invocation")
    invocation = candidates.pop()
    return {**payload, "turn_id": invocation, "tool_use_id": invocation}
