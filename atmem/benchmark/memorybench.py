"""Isolated MemoryBench adapter using AtMem admission and governed context.

Raw conversation chunks are explicitly imported as benchmark documents. This
profile measures retrieval, not fact extraction or full black-box capture.
No questions, reference answers, or benchmark labels enter ingestion.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import uuid

from atmem import Memory
from atmem.contracts import AuthorityScope, ContextRequest, RecallRequest
from atmem.semantic import SemanticIndex, default_index_path
from atmem.semantic.providers import HashingEmbedder, OpenAICompatibleEmbedder


PROFILE = "atmem-memorybench-raw-hybrid-v1"


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def chunks(text: str, maximum: int = 1800):
    while text:
        end = min(len(text), maximum)
        if end < len(text):
            boundary = text.rfind("\n", maximum // 2, end)
            if boundary > 0:
                end = boundary
        part, text = text[:end], text[end:].lstrip("\n")
        if part.strip():
            yield part


class BenchmarkStore:
    def __init__(self, root: Path, container: str, *, embedding: str = "openai"):
        if not isinstance(container, str) or not container.strip():
            raise ValueError("containerTag is required")
        if embedding not in {"openai", "hashing"}:
            raise ValueError("embedding must be openai or hashing")
        self.root = root.expanduser().resolve()
        self.directory = self.root / digest(container)
        self.database = self.directory / "memory.db"
        self.embedding = embedding
        self.scope = AuthorityScope("benchmark-user", "benchmark-agent", "benchmark-workspace")

    def _memory(self):
        if self.directory.is_symlink():
            raise ValueError("invalid benchmark container")
        self.directory.mkdir(parents=True, exist_ok=True)
        return Memory(self.database, auto_vectors=False, retain_query_text=False)

    def _embedder(self):
        if self.embedding == "hashing":
            return HashingEmbedder()
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError("OPENAI_API_KEY is required for the OpenAI benchmark profile")
        return OpenAICompatibleEmbedder(
            "text-embedding-3-small", endpoint="https://api.openai.com",
            api_key=key, dimensions=1536, timeout=60,
        )

    def ingest(self, sessions: list[dict]) -> dict:
        # Persist each successful chunk via AtMem's idempotent admission. A
        # crashed batch may be retried without discarding the previous corpus.
        ids = []
        memory = self._memory()
        try:
            for session in sessions:
                session_id = session.get("sessionId")
                if not isinstance(session_id, str) or not session_id:
                    raise ValueError("sessionId is required")
                messages = session.get("messages")
                if not isinstance(messages, list):
                    raise ValueError("messages must be an array")
                metadata = session.get("metadata") or {}
                date = metadata.get("formattedDate") or metadata.get("date") or "unknown"
                header = f"Session: {session_id}; Date: {date}"
                lines = []
                for message in messages:
                    if message.get("role") not in {"user", "assistant"} or not isinstance(message.get("content"), str):
                        raise ValueError("invalid benchmark message")
                    speaker = str(message.get("speaker") or message["role"])
                    lines.append(f"{speaker}: {message['content']}")
                for index, text in enumerate(chunks("\n".join(lines), maximum=1600)):
                    fingerprint = digest([session_id, index, text])
                    text = f"Source chunk {fingerprint}\n{header}\n{text}"
                    result = memory.remember(
                        self.scope.subject_id, text, session_id=session_id,
                        interpreted_fact=text,
                        interpreted_fact_key=f"benchmark.{fingerprint}",
                        source_type="user_message", turn_id=fingerprint,
                        raw={"interpreter": PROFILE, "sensitivity": "public"},
                    )
                    records = result.get("records") or []
                    duplicates = result.get("duplicate_ids") or []
                    if not records and not duplicates:
                        raise RuntimeError("AtMem did not admit a benchmark chunk")
                    ids.extend(str(row["id"]) for row in records)
                    ids.extend(str(record_id) for record_id in duplicates)
            return {"documentIds": list(dict.fromkeys(ids)), "profile": PROFILE}
        finally:
            memory.close()

    def index(self) -> dict:
        memory = self._memory()
        try:
            index = SemanticIndex(default_index_path(self.database), policy=memory.policy)
            try:
                report = index.build(memory, self.scope.subject_id, self._embedder(), batch_size=32)
                return {"indexed": True, "profile": PROFILE, "report": report}
            finally:
                index.close()
        finally:
            memory.close()

    def search(self, query: str, *, limit: int = 10, budget: int = 16000, threshold: float = 0.3) -> list[dict]:
        if not query.strip() or not 1 <= limit <= 50 or not 1 <= budget <= 100000:
            raise ValueError("invalid query, limit or context budget")
        if not -1 <= threshold <= 1:
            raise ValueError("invalid cosine similarity threshold")
        memory = self._memory()
        try:
            lexical = memory.recall(self.scope.subject_id, query, limit=100, min_score=0)
            index = SemanticIndex(default_index_path(self.database), policy=memory.policy)
            try:
                semantic = index.search(memory, self.scope.subject_id, query, self._embedder(), limit=100, min_similarity=threshold)
            finally:
                index.close()
            scores: dict[str, float] = {}
            for ranking in (lexical, semantic):
                for rank, row in enumerate(ranking, 1):
                    record_id = str(row.get("record_id") or row.get("id"))
                    scores[record_id] = scores.get(record_id, 0) + 1 / (60 + rank)
            ordered = sorted(scores, key=lambda key: (-scores[key], key))[:limit]
            request = RecallRequest(
                request_id=f"benchmark-{uuid.uuid4().hex}", scope=self.scope,
                query=query, limit=limit, candidate_limit=100, context_budget_chars=budget,
                egress_class="remote" if self.embedding == "openai" else "local",
            )
            candidates = memory.create_candidate_set_v1(request, [
                {"record_id": record_id, "score": scores[record_id]} for record_id in ordered
            ])
            package = memory.prepare_context_v1(ContextRequest(
                context_id=f"benchmark-{uuid.uuid4().hex}",
                candidate_set_id=candidates.candidate_set_id, scope=self.scope,
                record_ids=tuple(row.record_id for row in candidates.candidates), budget_chars=budget,
            ))
            # Return the actual governed context once, not the unbounded candidate
            # texts. The answering harness must consume exactly this payload.
            if not package.record_ids:
                return []
            return [{"content": package.context, "recordIds": list(package.record_ids),
                     "sessionIds": list(dict.fromkeys(
                         str(memory.store.get_record(self.scope.subject_id, rid).get("source_session_id"))
                         for rid in package.record_ids)),
                     "profile": PROFILE, "embedding": self.embedding}]
        finally:
            memory.close()

    def clear(self) -> dict:
        if self.directory.parent != self.root or self.directory.is_symlink():
            raise ValueError("invalid benchmark container")
        if self.directory.exists():
            shutil.rmtree(self.directory)
        return {"cleared": True}


def main():
    try:
        value = json.load(sys.stdin)
        root = Path(os.environ.get("ATMEM_BENCHMARK_ROOT", "data/providers/atmem"))
        store = BenchmarkStore(root, value["containerTag"], embedding=value.get("embedding", "openai"))
        operation = value["operation"]
        if operation == "ingest":
            result = store.ingest(value["sessions"])
        elif operation == "index":
            result = store.index()
        elif operation == "search":
            result = store.search(value["query"], limit=int(value.get("limit", 10)), budget=int(value.get("budget", 16000)), threshold=float(value.get("threshold", 0.3)))
        elif operation == "clear":
            result = store.clear()
        else:
            raise ValueError("unknown benchmark operation")
        print(json.dumps(result, default=str))
    except Exception as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
