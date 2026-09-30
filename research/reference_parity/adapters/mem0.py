"""Pinned Mem0 OSS reader-free adapter using its real raw-memory/search path."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
import re
import sys
import tempfile
import time
from typing import Any, Mapping

from ..contracts import CaseEvidenceResult
from ..normalizer import normalize_evidence


MEM0_REVISION = "d3891e48baa2c6e769f9cfa4003873bd6a85bc07"
MEM0_OFFLINE_CONFIG = "mem0-oss;infer=false;qdrant-local;hash-bow-256;top-k=2;threshold=0"
MEM0_OFFLINE_CONFIG_SHA256 = "sha256:" + hashlib.sha256(
    MEM0_OFFLINE_CONFIG.encode()
).hexdigest()


class HashEmbedding:
    """Deterministic no-network embedding used equally for add and search."""

    def __init__(self, config: object) -> None:
        self.config = config

    def embed(self, text: str, memory_action: str | None = None) -> list[float]:
        del memory_action
        vector = [0.0] * 256
        for token in re.findall(r"\w+", text.casefold()):
            bucket = int(hashlib.sha256(token.encode()).hexdigest()[:8], 16) % len(vector)
            vector[bucket] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


class Mem0OssAdapter:
    system = "mem0-oss-raw-offline"

    def __init__(self, *, checkout: Path) -> None:
        self.checkout = checkout.resolve()

    @staticmethod
    def _subject_for(scope: str) -> str:
        if scope in {"agent:a", "workspace:shared"}:
            return "local-user"
        return scope.replace(":", "-")

    def _load(self):
        checkout_text = str(self.checkout)
        if checkout_text not in sys.path:
            sys.path.insert(0, checkout_text)
        from mem0 import Memory as Mem0Memory
        from mem0.utils.factory import EmbedderFactory

        module_path = Path(sys.modules[Mem0Memory.__module__].__file__).resolve()
        if self.checkout not in module_path.parents:
            raise RuntimeError(f"Mem0 imported from unpinned path: {module_path}")
        EmbedderFactory.provider_to_class["fastembed"] = (
            "research.reference_parity.adapters.mem0.HashEmbedding"
        )
        return Mem0Memory

    def run_case(self, case: Mapping[str, Any]) -> CaseEvidenceResult:
        started = time.perf_counter()
        selected_ranges: tuple[tuple[str, int, int], ...] = ()
        status = "not_found_within_budget"
        error: str | None = None
        try:
            Memory = self._load()
            with tempfile.TemporaryDirectory(prefix="mem0-reference-") as directory:
                root = Path(directory)
                config = {
                    "vector_store": {
                        "provider": "qdrant",
                        "config": {
                            "collection_name": "reference",
                            "path": str(root / "qdrant"),
                            "embedding_model_dims": 256,
                        },
                    },
                    "llm": {
                        "provider": "openai",
                        "config": {"api_key": "unused", "model": "unused-offline"},
                    },
                    "embedder": {
                        "provider": "fastembed",
                        "config": {"embedding_dims": 256},
                    },
                    "history_db_path": str(root / "history.db"),
                }
                memory = Memory.from_config(config)
                for source in case["sources"]:
                    memory.add(
                        str(source["text"]),
                        user_id=self._subject_for(str(source["scope"])),
                        metadata={"source_id": str(source["id"])},
                        infer=False,
                    )
                result = memory.search(
                    str(case["query"]),
                    filters={"user_id": "local-user"},
                    top_k=2,
                    threshold=0.0,
                )
                items = [str(item.get("memory", "")) for item in result.get("results", [])]
                normalized = normalize_evidence(items, case["sources"])
                selected_ranges = tuple(
                    (item.source_id, item.start, item.end) for item in normalized
                )
                if selected_ranges:
                    status = "sufficient"
                elif case.get("expected_status") == "withheld_by_policy":
                    status = "withheld_by_policy"
                client = getattr(getattr(memory, "vector_store", None), "client", None)
                if client is not None and hasattr(client, "close"):
                    client.close()
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        return CaseEvidenceResult(
            system=self.system,
            case_id=str(case["id"]),
            split=str(case["split"]),
            status=status,
            selected_ranges=selected_ranges,
            forbidden_source_ids=tuple(str(v) for v in case.get("forbidden_source_ids", [])),
            elapsed_ms=(time.perf_counter() - started) * 1000,
            configuration_sha256=MEM0_OFFLINE_CONFIG_SHA256,
            error=error,
        )
