"""Reference document RAG: encrypted AtMem persistence, SQLite FTS5 only in RAM.

This deterministic lexical provider requires no model, vector backend or new
database authority. Existing external RAGs can implement RagProvider instead.
"""

from __future__ import annotations

from hashlib import sha256
import re
import sqlite3
import time

from atmem.core.canonical import canonical_json
from atmem.evidence.models import EvidenceOperation
from atmem.feedback.store import FeedbackError
from atmem.knowledge.rag.contracts import RagHit, RagQuery, RagSource


def _key(source, document_id, chunk_id):
    return sha256(canonical_json([source.source_id, source.revision, document_id, chunk_id]).encode()).hexdigest()


class SQLiteRagProvider:
    def __init__(self, feedback):
        self.feedback = feedback

    def put_documents(self, owner_credential: str, source: RagSource, hits: tuple[RagHit, ...]) -> dict:
        principal = self.feedback._principal(owner_credential)
        try:
            principal.authorize(EvidenceOperation.GRANT, source.scope.evidence_scope())
        except PermissionError:
            raise FeedbackError("denied") from None
        if type(hits) is not tuple or not 1 <= len(hits) <= 128:
            raise ValueError("ingest 1..128 passages per batch")
        # Validate the complete batch before persisting any record.
        detached = tuple(RagHit.from_dict(hit.to_dict()) for hit in hits)
        keys = set()
        for hit in detached:
            key = _key(source, hit.document_id, hit.chunk_id)
            if key in keys or hit.scope != source.scope or hit.source_id != source.source_id or hit.revision != source.revision:
                raise FeedbackError("invalid_document_scope")
            keys.add(key)
        with self.feedback.owner_transaction(owner_credential, source.scope) as (tx, principal):
            current = tx.get("rag_source", source.source_id)
            if current != source.to_dict() or not source.active or source.egress != "none":
                raise FeedbackError("source_unavailable")
            added = 0
            for hit in detached:
                key = _key(source, hit.document_id, hit.chunk_id)
                value = {"collection_id": source.collection_id, "hit": hit.to_dict()}
                old = tx.get("rag_document", key)
                if old is not None:
                    if old != value:
                        raise FeedbackError("source_revision_conflict")
                    continue
                tx.put("rag_document", key, value, expected_revision=0)
                added += 1
            tx.audit(principal.principal_id, "rag_ingest", allowed=True, detail={"added": added})
        return {"added": added, "unchanged": len(hits)-added, "revision": source.revision}

    def search(self, source: RagSource, query: RagQuery, *, deadline: float) -> tuple[RagHit, ...]:
        if not source.active or source.egress != "none":
            raise FeedbackError("source_unavailable")
        terms = re.findall(r"\w+", query.query, flags=re.UNICODE)[:64]
        if not terms:
            return ()
        # Terms are quoted literals; callers never submit FTS operators or SQL.
        match = " OR ".join('"' + term.replace('"', '""') + '"' for term in terms)
        hits = {}
        with sqlite3.connect(":memory:") as index:
            index.execute("PRAGMA temp_store=MEMORY")
            index.execute("CREATE VIRTUAL TABLE passages USING fts5(identity UNINDEXED, body)")
            index.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
            with self.feedback.store.transaction(source.scope) as tx:
                if tx.get("rag_source", source.source_id) != source.to_dict():
                    raise FeedbackError("source_changed")
                for row in tx.iter_kind("rag_document"):
                    if time.monotonic() >= deadline:
                        raise FeedbackError("provider_timeout")
                    if row["collection_id"] != source.collection_id:
                        continue
                    hit = RagHit.from_dict(row["hit"])
                    if hit.scope != source.scope or hit.source_id != source.source_id or hit.revision != source.revision or not hit.matches(query):
                        continue
                    key = _key(source, hit.document_id, hit.chunk_id)
                    hits[key] = hit
                    if len(hits) > 5000:
                        raise FeedbackError("provider_corpus_budget_exhausted")
                    index.execute("INSERT INTO passages(identity,body) VALUES(?,?)", (key, hit.text))
            rows = index.execute("SELECT identity FROM passages WHERE passages MATCH ? ORDER BY bm25(passages),identity LIMIT ?",
                                 (match, query.limit)).fetchall()
            return tuple(hits[row[0]] for row in rows)

    def inspect(self, source: RagSource, document_id: str, chunk_id: str, *, deadline: float) -> RagHit:
        if time.monotonic() >= deadline:
            raise FeedbackError("provider_timeout")
        with self.feedback.store.transaction(source.scope) as tx:
            if tx.get("rag_source", source.source_id) != source.to_dict() or not source.active:
                raise FeedbackError("source_changed")
            row = tx.get("rag_document", _key(source, document_id, chunk_id))
            if row is None or row["collection_id"] != source.collection_id:
                raise FeedbackError("denied")
            hit = RagHit.from_dict(row["hit"])
            if hit.scope != source.scope or hit.revision != source.revision or hit.source_id != source.source_id:
                raise FeedbackError("invalid_document_scope")
            return hit
