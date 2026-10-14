"""Bounded, source-linked native coding-memory context packages."""

from __future__ import annotations

from hashlib import sha256

from atmem.code.contracts import CodeContextPackage, CodeContextRequest
from atmem.code.formation import memory_subject_id
from atmem.memory import Memory


def build_context(memory: Memory, request: CodeContextRequest, *, limit: int = 8) -> CodeContextPackage:
    if not 1 <= limit <= 32:
        raise ValueError("context record limit must be between 1 and 32")
    subject = memory_subject_id(request.scope)
    records = memory.recall(
        subject, request.task, session_id=request.session_id,
        limit=limit, use_graph=False,
    )
    chunks: list[str] = []
    record_ids: list[str] = []
    total = 0
    for record in records:
        if record["status"] != "active" or record["subject_id"] != subject:
            continue
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
