"""One scoped RAG boundary behind API, CLI and generic MCP clients."""

from __future__ import annotations

from contextvars import copy_context
from dataclasses import replace
import queue
import threading
import time
import uuid

from atmem.contracts.feedback import FeedbackScope, identifier
from atmem.evidence.models import EvidenceOperation
from atmem.feedback.store import FeedbackError, snapshot
from atmem.knowledge.rag.contracts import RagHit, RagQuery, RagSource


class RagService:
    def __init__(self, feedback, *, timeout_seconds: float = 5):
        if type(timeout_seconds) not in (float, int) or not 0 < timeout_seconds <= 30:
            raise ValueError("RAG read timeout must be within (0,30] seconds")
        self.feedback = feedback
        self.timeout_seconds = timeout_seconds
        self._providers = {}
        self._lock = threading.Lock()
        self._running = set()

    def register(self, owner_credential: str, source: RagSource, provider) -> dict:
        """Owner-only application configuration; never exposed to model tools."""
        principal = self.feedback._principal(owner_credential)
        try:
            principal.authorize(EvidenceOperation.GRANT, source.scope.evidence_scope())
        except PermissionError:
            raise FeedbackError("denied") from None
        if type(source) is not RagSource or not callable(getattr(provider, "search", None)) or not callable(getattr(provider, "inspect", None)):
            raise ValueError("registered source and search/inspect adapter required")
        with self.feedback.owner_transaction(owner_credential, source.scope) as (tx, principal):
            from atmem.feedback.recovery import revocation_key
            tombstone = tx.get("source_revocation", revocation_key(source.source_id, "rag"))
            if tombstone is not None and source.generation <= tombstone["generation"]:
                raise FeedbackError("source_revoked")
            old = tx.get("rag_source", source.source_id)
            if old is not None:
                prior = RagSource.from_dict(old)
                if old != source.to_dict() and source.generation != prior.generation + 1:
                    raise FeedbackError("stale_revision")
                if old == source.to_dict():
                    # Reattach an owner-configured adapter after application restart.
                    receipt = {"revision": tx.revision("rag_source", source.source_id)}
                else:
                    receipt = tx.put("rag_source", source.source_id, source.to_dict(),
                                     expected_revision=tx.revision("rag_source", source.source_id))
            else:
                expected_generation = tombstone["generation"] + 1 if tombstone else 1
                if source.generation != expected_generation:
                    raise FeedbackError("stale_revision")
                receipt = tx.put("rag_source", source.source_id, source.to_dict(), expected_revision=0)
            tx.audit(principal.principal_id, "rag_register", allowed=True)
        with self._lock:
            self._providers[(source.scope.content_digest, source.content_digest)] = provider
        return receipt

    def revoke(self, owner_credential: str, scope: FeedbackScope, source_id: str) -> None:
        principal = self.feedback._principal(owner_credential)
        try:
            principal.authorize(EvidenceOperation.GRANT, scope.evidence_scope())
        except PermissionError:
            raise FeedbackError("denied") from None
        with self.feedback.owner_transaction(owner_credential, scope) as (tx, principal):
            old = tx.get("rag_source", identifier(source_id))
            if old is None:
                raise FeedbackError("denied")
            source = RagSource.from_dict(old)
            tx.put("rag_source", source_id, replace(source, active=False, generation=source.generation+1).to_dict(),
                   expected_revision=tx.revision("rag_source", source_id))
            tx.audit(principal.principal_id, "rag_revoke", allowed=True)

    def sources(self, session) -> dict:
        with self.feedback._authorized(session, "search") as (tx, _):
            rows = [r for r in tx.list("rag_source") if r["active"]]
            return {"format": "atmem-rag-sources-v1", "sources": rows, "scope": session.scope.to_dict()}

    def attach_local(self, session) -> None:
        """Application startup: attach only pre-registered built-in local sources.

        This cannot register/change a source or load arbitrary adapter code.
        External providers must be attached by their trusted application owner.
        """
        from atmem.knowledge.rag.sqlite import SQLiteRagProvider

        with self.feedback._authorized(session, "search") as (tx, _):
            sources = [RagSource.from_dict(row) for row in tx.iter_kind("rag_source")
                       if row["active"] and row["provider_id"] == "sqlite-vault" and row["egress"] == "none"]
        with self._lock:
            for source in sources:
                self._providers[(source.scope.content_digest, source.content_digest)] = SQLiteRagProvider(self.feedback)

    def _source(self, tx, source_id):
        value = tx.get("rag_source", identifier(source_id))
        if value is None or not value["active"]:
            raise FeedbackError("denied")
        return RagSource.from_dict(value)

    def _bounded_read(self, source, invoke):
        key = (source.scope.content_digest, source.content_digest)
        with self._lock:
            provider = self._providers.get(key)
            if provider is None:
                raise FeedbackError("provider_unavailable")
            if key in self._running:
                raise FeedbackError("provider_busy")
            if len(self._running) >= 8:
                raise FeedbackError("provider_capacity")
            self._running.add(key)
        results = queue.Queue(maxsize=1)
        deadline = time.monotonic() + self.timeout_seconds
        context = copy_context()
        def run():
            try:
                results.put((True, context.run(invoke, provider, deadline)))
            except BaseException:
                # Provider exception text may contain credentials or private passages.
                results.put((False, None))
            finally:
                with self._lock:
                    self._running.discard(key)
        try:
            threading.Thread(target=run, daemon=True, name="atmem-rag-read").start()
        except RuntimeError:
            with self._lock:
                self._running.discard(key)
            raise FeedbackError("provider_unavailable") from None
        try:
            ok, value = results.get(timeout=max(0, deadline-time.monotonic()))
        except queue.Empty:
            # The abandoned read holds its slot until it actually finishes.
            raise FeedbackError("provider_timeout") from None
        if not ok:
            raise FeedbackError("provider_unavailable")
        return value

    def search(self, session, query: RagQuery, *, idempotency_key: str) -> dict:
        query = RagQuery.from_dict(query.to_dict())
        identifier(idempotency_key)
        attempt_id = "attempt-" + uuid.uuid4().hex
        with self.feedback._authorized(session, "search") as (tx, principal):
            source = self._source(tx, query.source_id)
            request = {"attempt_id": attempt_id, "source": source.to_dict(), "query": query.to_dict(),
                       "actor_id": principal.principal_id, "status": "pending"}
            tx.put("rag_attempt", attempt_id, request, expected_revision=0)
        try:
            result = self._search(session, query, idempotency_key=idempotency_key)
        except Exception as exc:
            code = exc.code if isinstance(exc, FeedbackError) else "retrieval_unavailable"
            self._finish_attempt(session, attempt_id, {**request, "status": "failed", "error": code})
            if isinstance(exc, FeedbackError):
                raise
            raise FeedbackError(code) from None
        self._finish_attempt(session, attempt_id, {**request, "status": "complete", "receipt_id": result["receipt_id"]})
        return result

    def _finish_attempt(self, session, attempt_id, value):
        try:
            with self.feedback._authorized(session, "search") as (tx, _):
                tx.put("rag_attempt", attempt_id, value, expected_revision=1)
        except FeedbackError:
            # Revocation may prohibit even completing the scoped trace. Retain
            # the original pending request as unknown, never invent success.
            return

    def _search(self, session, query: RagQuery, *, idempotency_key: str) -> dict:
        query = RagQuery.from_dict(query.to_dict())
        identifier(idempotency_key)
        with self.feedback._authorized(session, "search") as (tx, _):
            source = self._source(tx, query.source_id)
            payload = {"query": query.to_dict(), "source_sha256": source.content_digest}
            cached = tx.cached("rag_search", idempotency_key, payload)
            if cached is not None:
                return cached
        returned = self._bounded_read(source, lambda provider, deadline: provider.search(source, query, deadline=deadline))
        if type(returned) is not tuple or len(returned) > query.limit:
            raise FeedbackError("invalid_provider_result")
        hits, identities = [], set()
        for item in returned:
            if type(item) is not RagHit:
                raise FeedbackError("invalid_provider_result")
            try:
                hit = RagHit.from_dict(item.to_dict())
            except (AttributeError, ValueError, TypeError):
                raise FeedbackError("invalid_provider_result") from None
            identity = (hit.document_id, hit.chunk_id)
            if hit.scope != session.scope or hit.source_id != source.source_id or hit.revision != source.revision or identity in identities:
                raise FeedbackError("invalid_provider_result")
            identities.add(identity)
            if hit.matches(query):
                hits.append(hit.to_dict())
        # A result is bounded as one encrypted record. Refuse oversized evidence
        # instead of silently truncating a legal passage or its citation.
        try:
            snapshot(hits)
        except ValueError:
            raise FeedbackError("result_budget_exhausted") from None
        with self.feedback._authorized(session, "search") as (tx, principal):
            if self._source(tx, source.source_id) != source:
                raise FeedbackError("source_changed")
            def publish():
                receipt_id = "rag-" + uuid.uuid4().hex
                value = {"format": "atmem-rag-search-receipt-v1", "receipt_id": receipt_id,
                         "scope": session.scope.to_dict(), "source": source.to_dict(),
                         "query": query.to_dict(), "hits": hits, "untrusted_evidence": True,
                         "memory_admitted": False, "status": "complete", "completeness": "not_established",
                         "filtered": len(returned)-len(hits), "actor_id": principal.principal_id}
                tx.put("rag_receipt", receipt_id, value, expected_revision=0)
                return value
            return tx.once("rag_search", idempotency_key, payload, publish)

    def inspect(self, session, *, receipt_id: str, document_id: str, chunk_id: str) -> dict:
        """Inspect exactly the retained passage, while its source is still authorized."""
        for value in (receipt_id, document_id, chunk_id):
            identifier(value)
        with self.feedback._authorized(session, "inspect") as (tx, _):
            receipt = tx.get("rag_receipt", receipt_id)
            if receipt is None:
                raise FeedbackError("denied")
            source = self._source(tx, receipt["source"]["source_id"])
            if source.to_dict() != receipt["source"]:
                raise FeedbackError("source_changed")
            hit = next((v for v in receipt["hits"] if v["document_id"] == document_id and v["chunk_id"] == chunk_id), None)
            if hit is None:
                raise FeedbackError("denied")
            return {"format": "atmem-rag-inspect-receipt-v1", "receipt_id": receipt_id,
                    "hit": RagHit.from_dict(hit).to_dict(), "untrusted_evidence": True, "memory_admitted": False}
