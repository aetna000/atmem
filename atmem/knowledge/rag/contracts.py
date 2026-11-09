"""Scoped document-provider inputs and original-passage results."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Literal, Protocol
from urllib.parse import urlsplit

from atmem.contracts.feedback import FeedbackScope, Wire, identifier, iso_date


@dataclass(frozen=True)
class RagSource(Wire):
    format = "atmem-rag-source-v1"
    source_id: str
    scope: FeedbackScope
    provider_id: str
    collection_id: str
    revision: str
    egress: Literal["none", "remote"]
    active: bool = True
    generation: int = 1

    def __post_init__(self):
        super().__post_init__()
        identifier(self.revision)
        if self.generation < 1:
            raise ValueError("positive source generation required")


@dataclass(frozen=True)
class RagQuery(Wire):
    format = "atmem-rag-query-v1"
    source_id: str
    query: str
    limit: int = 5
    jurisdiction: str | None = None
    as_of: str | None = None

    def __post_init__(self):
        super().__post_init__()
        if not self.query.strip() or len(self.query.encode()) > 4096 or not 1 <= self.limit <= 50:
            raise ValueError("bounded nonempty query and limit 1..50 required")
        if self.jurisdiction is not None:
            identifier(self.jurisdiction)
        iso_date(self.as_of)


@dataclass(frozen=True)
class RagHit(Wire):
    format = "atmem-rag-hit-v1"
    source_id: str
    scope: FeedbackScope
    revision: str
    document_id: str
    chunk_id: str
    title: str
    citation: str
    locator: str
    text: str
    text_sha256: str
    jurisdiction: str | None = None
    effective_from: str | None = None
    effective_to: str | None = None

    def __post_init__(self):
        super().__post_init__()
        identifier(self.revision)
        for value in (self.title, self.citation, self.locator, self.text):
            if not value.strip():
                raise ValueError("passage and citation provenance required")
        if len(self.text.encode()) > 32_768 or len(self.title.encode()) > 1024 or len(self.locator.encode()) > 1024 or len(self.citation.encode()) > 2048:
            raise ValueError("passage/provenance exceeds bound")
        if sha256(self.text.encode()).hexdigest() != self.text_sha256:
            raise ValueError("passage digest mismatch")
        if urlsplit(self.citation).username is not None or urlsplit(self.citation).password is not None:
            raise ValueError("credentials forbidden in citation")
        if self.jurisdiction is not None:
            identifier(self.jurisdiction)
        iso_date(self.effective_from)
        iso_date(self.effective_to)
        if self.effective_from is not None and self.effective_to is not None and self.effective_to <= self.effective_from:
            raise ValueError("empty or reversed effective interval")

    def matches(self, query: RagQuery) -> bool:
        if query.source_id != self.source_id:
            return False
        if query.jurisdiction is not None and query.jurisdiction != self.jurisdiction:
            return False
        if query.as_of is not None:
            # Unknown start is not proof that a source was effective on a date.
            if self.effective_from is None or query.as_of < self.effective_from:
                return False
            if self.effective_to is not None and query.as_of >= self.effective_to:
                return False
        return True


class RagProvider(Protocol):
    """Application-owned adapter; must honor deadline and fixed authority scope.

    Credentials and connection configuration stay inside the adapter. Search
    results are external evidence; AtMem validates scope/provenance again.
    """

    def search(self, source: RagSource, query: RagQuery, *, deadline: float) -> tuple[RagHit, ...]: ...

    def inspect(self, source: RagSource, document_id: str, chunk_id: str, *, deadline: float) -> RagHit: ...
