"""Synthetic, deterministic cases for the Jev-Lab experiment."""

from __future__ import annotations

import hashlib
import json
import random
from typing import Any

DATASET_VERSION = "jev-lab-synthetic-v1"


def build_dataset(seed: int = 34, cases: int = 8) -> dict[str, Any]:
    rng = random.Random(seed)
    templates = [
        ("travel", "What should I remember about my flight preferences?", "I prefer morning flights and an aisle seat.", "travel preferences"),
        ("diet", "What food constraint should the assistant respect?", "The user is allergic to peanuts.", "allergy constraint"),
        ("work", "What is the deadline for the launch?", "The product launch is scheduled for 15 October.", "launch deadline"),
        ("family", "Who should receive the school update?", "Send school updates to Alex's parent account.", "school contact"),
        ("finance", "What spending limit did the user set?", "The weekly discretionary limit is 150 dollars.", "spending limit"),
        ("health", "Which exercise preference is current?", "The user prefers low-impact cycling while recovering.", "exercise preference"),
        ("security", "Which security requirement applies?", "Never disclose the recovery code in an assistant response.", "security rule"),
        ("learning", "What learning format works best?", "The user learns best from short worked examples.", "learning format"),
    ]
    rows: list[dict[str, Any]] = []
    for index in range(cases):
        topic, query, answer, label = templates[index % len(templates)]
        case_id = f"case-{index + 1:02d}"
        candidates = [
            {"id": f"{case_id}-relevant", "text": answer, "eligible": True, "status": "active", "label": label},
            {"id": f"{case_id}-stale", "text": f"Older {topic} note that may no longer apply to the current request.", "eligible": True, "status": "expired", "label": "stale"},
            {"id": f"{case_id}-restricted", "text": f"Private {topic} detail that is outside this session scope.", "eligible": False, "status": "active", "label": "out-of-scope"},
            {"id": f"{case_id}-distractor", "text": f"A general note about {topic} with unrelated background information.", "eligible": True, "status": "active", "label": "distractor"},
        ]
        rng.shuffle(candidates)
        rows.append({"id": case_id, "topic": topic, "query": query, "expected_id": f"{case_id}-relevant", "candidates": candidates})
    return {"format": DATASET_VERSION, "seed": seed, "cases": rows}


def dataset_digest(dataset: dict[str, Any]) -> str:
    payload = json.dumps(dataset, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()
