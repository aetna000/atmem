"""Pinned AgentRunbook-R index baseline using its real search primitive.

This excludes AgentRunbook's model-assisted formation and query rewriting. It is
an offline reader-free index baseline, not a reproduction of published scores.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
import re
import sys
import time
from types import MethodType
from typing import Any, Mapping

import numpy as np

from ..contracts import CaseEvidenceResult
from ..normalizer import normalize_evidence


AGENTRUNBOOK_REVISION = "2cc8c540bdb87fe6761629b585e727e1c4704520"
AGENTRUNBOOK_OFFLINE_CONFIG = (
    "agentrunbook-r;real-search-entries;formation=identity;query-routing=all-pools;"
    "hash-bow-256;top-k-global=2"
)
AGENTRUNBOOK_OFFLINE_CONFIG_SHA256 = "sha256:" + hashlib.sha256(
    AGENTRUNBOOK_OFFLINE_CONFIG.encode()
).hexdigest()


def _hash_embedding(text: str) -> list[float]:
    vector = [0.0] * 256
    for token in re.findall(r"\w+", text.casefold()):
        bucket = int(hashlib.sha256(token.encode()).hexdigest()[:8], 16) % len(vector)
        vector[bucket] += 1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


class AgentRunbookROfflineAdapter:
    system = "agentrunbook-r-index-offline"

    def __init__(self, *, checkout: Path) -> None:
        self.checkout = checkout.resolve()

    def _load(self):
        checkout_text = str(self.checkout)
        if checkout_text not in sys.path:
            sys.path.insert(0, checkout_text)
        # Import through the package registry to respect its circular-import contract.
        from memory_modules.memory import AgentRunbookR

        module_path = Path(sys.modules[AgentRunbookR.__module__].__file__).resolve()
        if self.checkout not in module_path.parents:
            raise RuntimeError(f"AgentRunbook imported from unpinned path: {module_path}")
        return AgentRunbookR

    @staticmethod
    def _pool(category: str) -> str:
        if category in {"state_transition", "correction", "conflict"}:
            return "event"
        if category in {"procedure", "durable_rule"}:
            return "procedure"
        if category in {"failure_gotcha", "negative_premise"}:
            return "hint"
        return "raw_state"

    def run_case(self, case: Mapping[str, Any]) -> CaseEvidenceResult:
        started = time.perf_counter()
        selected_ranges: tuple[tuple[str, int, int], ...] = ()
        status = "not_found_within_budget"
        error: str | None = None
        try:
            AgentRunbookR = self._load()
            memory = AgentRunbookR({})

            def embed_texts(
                _self: object, texts: list[str], *, is_query: bool
            ) -> np.ndarray:
                del is_query
                return np.asarray([_hash_embedding(text) for text in texts], dtype=np.float32)

            memory._embed_texts = MethodType(embed_texts, memory)
            pools: dict[str, list[dict[str, Any]]] = {
                "raw_state": [], "event": [], "procedure": [], "hint": []
            }
            for source in case["sources"]:
                if str(source["scope"]) not in {"agent:a", "workspace:shared"}:
                    continue
                category = str(source.get("category", case["category"]))
                pools[self._pool(category)].append(
                    {"source_id": str(source["id"]), "text": str(source["text"])}
                )

            candidates: list[dict[str, Any]] = []
            for entries in pools.values():
                if not entries:
                    continue
                embeddings = np.asarray(
                    [_hash_embedding(str(entry["text"])) for entry in entries],
                    dtype=np.float32,
                )
                candidates.extend(
                    memory._search_entries(
                        entries=entries,
                        embeddings=embeddings,
                        query_text=str(case["query"]),
                        top_k=2,
                    )
                )
            candidates.sort(
                key=lambda item: (-float(item["score"]), item["entry"]["source_id"])
            )
            items = [str(item["entry"]["text"]) for item in candidates[:2]]
            normalized = normalize_evidence(items, case["sources"])
            selected_ranges = tuple(
                (item.source_id, item.start, item.end) for item in normalized
            )
            if selected_ranges:
                status = "sufficient"
            elif case.get("expected_status") == "withheld_by_policy":
                status = "withheld_by_policy"
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
            configuration_sha256=AGENTRUNBOOK_OFFLINE_CONFIG_SHA256,
            error=error,
        )
