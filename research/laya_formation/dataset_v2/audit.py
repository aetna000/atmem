from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
from typing import Any, Sequence

from atmem.core.canonical import canonical_json, sha256_hex

from .generator import DISPOSITIONS


def build_blinded_packet(rows: Sequence[dict[str, Any]], *, per_class: int, seed: int) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_label[row["expected"]["disposition"]].append(row)
    rng = random.Random(seed)
    selected = []
    for label in DISPOSITIONS:
        candidates = sorted(by_label[label], key=lambda row: row["content_digest"])
        if len(candidates) < per_class:
            raise ValueError(f"not enough {label} rows for audit")
        selected.extend(rng.sample(candidates, per_class))
    rng.shuffle(selected)
    packet_rows = []
    key_rows = []
    review_rows = []
    for ordinal, row in enumerate(selected):
        opaque_id = "audit-" + hashlib.sha256(f"{seed}:{ordinal}:{row['content_digest']}".encode()).hexdigest()[:20]
        packet_rows.append({
            "audit_id": opaque_id,
            "state": row["state"],
            "allowed_dispositions": list(DISPOSITIONS),
        })
        key_rows.append({
            "audit_id": opaque_id,
            "expected_disposition": row["expected"]["disposition"],
            "source_example_digest": row["content_digest"],
        })
        review_rows.append({
            "audit_id": opaque_id,
            "selected_disposition": None,
            "confidence": None,
            "critical_issue": None,
            "notes": "",
        })
    packet = {
        "format": "atmem-laya-blinded-data-audit-packet-v2",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "rows": packet_rows,
    }
    packet["digest"] = "sha256:" + sha256_hex(canonical_json(packet))
    answer_key = {
        "format": "atmem-laya-private-data-audit-key-v2",
        "packet_digest": packet["digest"],
        "rows": key_rows,
    }
    answer_key["digest"] = "sha256:" + sha256_hex(canonical_json(answer_key))
    review = {
        "format": "atmem-laya-data-audit-review-v2",
        "packet_digest": packet["digest"],
        "reviewer_id": None,
        "independent_of_generation": None,
        "rows": review_rows,
    }
    return packet, answer_key, review


def score_review(packet: dict[str, Any], answer_key: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    if review.get("packet_digest") != packet.get("digest") or answer_key.get("packet_digest") != packet.get("digest"):
        raise ValueError("audit packet binding mismatch")
    expected = {row["audit_id"]: row["expected_disposition"] for row in answer_key["rows"]}
    reviewed = {row["audit_id"]: row for row in review["rows"]}
    if set(reviewed) != set(expected):
        raise ValueError("audit review membership mismatch")
    confusion: dict[str, Counter[str]] = defaultdict(Counter)
    critical = []
    for identity, gold in expected.items():
        value = reviewed[identity]
        selected = value.get("selected_disposition")
        if selected not in DISPOSITIONS:
            raise ValueError(f"missing or invalid disposition for {identity}")
        confusion[gold][selected] += 1
        if value.get("critical_issue"):
            critical.append(identity)
    correct = sum(confusion[label][label] for label in DISPOSITIONS)
    return {
        "format": "atmem-laya-data-audit-result-v2",
        "packet_digest": packet["digest"],
        "reviewer_id": review.get("reviewer_id"),
        "independent_of_generation": review.get("independent_of_generation"),
        "reviewed": len(expected),
        "correct": correct,
        "accuracy": correct / len(expected),
        "critical_issues": critical,
        "confusion": {label: dict(sorted(confusion[label].items())) for label in DISPOSITIONS},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--per-class", type=int, default=100)
    parser.add_argument("--seed", type=int, default=417_029)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
    packet, key, review = build_blinded_packet(rows, per_class=args.per_class, seed=args.seed)
    public = args.output / "public"
    private = args.output / "private"
    public.mkdir(parents=True, exist_ok=True)
    private.mkdir(parents=True, exist_ok=True)
    (public / "packet.json").write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n")
    (public / "review-template.json").write_text(json.dumps(review, indent=2, sort_keys=True) + "\n")
    (private / "answer-key.json").write_text(json.dumps(key, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "packet_digest": packet["digest"], "answer_key_digest": key["digest"],
        "rows": len(packet["rows"]), "public": str(public), "private": str(private),
    }, indent=2))


if __name__ == "__main__":
    main()
