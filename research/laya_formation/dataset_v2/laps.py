from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterator, Sequence

from atmem.core.canonical import canonical_json, sha256_hex
from atmem.laya_formation.packing import AuthorizedCandidate, AuthorizedRange, build_authorized_state_v2


LAPS_REVISION = "ac9c1f5b2d2878d85ed9638ed7418f1523922005"
LAPS_LICENSE = "MIT"
_WORD = re.compile(r"[a-z0-9]+")
_SECRET = re.compile(r"(?i)(?:api[_ -]?key|password|secret|token)\s*[:=]\s*\S+")
_EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
_PHONE = re.compile(r"(?<!\d)(?:\+?\d[\d ()-]{7,}\d)(?!\d)")


def _tokens(text: str) -> set[str]:
    return {word for word in _WORD.findall(text.casefold()) if len(word) > 2}


def _best_user_message(session: dict[str, Any], preference: str) -> tuple[str, float] | None:
    wanted = _tokens(preference)
    if not wanted:
        return None
    candidates = []
    for turn in session.get("dialogue") or []:
        if str(turn.get("role")).casefold() != "user":
            continue
        text = str(turn.get("message") or "").strip()
        if not text or _SECRET.search(text) or _EMAIL.search(text) or _PHONE.search(text):
            continue
        overlap = len(wanted & _tokens(text)) / len(wanted)
        candidates.append((overlap, text))
    if not candidates:
        return None
    score, text = max(candidates, key=lambda item: (item[0], -len(item[1])))
    return (text, score) if score >= 0.5 else None


def load_preference_anchors(root: Path, *, source_split: str) -> list[dict[str, Any]]:
    if source_split not in {"train", "val", "test"}:
        raise ValueError("LAPS split must be train, val, or test")
    anchors = []
    for domain in ("recipe", "movie"):
        path = root / "dataset" / f"{domain}_dataset_{source_split}.json"
        for conversation in json.loads(path.read_text(encoding="utf-8")):
            worker_hash = hashlib.sha256(str(conversation["worker_id"]).encode()).hexdigest()[:16]
            for session_index, session in enumerate(conversation.get("sessions") or []):
                for category, values in sorted((session.get("preferences") or {}).items()):
                    for value in values:
                        match = _best_user_message(session, str(value))
                        if match is None:
                            continue
                        evidence, alignment = match
                        anchors.append({
                            "anchor_id": f"laps-{domain}-{source_split}-{worker_hash}-{session_index}-{len(anchors)}",
                            "domain": domain,
                            "worker_hash": worker_hash,
                            "session_index": session_index,
                            "relation": f"{domain}:{category}",
                            "value": str(value),
                            "evidence": evidence,
                            "alignment_recall": alignment,
                            "source_split": source_split,
                        })
    return anchors


def disjoint_partitions(root: Path) -> dict[str, list[dict[str, Any]]]:
    """Respect upstream splits while removing worker overlap across all partitions."""

    def deduplicate(rows: list[dict[str, Any]], excluded: set[str]) -> list[dict[str, Any]]:
        chosen: dict[str, dict[str, Any]] = {}
        for row in rows:
            if len(row["evidence"]) > 240:
                continue
            key = " ".join(row["evidence"].casefold().split())
            if key in excluded:
                continue
            current = chosen.get(key)
            if current is None or row["alignment_recall"] > current["alignment_recall"]:
                chosen[key] = row
        return [chosen[key] for key in sorted(chosen)]

    train = deduplicate(load_preference_anchors(root, source_split="train"), set())
    train_workers = {row["worker_hash"] for row in train}
    train_texts = {" ".join(row["evidence"].casefold().split()) for row in train}
    validation = deduplicate([
        row for row in load_preference_anchors(root, source_split="val")
        if row["worker_hash"] not in train_workers
    ], train_texts)
    validation_workers = {row["worker_hash"] for row in validation}
    validation_texts = {" ".join(row["evidence"].casefold().split()) for row in validation}
    test = deduplicate([
        row for row in load_preference_anchors(root, source_split="test")
        if row["worker_hash"] not in train_workers | validation_workers
    ], train_texts | validation_texts)
    return {"train": train, "transfer_validation": validation, "transfer_test": test}


def _candidate(identity: str, anchor: dict[str, Any]) -> AuthorizedCandidate:
    content = {
        "subject": "authenticated-user",
        "relation": "source_utterance",
        "text": anchor["evidence"],
        "memory_class": "PREFERENCE",
    }
    return AuthorizedCandidate(
        candidate_id=identity, lifecycle="active", kind="preference", content=content,
        digest="sha256:" + sha256_hex(canonical_json(content)),
    )


def build_counterfactual_examples(
    anchors: Sequence[dict[str, Any]], *, output_split: str,
) -> Iterator[dict[str, Any]]:
    """Create core disposition triples grounded in natural LAPS utterances."""

    for index, anchor in enumerate(anchors):
        evidence = AuthorizedRange(
            range_id=f"range-{anchor['anchor_id']}", source_id=f"source-{anchor['anchor_id']}",
            start=0, end=len(anchor["evidence"].encode()), text=anchor["evidence"],
            source_type="user_message", binding_assurance="host_authenticated",
        )
        for disposition in ("STORE", "DUPLICATE"):
            candidates = [] if disposition == "STORE" else [
                _candidate(f"candidate-{anchor['anchor_id']}", anchor)
            ]
            state = build_authorized_state_v2(
                scope={
                    "subject_id": f"laps-worker-{anchor['worker_hash']}",
                    "agent_id": "laps-import",
                    "workspace_id": f"laps-{anchor['domain']}",
                },
                ranges=[evidence], candidates=candidates,
            )
            example_id = f"{anchor['anchor_id']}-{disposition.casefold()}"
            payload = {
                "format": "atmem-laya-training-example-v2",
                "example_id": example_id,
                "semantic_family_id": anchor["anchor_id"],
                "generator_version": "laps-import-v1",
                "split": output_split,
                "state": state,
                "expected": {"disposition": disposition, "memory_class": "PREFERENCE"},
                "oracle": {
                    "rule_id": "laps_extracted_preference_counterfactual",
                    "target_candidate_id": None,
                    "alignment_recall": anchor["alignment_recall"],
                },
                "training_only": output_split == "train",
                "provenance": {
                    "dataset": "informagi/laps",
                    "revision": LAPS_REVISION,
                    "license": LAPS_LICENSE,
                    "upstream_split": anchor["source_split"],
                    "worker_id_retained": False,
                    "label_quality": "silver_extracted_preference",
                },
            }
            payload["content_digest"] = "sha256:" + sha256_hex(canonical_json(payload))
            yield payload
