from __future__ import annotations

import pytest

from atmem import Memory
from atmem.semantic import HashingEmbedder
from atmem.semantic import SemanticIndex
from atmem.semantic.health import load_model_catalog
from atmem.semantic.providers import OpenAICompatibleEmbedder


def test_catalog_profiles_are_complete_and_exactly_describe_preprocessing() -> None:
    required = {
        "provider", "model", "revision", "dimensions", "distance",
        "normalization", "query_prefix", "document_prefix",
        "preprocessing_version", "quality_class", "license",
    }
    for profile in load_model_catalog()["models"]:
        assert required <= profile.keys()
        assert profile["dimensions"] > 0
        assert profile["distance"] == "cosine"
        assert profile["normalization"] == "l2"


def test_provider_identity_changes_when_revision_or_preprocessing_changes(monkeypatch) -> None:
    left = OpenAICompatibleEmbedder(
        "fixture/model", endpoint="http://127.0.0.1:9999", model_version="rev-1"
    )
    right = OpenAICompatibleEmbedder(
        "fixture/model", endpoint="http://127.0.0.1:9999", model_version="rev-2"
    )
    assert left.identity["revision"] == "rev-1"
    assert left.identity != right.identity
    assert left.identity["distance"] == "cosine"
    assert left.identity["license"] == "operator-supplied"


def test_hashing_profile_is_diagnostic_and_complete() -> None:
    identity = HashingEmbedder(dimensions=32).identity
    assert identity["dimensions"] == 32
    assert identity["distance"] == "cosine"
    assert identity["quality_class"] == "diagnostic"


def test_unknown_preprocessing_version_fails_closed(monkeypatch) -> None:
    embedder = OpenAICompatibleEmbedder(
        "fixture/model", endpoint="http://127.0.0.1:9999", model_version="rev-1"
    )
    embedder.profile["preprocessing_version"] = "future-v99"
    with pytest.raises(ValueError, match="unsupported embedding preprocessing"):
        embedder.embed_query("query")


class _ExactEmbedder:
    def __init__(self, *, query_prefix: str = "query: ") -> None:
        self.query_prefix = query_prefix

    @property
    def identity(self):
        return {
            "provider": "fixture-production", "model": "fixture/model",
            "version": "sha256:fixture", "revision": "sha256:fixture",
            "dimensions": 2, "distance": "cosine", "normalization": "l2",
            "query_prefix": self.query_prefix, "document_prefix": "document: ",
            "preprocessing_version": "atmem-embedding-text-v1",
            "quality_class": "production", "license": "Apache-2.0",
        }

    def embed_documents(self, texts):
        return [[1.0, 0.0] for _ in texts]

    def embed_query(self, text):
        return [1.0, 0.0]


def test_exact_profile_survives_restart_and_changed_prefix_requires_rebuild(tmp_path) -> None:
    memory = Memory(tmp_path / "memory.db")
    memory.remember("u1", "I prefer aisle seats.")
    path = tmp_path / "semantic.db"
    index = SemanticIndex(path)
    try:
        index.build(memory, "u1", _ExactEmbedder())
    finally:
        index.close()
    reopened = SemanticIndex(path)
    try:
        assert reopened.search(memory, "u1", "seat", _ExactEmbedder())
        with pytest.raises(ValueError, match="query_prefix mismatch"):
            reopened.search(memory, "u1", "seat", _ExactEmbedder(query_prefix="q: "))
    finally:
        reopened.close()
        memory.close()
