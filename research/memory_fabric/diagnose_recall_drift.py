"""Reproduce cross-subject FTS ranking drift with synthetic records only."""
import argparse
import json
from pathlib import Path
import tempfile

from atmem import Memory
from research.memory_fabric.local_baseline import SUBJECT, _seed
from research.memory_fabric.homa_experiment import WRITE_SUBJECT


def reproduce():
    with tempfile.TemporaryDirectory(prefix="fabric-recall-drift-") as temporary:
        path = Path(temporary) / "memory.db"
        _seed(path, 40)
        memory = Memory(path)
        query = "What is synthetic catalog item 0000?"
        try:
            def snapshot():
                from atmem.retrieve.rank import query_tokens
                block = memory.build_recall_block(SUBJECT, query, max_records=3,
                                                  require_direct_support=True)["block"]
                scores = memory.store.fts_match_scores(SUBJECT, query_tokens(query), limit=200)
                return {"block": block, "read_generation": memory.store.record_generation(SUBJECT),
                        "fts_min": min(scores.values()), "fts_max": max(scores.values())}
            before = snapshot()
            for i in range(70):
                text = f"Synthetic write {i}: " + "x" * (64, 256, 1024)[i % 3]
                memory.remember(WRITE_SUBJECT, text, interpreted_fact=text,
                                interpreted_fact_key=f"fixture_{i}")
            after = snapshot()
            return {"format": "synthetic-cross-subject-ranking-diagnostic-v1",
                    "before": before, "after": after,
                    "read_generation_unchanged": before["read_generation"] == after["read_generation"],
                    "context_bytes_changed": before["block"] != after["block"],
                    "note": "Different FTS corpus snapshot despite unchanged read-subject records; does not establish unauthorized disclosure."}
        finally:
            memory.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = reproduce()
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(json.dumps(report, indent=2))
