"""Protected local hook enrollment and host event normalization."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import hmac
import json
from pathlib import Path
import sys

if __package__ in {None, ""}:
    # Host commands use this exact installed script and interpreter, including
    # when a developer is testing a separate source worktree.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from atmem.code.application import CodeApplication, digest
from atmem.code.contracts import CodeContextRequest, CodeObservation, CodeScope
from atmem.code.identity import repository_key, _git
from atmem.code.receipts import CodeReceipts
from atmem.code.runtime import CodeRuntime
from atmem.code.service import CodeIntakeService
from atmem.evidence.crypto import load_existing_key, load_or_create_key
from atmem.memory import Memory


def opaque(prefix: str, value: str) -> str:
    return prefix + "-" + sha256(value.encode()).hexdigest()[:48]


def enroll(app: CodeApplication, *, project: str, root: str, profile: str, agent: str,
           host: str, credential_file: str) -> dict:
    app.authorize(project)
    return enroll_store(app.store, subject=app.subject_id, project=project, root=root, profile=profile,
                        agent=agent, host=host, credential_file=credential_file)


def enroll_store(store, *, subject: str, project: str, root: str, profile: str, agent: str,
                 host: str, credential_file: str) -> dict:
    if not store.code_project_exists(subject, project):
        raise PermissionError("project is not owned by subject")
    scope = CodeScope(subject, project, profile, agent)
    binding = store.code_project_binding(subject, repository_key(root))
    if binding is None or binding["project_id"] != project:
        raise PermissionError("hook repository binding mismatch")
    path = Path(credential_file).expanduser()
    if path.is_symlink():
        raise ValueError("hook credential cannot be a symlink")
    secret = load_or_create_key(path)
    value = {"scope": scope.to_dict(), "host": host, "repository_key": repository_key(root)}
    key = sha256(secret).hexdigest()
    previous = store.code_document(subject, project, "enrollment", key)
    if previous is not None and previous != value:
        raise ValueError("credential is already enrolled for another scope")
    store.put_code_document(subject, project, "enrollment", key, value)
    return {"credential_file": str(path.resolve()), "project_id": project, "host": host}


def handle(app: CodeApplication, *, project: str, credential: bytes, payload: dict) -> dict:
    app.authorize(project)
    enrollment = app.store.code_document(app.subject_id, project, "enrollment", sha256(credential).hexdigest())
    if enrollment is None:
        raise PermissionError("unknown hook credential")
    scope = CodeScope.from_dict(enrollment["scope"])
    host = enrollment["host"]
    cwd = str(payload.get("cwd") or "")
    challenge = app.store.code_document(app.subject_id, project, "probe", sha256(credential).hexdigest())
    if (challenge is not None and payload.get("prompt") == challenge["prompt"]
            and cwd and repository_key(cwd) == challenge.get("repository_key", enrollment["repository_key"])
            and datetime.fromisoformat(challenge["expires_at"]) > datetime.now(timezone.utc)):
        if host == "copilot":
            from atmem.code.adapters.copilot_events import normalize_event
            normalize_event(payload)
        challenge["hook_seen"] = True
        app.store.put_code_document(app.subject_id, project, "probe", sha256(credential).hexdigest(), challenge)
        if host == "copilot":
            return {"additionalContext": challenge["canary"]}
        return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": challenge["canary"]}}
    if not cwd or repository_key(cwd) != enrollment["repository_key"]:
        raise PermissionError("hook event came from another repository")
    row = app.store.code_installation(app.subject_id, project, host)
    if row is None or not row["enabled"]:
        return {}
    if host == "copilot":
        from atmem.code.adapters.copilot_events import normalize_event
        payload = normalize_event(payload)
    event = payload.get("hook_event_name") or payload.get("hookEventName") or payload.get("event")
    mapping = {"userPromptSubmitted": "UserPromptSubmit", "user_prompt_submit": "UserPromptSubmit",
               "postToolUse": "PostToolUse", "post_tool_use": "PostToolUse",
               "sessionStart": "SessionStart", "sessionEnd": "SessionEnd"}
    event = mapping.get(event, event)
    session_raw = payload.get("session_id") or payload.get("sessionId")
    if not isinstance(session_raw, str) or not session_raw:
        raise ValueError("host event has no session identifier")
    session = opaque("session", session_raw)
    session_secret = hmac.new(credential, session.encode(), sha256).digest()
    intake = CodeIntakeService(app.store, scope=scope, host=host, session_id=session,
                               secret=session_secret, enabled=True)
    runtime = CodeRuntime(app.memory, intake)
    settings = app.settings(project)
    if event in {"PreCompact", "SessionEnd", "Stop"}:
        if settings["auto_capture"]:
            runtime.process_pending()
        return {}
    if event == "SessionStart":
        # Per-prompt recall already ran; startup recall would inject twice.
        return {}
    if event not in {"UserPromptSubmit", "PostToolUse"}:
        return {}
    turn_raw = payload.get("turn_id") or payload.get("promptId") or payload.get("prompt_id")
    if not isinstance(turn_raw, str) or not turn_raw:
        # Content alone cannot distinguish a retry from two identical prompts.
        # Withhold until the host supplies a stable turn/event identifier.
        raise ValueError("host event has no stable turn identifier; automatic capture is unverified")
    turn = opaque("turn", turn_raw)
    kind = "user_turn" if event == "UserPromptSubmit" else "tool_outcome"
    content = payload.get("prompt") if kind == "user_turn" else json.dumps({
        "tool": payload.get("tool_name") or payload.get("toolName"),
        "result": payload.get("tool_response") or payload.get("toolResult") or payload.get("toolResultText"),
    }, ensure_ascii=False)
    if not isinstance(content, str) or not content.strip() or len(content.encode()) > 32768:
        return {}
    tool_id = str(payload.get("tool_use_id") or payload.get("toolUseId") or "")
    event_id = opaque("event", session + turn + event + tool_id)
    clock = app.store.code_document(app.subject_id, project, "hook-event", event_id)
    if clock is None:
        clock = {"observed_at": datetime.now(timezone.utc).isoformat()}
        app.store.put_code_document(app.subject_id, project, "hook-event", event_id, clock)
    observation = CodeObservation(event_id, session, turn, host, kind, content,
                                  clock["observed_at"], f"{host}:{session}:{event_id}",
                                  _git(Path(cwd), "rev-parse", "HEAD"), scope)
    if kind != "user_turn":
        if settings["auto_capture"]:
            intake.submit(observation.to_dict(), intake.sign(observation))
            runtime.process_pending()
        return {}
    task_text = content.encode("utf-8")[:8192].decode("utf-8", errors="ignore")
    request = CodeContextRequest(opaque("request", session + turn), session, turn, task_text, settings["max_context_bytes"], scope)
    result = runtime.on_user_turn(request, observation, intake.sign(observation), repository_root=cwd)
    package = result["context"]
    if host == "grok" or not package.content:
        return {}
    CodeReceipts(app.store).submitted(request, package, host=host)
    if host == "copilot":
        return {"additionalContext": package.content}
    return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": package.content}}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--credential-file", required=True)
    parser.add_argument("--host-event", choices=("userPromptSubmitted", "postToolUse", "sessionEnd"))
    args = parser.parse_args()
    memory = None
    try:
        raw = sys.stdin.buffer.read(131073)
        if len(raw) > 131072:
            raise ValueError("hook event exceeds size limit")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("hook input must be an object")
        if args.host_event:
            if any(payload.get(key) not in (None, args.host_event) for key in ("event", "hook_event_name", "hookEventName")):
                raise ValueError("host event argument conflicts with payload")
            payload["event"] = args.host_event
        memory = Memory(args.db, auto_vectors=False)
        result = handle(CodeApplication(memory, subject_id=args.subject), project=args.project_id,
                        credential=load_existing_key(args.credential_file), payload=payload)
        print(json.dumps(result, ensure_ascii=False))
    except (ValueError, PermissionError, OSError, RuntimeError) as exc:
        # Keep the coding host usable on an unavailable memory dependency.
        print(json.dumps({"systemMessage": f"AtMem Code unavailable: {type(exc).__name__}"}))
    finally:
        if memory is not None:
            memory.close()


if __name__ == "__main__":
    main()
