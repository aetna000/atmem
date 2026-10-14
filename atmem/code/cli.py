"""Code commands share the dashboard's authorized application methods."""

from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path

from atmem.code.application import CodeApplication
from atmem.code.identity import repository_key
from atmem.code.install import CodeInstall
from atmem.memory import Memory


COMMANDS = ("setup", "status", "doctor", "enable", "disable", "uninstall", "projects",
            "search", "inspect", "correct", "forget", "config", "clear", "routes", "route-set", "route-delete",
            "graph-index", "graph-search", "graph-status", "keygen", "export", "import", "enroll", "reviews", "review", "attach")


def add_commands(parser, *, default_db: str) -> None:
    commands = parser.add_subparsers(dest="code_command")
    for name in COMMANDS:
        command = commands.add_parser(name)
        command.add_argument("--project", default=".", help="Repository directory")
        command.add_argument("--project-id", help="Explicit already-owned project identity")
        command.add_argument("--db", default=default_db)
        command.add_argument("--subject", default="local")
        command.add_argument("--profile", default=None)
        command.add_argument("--agent", default=None)
        command.add_argument("--host", choices=("muse", "claude", "grok", "copilot", "codex"), default="codex")
        command.add_argument("--json", action="store_true")
        if name == "setup":
            command.add_argument("--apply", action="store_true", help="Record disabled setup after preview")
        if name in {"search", "graph-search"}:
            command.add_argument("query", nargs="?", default="")
        if name == "search":
            command.add_argument("--type", dest="memory_class")
            command.add_argument("--source")
            command.add_argument("--status", default="active")
            command.add_argument("--after")
            command.add_argument("--before")
            command.add_argument("--limit", type=int, default=100)
        if name in {"inspect", "correct", "forget"}:
            command.add_argument("record_id")
        if name == "correct":
            command.add_argument("text")
        if name == "config":
            command.add_argument("--set", dest="changes", help="JSON object of settings to change")
        if name == "clear":
            command.add_argument("--preview-token", help="Apply exactly the previously previewed selection")
        if name == "route-set":
            command.add_argument("route_file", help="JSON route referencing an existing delegated registration")
        if name == "route-delete":
            command.add_argument("route_id")
        if name == "review":
            command.add_argument("event_id")
            command.add_argument("decision", choices=("approve", "reject"))
        if name == "keygen":
            command.add_argument("directory")
        if name == "enroll":
            command.add_argument("--credential-file", required=True)
        if name == "attach":
            command.add_argument("--confirm-remote-change", action="store_true")
        if name == "export":
            command.add_argument("destination")
            command.add_argument("--recipient-key", required=True)
            command.add_argument("--signing-key", required=True)
            command.add_argument("--signing-public-key", required=True)
        if name == "import":
            command.add_argument("source")
            command.add_argument("--recipient-secret-key", required=True)
            command.add_argument("--trusted-signing-key", required=True)
            command.add_argument("--preview-token")


def read_key(path: str) -> bytes:
    candidate = Path(path).expanduser()
    if candidate.is_symlink() or not candidate.is_file() or candidate.stat().st_size > 16384:
        raise ValueError("key must be a bounded regular file")
    if os.name != "nt" and candidate.stat().st_mode & 0o077:
        raise PermissionError("key file must have private permissions")
    return base64.b64decode(candidate.read_text(encoding="ascii").strip(), validate=True)


def keygen(directory: str) -> dict:
    from atmem.evidence.crypto import generate_recipient_keypair, generate_signing_keypair
    root = Path(directory).expanduser()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.is_symlink():
        raise ValueError("key directory cannot be a symlink")
    names = ("recipient.public", "recipient.secret", "signing.public", "signing.secret")
    if any((root / name).exists() for name in names):
        raise FileExistsError("key files already exist; choose another directory")
    recipient_public, recipient_secret = generate_recipient_keypair()
    signing_public, signing_secret = generate_signing_keypair()
    for name, key in zip(names, (recipient_public, recipient_secret, signing_public, signing_secret)):
        descriptor = os.open(root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="ascii") as handle:
            handle.write(base64.b64encode(key).decode() + "\n")
    return {"directory": str(root.resolve()), "files": list(names), "suite": "ML-KEM-768+AES-256-GCM+ML-DSA-65"}


def run(args: argparse.Namespace) -> dict:
    command = args.code_command
    if command == "keygen":
        return keygen(args.directory)
    if command == "doctor":
        from atmem.store.sqlite import SQLiteStore
        store = SQLiteStore()
        try:
            return CodeInstall(store).doctor(args.host)
        finally:
            store.close()
    memory = Memory(args.db, auto_vectors=False)
    try:
        installer = CodeInstall(memory.store)
        common = {"project": args.project, "subject_id": args.subject, "host": args.host}
        if command == "setup":
            return installer.setup(**common, profile_id=args.profile or "shared", agent_id=args.agent or args.host, apply=args.apply)
        if command in {"status", "enable", "disable", "uninstall"}:
            return getattr(installer, command)(**common)
        app = CodeApplication(memory, subject_id=args.subject)
        if command == "projects":
            return app.projects()
        if command == "import":
            from atmem.code.portable import CodePortable
            portable = CodePortable(app)
            bundle = json.loads(Path(args.source).read_text(encoding="utf-8"))
            value = portable.open(bundle, recipient_secret_key=read_key(args.recipient_secret_key),
                                  trusted_signing_public_key=read_key(args.trusted_signing_key))
            return (portable.restore(value, root=args.project, preview_token=args.preview_token) if args.preview_token else
                    portable.preview(value, root=args.project))
        binding = memory.store.code_project_binding(args.subject, repository_key(args.project))
        project = args.project_id or (binding["project_id"] if binding else None)
        if project is None:
            raise ValueError("run atmem code setup --apply for this repository first")
        app.authorize(project)
        body = {"project_id": project}
        if command == "attach":
            return app.dispatch("project-attach", {**body, "root": args.project, "profile": args.profile or "shared",
                "agent": args.agent or args.host, "confirm_remote_change": args.confirm_remote_change})
        if command == "enroll":
            from atmem.code.hook import enroll
            return enroll(app, project=project, root=args.project, profile=args.profile or "shared",
                          agent=args.agent or args.host, host=args.host, credential_file=args.credential_file)
        if command == "export":
            from atmem.code.portable import CodePortable
            portable = CodePortable(app)
            bundle = portable.export(project, recipient_public_key=read_key(args.recipient_key),
                                     signing_public_key=read_key(args.signing_public_key), signing_secret_key=read_key(args.signing_key))
            with open(args.destination, "x", encoding="utf-8") as handle:
                json.dump(bundle, handle)
            return {"exported": True, "path": str(Path(args.destination).resolve()), "project_id": project}
        if command == "search":
            body.update({key: getattr(args, key) for key in ("query", "profile", "agent", "status", "memory_class", "source", "after", "before", "limit")})
        elif command in {"inspect", "forget", "correct"}:
            body["record_id"] = args.record_id
            if command == "correct":
                body["text"] = args.text
        elif command == "config" and args.changes is not None:
            body["changes"] = json.loads(args.changes)
        elif command == "clear":
            body.update(profile=args.profile, agent=args.agent)
            command = "clear" if args.preview_token else "clear-preview"
            body["preview_token"] = args.preview_token
        elif command == "route-set":
            body["route"] = json.loads(Path(args.route_file).read_text(encoding="utf-8"))
        elif command == "route-delete":
            body["route_id"] = args.route_id
        elif command == "review":
            body.update(event_id=args.event_id, decision=args.decision)
        elif command.startswith("graph-"):
            body.update(root=args.project, query=getattr(args, "query", ""))
        return app.dispatch(command, body)
    finally:
        memory.close()
