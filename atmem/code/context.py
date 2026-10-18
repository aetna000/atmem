"""Bounded, source-linked native coding-memory context packages."""

from __future__ import annotations

from hashlib import sha256
import time

from atmem.code.contracts import CodeContextPackage, CodeContextRequest
from atmem.code.formation import memory_subject_id
from atmem.memory import Memory


def source_current(store, request: CodeContextRequest, record: dict, repository_root: str | None) -> bool:
    """Conservative freshness for code-dependent user assertions, not preferences."""
    origin = store.code_document(request.scope.subject_id, request.scope.project_id, "origin", record["id"]) or {}
    if origin.get("code_memory_class") == "coding_experience":
        if repository_root is None:
            return False
        from atmem.knowledge.projections import CodeKnowledge
        from atmem.knowledge.contracts import SourceSnapshot, ExperienceProposal
        from atmem.knowledge.code.applicability import assess
        value = store.code_document(request.scope.subject_id, request.scope.project_id, "code-experience", origin["experience_proposal_id"])
        if not value or record["id"] not in value["formation"]["record_ids"]:
            return False
        # Use the shared source reader, not an enabled/indexed graph. No graph
        # is required to determine conservative source-anchor applicability.
        proposal, baseline = ExperienceProposal.from_dict(value["proposal"]), SourceSnapshot.from_dict(value["snapshot"])
        knowledge = CodeKnowledge.from_store(store, request.scope)
        from atmem.knowledge.code.environment import environment_digest
        environment = store.code_document(request.scope.subject_id, request.scope.project_id, "experience-environment", memory_subject_id(request.scope))
        identity = (environment["environment_sha256"] if environment and environment.get("assurance") == "producer_declared_tool_environment"
                    else environment_digest())
        try:
            current, _, _ = knowledge.capture(repository_root, identity, max_file_bytes=2_000_000, max_source_bytes=64_000_000)
        except (FileNotFoundError, ValueError, UnicodeError):
            return False
        return assess(proposal, baseline, current).status == "applicable"
    if origin.get("code_memory_class") == "preference" or repository_root is None:
        return True
    from pathlib import Path
    from atmem.code.identity import _git, repository_key
    root = Path(repository_root).resolve(strict=True)
    binding = store.code_project_binding(request.scope.subject_id, repository_key(root))
    if binding is None or binding["project_id"] != request.scope.project_id:
        raise PermissionError("context repository is not bound to the authorized project")
    revision = _git(root, "rev-parse", "HEAD")
    dirty = _git(root, "status", "--porcelain", "--untracked-files=normal", "--", ".",
                 ":(exclude).claude/settings.local.json", ":(exclude).codex/hooks.json", ":(exclude).codex/config.toml",
                 ":(exclude).muse/hooks.json", ":(exclude).grok/hooks/atmem-code.json", ":(exclude).github/hooks/atmem-code.json")
    return bool(revision and revision == origin.get("code_git_revision") and dirty == "")


def build_context(memory: Memory, request: CodeContextRequest, *, limit: int = 8, timeout_ms: int = 1000,
                  repository_root: str | None = None) -> CodeContextPackage:
    if not 1 <= limit <= 32:
        raise ValueError("context record limit must be between 1 and 32")
    if type(timeout_ms) is not int or not 1 <= timeout_ms <= 30000:
        raise ValueError("context timeout must be between 1 and 30000 milliseconds")
    deadline = time.monotonic() + timeout_ms / 1000
    subject = memory_subject_id(request.scope)
    records = memory.recall(
        subject, request.task, session_id=request.session_id,
        limit=limit, use_graph=False,
    )
    chunks: list[str] = []
    record_ids: list[str] = []
    total = 0
    for record in records:
        if time.monotonic() > deadline:
            return CodeContextPackage(request.request_id, "", sha256(b"").hexdigest(), ())
        if record["status"] != "active" or record["subject_id"] != subject:
            continue
        if not source_current(memory.store, request, record, repository_root):
            continue
        if time.monotonic() > deadline:
            return CodeContextPackage(request.request_id, "", sha256(b"").hexdigest(), ())
        content = str(record["content"])
        source = str(record.get("episode_id") or "source-unavailable")
        chunk = f"[AtMem Code {record['id']}; source {source}] {content}\n"
        encoded = chunk.encode("utf-8")
        if total + len(encoded) > request.max_context_bytes:
            continue
        chunks.append(chunk)
        record_ids.append(record["id"])
        total += len(encoded)
    body = "".join(chunks)
    return CodeContextPackage(
        request.request_id, body, sha256(body.encode("utf-8")).hexdigest(),
        tuple(record_ids),
    )
