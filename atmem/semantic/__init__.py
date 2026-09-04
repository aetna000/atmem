"""Derived local-vector retrieval with canonical AtMem authorization."""

from atmem.semantic.index import (
    SemanticIndex,
    SemanticIndexIntegrityError,
    default_index_path,
)
from atmem.semantic.health import (
    HardwareProfile,
    SemanticHealth,
    SemanticHealthReason,
    SemanticHealthStatus,
    SemanticManifest,
    evaluate_semantic_health,
    inspect_semantic_health,
    load_model_catalog,
    recommend_local_models,
)
from atmem.semantic.providers import (
    Embedder,
    HashingEmbedder,
    OllamaEmbedder,
    OpenAICompatibleEmbedder,
    SentenceTransformersEmbedder,
    create_embedder,
)

__all__ = [
    "Embedder",
    "HashingEmbedder",
    "HardwareProfile",
    "OllamaEmbedder",
    "OpenAICompatibleEmbedder",
    "SemanticIndex",
    "SemanticIndexIntegrityError",
    "SemanticHealth",
    "SemanticHealthReason",
    "SemanticHealthStatus",
    "SemanticManifest",
    "SentenceTransformersEmbedder",
    "create_embedder",
    "default_index_path",
    "evaluate_semantic_health",
    "inspect_semantic_health",
    "load_model_catalog",
    "recommend_local_models",
]
