"""Offline implementation probes, not a quality or latency benchmark.

Run from the repository root:
  .venv/bin/python RandD/mem0_retrieval_probes.py /path/to/mem0

Imports only Mem0's dependency-free scoring module, not its SDK or providers.
Uses synthetic inputs and does not open a database or call any model.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from atmem.retrieve.rank import decide_retrieval


MEM0_REVISION = "0df3e4b87df20785f0741370c75e44428796193e"


def main() -> None:
    root = Path(sys.argv[1]).resolve()
    revision = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    if revision != MEM0_REVISION:
        raise SystemExit(f"Expected {MEM0_REVISION}, got {revision}")
    spec = importlib.util.spec_from_file_location(
        "researched_mem0_scoring", root / "mem0/utils/scoring.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    score = module.score_and_rank
    semantic = [{"id": "semantic", "score": 0.8, "payload": {}}]
    keyword_only = score(semantic, {"keyword-only": 1.0}, {}, 0.1, 10)
    assert [row["id"] for row in keyword_only] == ["semantic"]
    low_semantic = score(
        [{"id": "exact-keyword", "score": 0.09}],
        {"exact-keyword": 1.0}, {"exact-keyword": 0.5}, 0.1, 10,
    )
    assert low_semantic == []
    unboosted = score(semantic, {}, {}, 0.1, 10)[0]["score"]
    unrelated_boost = keyword_only[0]["score"]
    assert unboosted == 0.8 and unrelated_boost == 0.4
    final_below_threshold = score(
        [{"id": "weak", "score": 0.15}], {"other": 0.9}, {}, 0.1, 10
    )[0]["score"]
    assert final_below_threshold == 0.075

    topical = decide_retrieval("How old is my daughter?", [
        {"record_id": "drawing", "content": "My daughter likes drawing.", "score": 0.8}
    ])
    assert topical.support_class.value == "direct_support"
    unicode_query = decide_retrieval("سن من چیست", [
        {"record_id": "age-fa", "content": "سن من ۴۰ سال است", "score": 0.8}
    ])
    assert unicode_query.ranked_record_ids == ()
    semantic_cases = {}
    for similarity in (0.71, 0.73):
        decision = decide_retrieval("Where do I reside?", [{
            "record_id": "home", "content": "Home: Paris.", "score": similarity,
            "signals": {
                "semantic_similarity": similarity,
                "semantic_provider": "openai",
                "semantic_quality_class": "production",
            },
        }])
        semantic_cases[str(similarity)] = decision.to_dict()
    assert semantic_cases["0.71"]["ranked_record_ids"] == []
    assert semantic_cases["0.73"]["ranked_record_ids"] == ["home"]

    print(json.dumps({
        "kind": "offline-implementation-probes-not-a-benchmark",
        "mem0_revision": revision,
        "assertions_passed": 9,
        "mem0": {
            "keyword_only_candidate_omitted": keyword_only,
            "semantic_gate_before_boost": low_semantic,
            "score_without_other_signal": unboosted,
            "score_with_off_pool_keyword_signal": unrelated_boost,
            "returned_score_below_input_threshold": final_below_threshold,
        },
        "atmem": {
            "topical_nonanswer": topical.to_dict(),
            "persian_lexical_only": unicode_query.to_dict(),
            "fixed_semantic_gate": semantic_cases,
        },
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
