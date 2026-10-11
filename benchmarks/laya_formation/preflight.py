"""Freeze and verify the matched synthetic evaluation before model calls."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random
from typing import Any, Mapping

from .contracts import ChoiceCase, digest


SEED = 410239
PER_QUESTION = 80
QUESTION_INSTRUCTIONS = {
    "operation": "Choose the only permitted memory formation operation.",
    "memory_class": "Classify the proposed memory using the finite policy classes.",
    "evidence_support": "Classify whether authorized evidence supports the proposal.",
    "target_selection": "Choose the authorized canonical target or review outcome.",
    "retrieval_usefulness": "Classify future retrieval usefulness from the authorized evidence.",
}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at {path}:{number}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"JSONL row is not an object at {path}:{number}")
            rows.append(value)
    return rows


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def freeze_cases(inputs_path: Path, labels_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    inputs, labels = _read_jsonl(inputs_path), _read_jsonl(labels_path)
    labels_by_id = {row["example_id"]: row for row in labels}
    if len(labels_by_id) != len(labels) or set(labels_by_id) != {row.get("example_id") for row in inputs}:
        raise ValueError("sealed input and label identities differ")
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    scenarios: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in inputs:
        if row.get("question_id") not in QUESTION_INSTRUCTIONS:
            raise ValueError("sealed row uses an unknown question")
        buckets[row["question_id"]].append(row)
        scenarios[row["scenario_id"]].append(row)
    if set(buckets) != set(QUESTION_INSTRUCTIONS):
        raise ValueError("sealed question coverage is incomplete")
    rng = random.Random(SEED)
    complete = []
    for scenario_id, rows in sorted(scenarios.items()):
        questions = [row["question_id"] for row in rows]
        if len(rows) == len(QUESTION_INSTRUCTIONS) and set(questions) == set(QUESTION_INSTRUCTIONS):
            complete.append(scenario_id)
    rng.shuffle(complete)
    if len(complete) < PER_QUESTION:
        raise ValueError("sealed evaluation is underpowered for complete scenario clusters")
    selected_ids = set(complete[:PER_QUESTION])
    selected = [row for row in inputs if row["scenario_id"] in selected_ids]
    selected.sort(key=lambda row: row["example_id"])
    cases, label_rows = [], []
    for row in selected:
        label = labels_by_id[row["example_id"]]
        choice = ChoiceCase(
            case_id=row["example_id"], scenario_id=row["scenario_id"],
            cluster_id=row["scenario_id"], question_id=row["question_id"],
            instructions=QUESTION_INSTRUCTIONS[row["question_id"]],
            authorized_input=row["authorized_input"], options=tuple(row["choice_ids"]),
            candidate_pool=tuple(
                option for option in row["choice_ids"] if str(option).startswith("target:")
            ),
            expected=tuple(label["expected_choice_ids"]),
        )
        cases.append({
            "case_id": choice.case_id, "scenario_id": choice.scenario_id,
            "cluster_id": choice.cluster_id, "question_id": choice.question_id,
            "instructions": choice.instructions, "authorized_input": choice.authorized_input,
            "options": list(choice.options), "candidate_pool": list(choice.candidate_pool),
            "matching": choice.matching_receipt().to_dict(),
        })
        label_rows.append({"case_id": choice.case_id, "expected": list(choice.expected)})
    packet = {
        "format": "atmem-laya-matched-evaluation-packet-v1",
        "seed": SEED, "case_count": len(cases),
        "scenario_count": len(selected_ids),
        "question_counts": dict(sorted(Counter(row["question_id"] for row in cases).items())),
        "cases": cases,
    }
    answer_key = {
        "format": "atmem-laya-matched-evaluation-answer-key-v1",
        "seed": SEED, "case_count": len(label_rows), "labels": label_rows,
    }
    packet["digest"] = digest(packet)
    answer_key["digest"] = digest(answer_key)
    return packet, answer_key


def public_manifest(packet: Mapping[str, Any], answer_key: Mapping[str, Any]) -> dict[str, Any]:
    cases = packet["cases"]
    return {
        "format": "atmem-laya-matched-evaluation-manifest-v1",
        "seed": packet["seed"], "case_count": packet["case_count"],
        "scenario_count": packet["scenario_count"],
        "question_counts": packet["question_counts"],
        "case_ids": [row["case_id"] for row in cases],
        "packet_digest": packet["digest"], "answer_key_digest": answer_key["digest"],
        "authorized_input_set_digest": digest([
            row["matching"]["authorized_input_digest"] for row in cases
        ]),
        "option_set_digest": digest([row["matching"]["option_digest"] for row in cases]),
        "candidate_pool_set_digest": digest([
            row["matching"]["candidate_pool_digest"] for row in cases
        ]),
        "question_schema_set_digest": digest([
            row["matching"]["question_schema_digest"] for row in cases
        ]),
    }


def write_frozen(packet_path: Path, answer_key_path: Path, packet: Mapping[str, Any], answer_key: Mapping[str, Any]) -> None:
    for path, value in ((packet_path, packet), (answer_key_path, answer_key)):
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise FileExistsError(f"refusing to overwrite frozen evaluation artifact: {path}")
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify_base_laya(root: Path, source_lock: Mapping[str, Any]) -> dict[str, Any]:
    expected = source_lock["laya"]["files"]
    checked = {}
    for relative, metadata in expected.items():
        path = root / relative
        if not path.is_file() or path.stat().st_size != int(metadata["size"]):
            raise ValueError(f"base Laya artifact mismatch: {relative}")
        actual = sha256_file(path)
        if actual != metadata["sha256"]:
            raise ValueError(f"base Laya digest mismatch: {relative}")
        checked[relative] = actual
    return {
        "repo": source_lock["laya"]["hub_repo"],
        "revision": source_lock["laya"]["hub_revision"],
        "files_verified": len(checked), "model_sha256": checked["model.safetensors"],
    }
