#!/usr/bin/env python3
"""Real local Mem0/Qdrant/Ollama fixture; dummy data only, no Storizon claim."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys

os.environ.setdefault("MEM0_TELEMETRY", "false")
from smoke_delegated_transport import fixture
from atmem.provider_adapters.mem0 import Mem0ContextProvider

FACT = "The fictional travel club codeword is ORCHID-731."
OTHER = "The other user's private fictional codeword is CEDAR-992."


def provider_factory(root, topology):
    from mem0 import Memory
    memory = Memory.from_config({
        "vector_store": {"provider": "qdrant", "config": {
            "collection_name": "atmem_roleplay", "path": str(root / "qdrant"),
            "embedding_model_dims": 768,
        }},
        "embedder": {"provider": "ollama", "config": {
            "model": "nomic-embed-text:latest", "ollama_base_url": "http://127.0.0.1:11434",
        }},
        "llm": {"provider": "ollama", "config": {
            "model": "qwen3:1.7b", "ollama_base_url": "http://127.0.0.1:11434",
        }},
        "history_db_path": str(root / "mem0-history.db"),
    })
    workspace = topology["primary_workspace_id"]
    for text, user, agent, app in [
        (FACT, "owner", "main", workspace),
        (OTHER, "other-user", "main", workspace),
        ("Wrong agent secret is MAPLE-123.", "owner", "other-agent", workspace),
        ("Wrong workspace secret is BIRCH-456.", "owner", "main", "other-workspace"),
    ]:
        memory.add(text, user_id=user, agent_id=agent, metadata={"app_id": app}, infer=False)

    class Client:
        def search(self, query, *, filters, top_k):
            result = memory.search(query, filters=filters, top_k=top_k, threshold=0.75)
            # Only scope/IDs/scores retained in this fixture journal, never credentials.
            with (root / "mem0-searches.jsonl").open("a") as output:
                output.write(json.dumps({"filters": filters, "ids": [r["id"] for r in result["results"]]}) + "\n")
            return result
    return Mem0ContextProvider(Client(), mode="oss-roleplay")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", type=Path, required=True)
    args = parser.parse_args()
    with fixture(args.serve, provider_factory=provider_factory) as (_, _, details):
        details.update(exact="Memory: " + FACT + "\n", fact=FACT, provider_kind="real-mem0-oss")
        print(json.dumps(details), flush=True)
        sys.stdin.read()

if __name__ == "__main__":
    main()
