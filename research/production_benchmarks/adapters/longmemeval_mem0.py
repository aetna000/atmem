"""Inert LongMemEval-V2 adapter for the pinned open-source Mem0 engine."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys

from memory_modules.memory import Memory, register_memory


MEM0_COMMIT = "d3891e48baa2c6e769f9cfa4003873bd6a85bc07"
EMBEDDING_DIMENSIONS = 768


class HashEmbedding:
    """Content-blind deterministic embedding shared by formation and query."""

    def __init__(self, config: object) -> None:
        self.config = config

    def embed(self, text: str, memory_action: str | None = None) -> list[float]:
        del memory_action
        vector = [0.0] * EMBEDDING_DIMENSIONS
        for token in re.findall(r"\w+", text.casefold()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSIONS
            vector[bucket] += 1.0 if digest[4] & 1 else -1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@register_memory
class Mem0Memory(Memory):
    memory_type = "mem0_oss"

    def __init__(self, memory_params: dict[str, object]) -> None:
        super().__init__(memory_params)
        checkout = Path(str(memory_params.get("checkout") or "")).expanduser().resolve()
        if not checkout.is_dir():
            raise RuntimeError("Mem0 OSS adapter requires a pinned checkout")
        checkout_text = str(checkout)
        if checkout_text in sys.path:
            sys.path.remove(checkout_text)
        sys.path.insert(0, checkout_text)
        os.environ.setdefault("MEM0_TELEMETRY", "False")
        from mem0 import Memory as Mem0
        from mem0.utils.factory import EmbedderFactory

        imported = Path(sys.modules[Mem0.__module__].__file__).resolve()
        if checkout not in imported.parents:
            raise RuntimeError(f"Mem0 imported from unpinned path: {imported}")
        EmbedderFactory.provider_to_class["fastembed"] = (
            "memory_modules.mem0_oss.HashEmbedding"
        )
        self._Memory = Mem0
        self.root = Path(str(memory_params["storage_path"])).expanduser().resolve()
        self.records_path = self.root / "records.jsonl"
        self._memory = self._open()

    def _open(self):
        self.root.mkdir(parents=True, exist_ok=True)
        config = {
            "vector_store": {"provider": "qdrant", "config": {
                "collection_name": "longmemeval",
                "path": str(self.root / "qdrant"),
                "embedding_model_dims": EMBEDDING_DIMENSIONS,
            }},
            "llm": {"provider": "openai", "config": {
                "api_key": "unused", "model": "unused-infer-false",
            }},
            "embedder": {"provider": "fastembed", "config": {
                "embedding_dims": EMBEDDING_DIMENSIONS,
            }},
            "history_db_path": str(self.root / "history.db"),
        }
        return self._Memory.from_config(config)

    def insert(self, trajectory: dict[str, object]) -> None:
        trajectory_id = str(trajectory.get("id") or "").strip()
        states = trajectory.get("states")
        if not trajectory_id or not isinstance(states, list):
            raise ValueError("trajectory requires a non-empty id and states list")
        records = [{
            "source_id": f"{trajectory_id}:metadata",
            "text": _canonical({
                key: trajectory[key]
                for key in ("id", "domain", "environment", "goal", "outcome", "start_url", "actions")
                if key in trajectory
            }),
        }]
        records.extend({
            "source_id": f"{trajectory_id}:state:{index}",
            "text": _canonical(state),
        } for index, state in enumerate(states) if isinstance(state, dict))
        with self.records_path.open("a", encoding="utf-8") as handle:
            for record in records:
                self._memory.add(
                    record["text"], user_id="longmemeval-public",
                    metadata={"source_id": record["source_id"]}, infer=False,
                )
                handle.write(_canonical(record) + "\n")

    def query(self, query: str, query_image: str | None = None) -> list[dict[str, str]]:
        del query_image
        result = self._memory.search(
            query, filters={"user_id": "longmemeval-public"},
            top_k=int(self.memory_params.get("top_k", 20)), threshold=0.0,
        )
        texts = [
            str(row.get("memory") or "")
            for row in result.get("results", [])
            if str(row.get("memory") or "").strip()
        ]
        if not texts:
            return []
        return [{"type": "text", "value": "\n\n".join(texts)}]

    def _close(self) -> None:
        client = getattr(getattr(self._memory, "vector_store", None), "client", None)
        if client is not None and hasattr(client, "close"):
            client.close()

    def _save_backend(self, output_dir: Path) -> None:
        self._close()
        try:
            shutil.copytree(self.root, output_dir / "mem0", dirs_exist_ok=True)
        finally:
            self._memory = self._open()

    def _load_backend(self, input_dir: Path) -> None:
        source = input_dir / "mem0"
        if not source.is_dir():
            raise FileNotFoundError(f"saved Mem0 state is missing: {source}")
        self._close()
        # Qdrant may remove its lock file immediately after ``close`` while
        # Python 3.12's rmtree is traversing the directory. Python 3.13 ignores
        # missing descendants; retain that behavior on every supported Python
        # without hiding permission or I/O failures.
        for attempt in range(3):
            if not self.root.exists():
                break
            try:
                shutil.rmtree(self.root)
                break
            except FileNotFoundError:
                if attempt == 2 and self.root.exists():
                    raise
        shutil.copytree(source, self.root)
        self._memory = self._open()

    @classmethod
    def reconcile_loaded_memory_config(cls, saved_config, requested_config):
        if requested_config is None:
            return saved_config
        if saved_config.get("memory_type") != cls.memory_type or requested_config.get("memory_type") != cls.memory_type:
            raise RuntimeError("loaded Mem0 memory type differs")
        saved = dict(saved_config["memory_params"])
        requested = dict(requested_config["memory_params"])
        saved.pop("storage_path", None)
        requested_storage = requested.pop("storage_path", None)
        if not requested_storage or requested != saved:
            raise RuntimeError("loaded Mem0 parameters differ beyond storage_path")
        return {"memory_type": cls.memory_type, "memory_params": {
            **saved, "storage_path": requested_storage,
        }}
