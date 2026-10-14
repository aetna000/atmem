"""Evidence-bound dual-CLI labeling for authentic conversation candidates.

This runner invokes locally authenticated Codex CLI and Claude CLI. It does not
use provider SDKs or API keys.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from typing import Any, Iterator


LABEL_FORMAT = "atmem-memory-understanding-label-v3"
RUBRIC_VERSION = "memory-understanding-rubric-v3"
DISPOSITIONS = ("STORE", "UPDATE", "DUPLICATE", "DO_NOT_STORE", "FORGET", "REVIEW")
MEMORY_CLASSES = (
    "preference", "durable_fact", "procedure", "commitment", "relationship",
    "episode", "temporary_state", "sensitive", "non_memory",
)
RELATIONS = (
    "new", "refines", "contradicts", "supersedes", "repeats", "removes",
    "uncertain", "not_applicable",
)
MEANING_SCHEMA = {
    "type": ["object", "null"],
    "properties": {
        "subject": {"type": "string"},
        "predicate": {"type": "string"},
        "value": {"type": ["string", "null"]},
        "scope": {
            "type": "string",
            "enum": ["user", "workspace", "session", "relationship", "unknown"],
        },
        "valid_from": {"type": ["string", "null"]},
        "valid_until": {"type": ["string", "null"]},
        "durability": {
            "type": "string",
            "enum": ["durable", "episodic", "temporary", "unknown"],
        },
        "relation_to_prior": {"type": "string", "enum": list(RELATIONS)},
    },
    "required": [
        "subject", "predicate", "value", "scope", "valid_from",
        "valid_until", "durability", "relation_to_prior",
    ],
    "additionalProperties": False,
}
LABEL_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "disposition": {"type": "string", "enum": list(DISPOSITIONS)},
        "memory_class": {"type": "string", "enum": list(MEMORY_CLASSES)},
        "evidence_turn_ids": {"type": "array", "items": {"type": "string"}},
        "supersedes_turn_ids": {"type": "array", "items": {"type": "string"}},
        "duplicate_of_turn_ids": {"type": "array", "items": {"type": "string"}},
        "normalized_memory": {"type": ["string", "null"]},
        "meaning": MEANING_SCHEMA,
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "rationale": {"type": "string", "minLength": 1, "maxLength": 500},
    },
    "required": [
        "disposition", "memory_class", "evidence_turn_ids", "supersedes_turn_ids",
        "duplicate_of_turn_ids", "normalized_memory", "meaning", "confidence", "rationale",
    ],
}
BATCH_ITEM_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "candidate_id": {"type": "string"},
        "label": LABEL_SCHEMA,
    },
    "required": ["candidate_id", "label"],
}
BATCH_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"labels": {"type": "array", "items": BATCH_ITEM_SCHEMA}},
    "required": ["labels"],
}

SYSTEM = """You label evidence-bound memory understanding from authentic conversations. Work directly in each conversation's original language; do not translate it. Decide the user's meaning and intention and how the agent's current understanding should evolve. Never copy text into memory merely because it appears in the conversation.

Labels:
- STORE: an explicit, user-authoritative fact, preference, procedure, commitment, relationship, or episode plausibly useful beyond the immediate exchange.
- UPDATE: the candidate explicitly corrects or replaces an earlier supplied user statement. Cite the earlier turn in supersedes_turn_ids.
- DUPLICATE: the candidate has the same durable meaning as an earlier user statement in the same supplied memory scope. Cite it in duplicate_of_turn_ids.
- DO_NOT_STORE: transient request content, chit-chat, acknowledgements, hypothetical/quoted content, assistant-origin claims not confirmed by the user, or information with no justified future memory value.
- FORGET: an explicit request to delete, forget, not retain, or stop using memory.
- REVIEW: ambiguous authority/meaning, sensitive information needing policy review, unresolved conflict, or insufficient evidence.

Class boundary:
- preference: a standing desired assistant behavior, style, format, correction, or user choice.
- procedure: a repeatable action rule or workflow, usually involving a trigger, constraint, or multiple steps; a simple desired assistant behavior is a preference.
- relationship: a durable named or clearly identified interpersonal relationship, not an incidental unnamed participant in a one-off request.

Rules:
1. Return one result for every supplied candidate_id, in input order, with no additions or omissions.
2. Use only exact supplied turn IDs. The candidate turn must be in evidence_turn_ids.
3. Assistant text is context, never proof of a user fact unless the user confirms it.
4. UPDATE requires a conflicting earlier user turn and at least one supersedes_turn_id.
5. DUPLICATE requires an equivalent earlier user turn and at least one duplicate_of_turn_id; similarity to another user's corpus row is not a memory duplicate.
6. FORGET requires an explicit non-retention/deletion intention.
7. Do not infer demographics, identity, preferences, facts, or permanence.
8. normalized_memory is concise and in the source language for STORE/UPDATE/FORGET; otherwise null.
9. Incidental facts embedded in a one-off drafting or information request are not STORE unless the user presents them as durable personal context useful beyond that task.
10. The rationale is a short evidence explanation in the candidate's source language, not hidden reasoning.
11. meaning represents the supported understanding: subject/entity, predicate or intent, value, scope, time validity, durability, and relation to prior understanding. Do not invent missing values or time bounds.
12. STORE uses relation_to_prior=new. UPDATE uses refines, contradicts, or supersedes. DUPLICATE uses repeats. FORGET uses removes. DO_NOT_STORE has meaning=null. REVIEW may use meaning=null or an uncertain proposal.
13. Return only the required schema."""


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def _validate(candidate: dict[str, Any], label: dict[str, Any]) -> None:
    state = candidate["authorized_input"]
    turn_ids = {turn["turn_id"] for turn in state["turns"]}
    user_ids = {turn["turn_id"] for turn in state["turns"] if turn["role"] == "user"}
    evidence = set(label["evidence_turn_ids"])
    supersedes = set(label["supersedes_turn_ids"])
    duplicates = set(label["duplicate_of_turn_ids"])
    if any((
        len(evidence) != len(label["evidence_turn_ids"]),
        len(supersedes) != len(label["supersedes_turn_ids"]),
        len(duplicates) != len(label["duplicate_of_turn_ids"]),
    )):
        raise ValueError("evidence, supersession and duplicate IDs must be unique")
    if label["disposition"] not in DISPOSITIONS or label["memory_class"] not in MEMORY_CLASSES:
        raise ValueError("unknown label")
    if state["candidate_turn_id"] not in evidence or not evidence <= turn_ids:
        raise ValueError("evidence IDs are not bound to the supplied candidate")
    if not supersedes <= user_ids - {state["candidate_turn_id"]}:
        raise ValueError("supersession IDs must be earlier supplied user turns")
    if not duplicates <= user_ids - {state["candidate_turn_id"]}:
        raise ValueError("duplicate IDs must be earlier supplied user turns")
    if label["disposition"] == "UPDATE" and not supersedes:
        raise ValueError("UPDATE requires a concrete supersession target")
    if label["disposition"] != "UPDATE" and supersedes:
        raise ValueError("only UPDATE may supersede earlier turns")
    if label["disposition"] == "DUPLICATE" and not duplicates:
        raise ValueError("DUPLICATE requires a concrete earlier duplicate")
    if label["disposition"] != "DUPLICATE" and duplicates:
        raise ValueError("only DUPLICATE may cite duplicate turns")
    normalized = label["normalized_memory"]
    if label["disposition"] in {"STORE", "UPDATE", "FORGET"} and not normalized:
        raise ValueError("actionable labels require normalized memory text")
    if label["disposition"] in {"DUPLICATE", "DO_NOT_STORE", "REVIEW"} and normalized is not None:
        raise ValueError("non-mutating and review labels must not create normalized memory")
    meaning = label["meaning"]
    disposition = label["disposition"]
    if disposition in {"STORE", "UPDATE", "DUPLICATE", "FORGET"} and meaning is None:
        raise ValueError("understanding-bearing labels require structured meaning")
    if disposition == "DO_NOT_STORE" and meaning is not None:
        raise ValueError("DO_NOT_STORE must not create structured meaning")
    if meaning is not None:
        relation = meaning["relation_to_prior"]
        permitted = {
            "STORE": {"new"},
            "UPDATE": {"refines", "contradicts", "supersedes"},
            "DUPLICATE": {"repeats"},
            "FORGET": {"removes"},
            "REVIEW": {"uncertain", "not_applicable", "new", "refines", "contradicts"},
        }
        if relation not in permitted.get(disposition, set()):
            raise ValueError("meaning relation is incompatible with disposition")
    if not 0 <= float(label["confidence"]) <= 1:
        raise ValueError("confidence is outside [0,1]")


def _agreement(primary: dict[str, Any], verifier: dict[str, Any]) -> tuple[bool, list[str]]:
    fields = (
        "disposition", "memory_class", "evidence_turn_ids",
        "supersedes_turn_ids", "duplicate_of_turn_ids", "meaning",
    )
    disagreements = [field for field in fields if primary[field] != verifier[field]]
    return not disagreements, disagreements


def _cli_environment() -> dict[str, str]:
    environment = dict(os.environ)
    for name in tuple(environment):
        normalized = name.upper()
        if (
            normalized in {"OPENAI_API_KEY", "ANTHROPIC_API_KEY", "HF_TOKEN", "VAST_AI"}
            or normalized.endswith(("_API_KEY", "_API_SECRET", "_ACCESS_TOKEN", "_BEARER_TOKEN"))
        ):
            environment.pop(name, None)
    return environment


def _prompt(batch: list[dict[str, Any]]) -> str:
    inputs = [
        {"candidate_id": row["candidate_id"], "state": row["authorized_input"]}
        for row in batch
    ]
    return SYSTEM + "\n\nINPUT BATCH:\n" + _canonical({"rubric": RUBRIC_VERSION, "candidates": inputs})


def _receipt(cli: str, model: str, version: str, started: float, stdout: str) -> dict[str, Any]:
    return {
        "interface": "authenticated_cli",
        "cli": cli,
        "cli_version": version,
        "model": model,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "latency_seconds": round(time.monotonic() - started, 6),
        "output_sha256": "sha256:" + hashlib.sha256(stdout.encode("utf-8")).hexdigest(),
        "api_key_environment_removed": True,
    }


def _validate_batch_output(batch: list[dict[str, Any]], payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    items = payload.get("labels")
    if not isinstance(items, list):
        raise ValueError("CLI output does not contain labels array")
    expected = [row["candidate_id"] for row in batch]
    observed = [item.get("candidate_id") for item in items]
    if observed != expected:
        raise ValueError("CLI output candidate IDs/order differ from input batch")
    mapped = {}
    for candidate, item in zip(batch, items):
        label = item["label"]
        _validate(candidate, label)
        mapped[candidate["candidate_id"]] = label
    return mapped


def _codex_structured(
    prompt: str, schema_value: dict[str, Any], *, model: str, timeout_seconds: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="atmem-codex-label-") as temporary:
        root = Path(temporary)
        schema = root / "schema.json"
        output = root / "output.json"
        schema.write_text(json.dumps(schema_value), encoding="utf-8")
        command = [
            "codex", "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
            "--sandbox", "read-only", "--skip-git-repo-check", "--model", model,
            "--cd", str(root),
            "--output-schema", str(schema), "--output-last-message", str(output), "-",
        ]
        result = subprocess.run(
            command, input=prompt, text=True, capture_output=True,
            env=_cli_environment(), timeout=timeout_seconds, check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Codex CLI failed ({result.returncode}): {result.stderr[-500:]}")
        raw = output.read_text(encoding="utf-8")
    return json.loads(raw), _receipt("codex", model, "0.162.1", started, raw)


def _codex_labels(batch: list[dict[str, Any]], *, model: str, timeout_seconds: int):
    payload, receipt = _codex_structured(
        _prompt(batch), BATCH_SCHEMA, model=model, timeout_seconds=timeout_seconds,
    )
    return _validate_batch_output(batch, payload), receipt


def _claude_labels(batch: list[dict[str, Any]], *, model: str, timeout_seconds: int):
    payload, receipt = _claude_structured(
        _prompt(batch), BATCH_SCHEMA, model=model,
        timeout_seconds=timeout_seconds,
    )
    return _validate_batch_output(batch, payload), receipt


def _claude_structured(
    prompt: str, schema_value: dict[str, Any], *, model: str,
    timeout_seconds: int, effort: str = "low",
) -> tuple[dict[str, Any], dict[str, Any]]:
    started = time.monotonic()
    command = [
        "claude", "--print", "--safe-mode", "--no-session-persistence", "--tools", "",
        "--model", model, "--effort", effort, "--output-format", "json",
        "--json-schema", json.dumps(schema_value),
    ]
    result = subprocess.run(
        command, input=prompt, text=True, capture_output=True,
        env=_cli_environment(), timeout=timeout_seconds, check=False,
    )
    if result.returncode != 0:
        detail = result.stderr[-500:].strip()
        if not detail and result.stdout.strip():
            try:
                envelope = json.loads(result.stdout)
                detail = str(
                    envelope.get("result")
                    or envelope.get("api_error_status")
                    or envelope.get("terminal_reason")
                    or "unknown CLI error"
                )[-500:]
            except (TypeError, ValueError):
                detail = result.stdout[-500:].strip()
        raise RuntimeError(f"Claude CLI failed ({result.returncode}): {detail}")
    envelope = json.loads(result.stdout)
    payload = envelope.get("structured_output")
    if payload is None:
        payload = json.loads(envelope["result"])
    receipt = _receipt("claude", model, "2.1.281", started, result.stdout)
    for key in ("duration_ms", "duration_api_ms", "num_turns", "total_cost_usd"):
        if key in envelope:
            receipt[key] = envelope[key]
    return payload, receipt


def _language_batches(rows: list[dict[str, Any]], size: int) -> Iterator[list[dict[str, Any]]]:
    """Prevent language leakage by batching only identical source tags."""
    groups: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for row in rows:
        language = row["provenance"]["language"]
        if language not in groups:
            groups[language] = []
            order.append(language)
        groups[language].append(row)
    for language in order:
        group = groups[language]
        for start in range(0, len(group), size):
            yield group[start : start + size]


def label(
    *, candidates_path: Path, output_path: Path, codex_model: str,
    claude_model: str, limit: int | None, batch_size: int, timeout_seconds: int,
) -> dict[str, Any]:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    completed = {
        row["candidate_id"] for row in _iter_jsonl(output_path)
        if row.get("status") in {"accepted", "disagreed"}
    } if output_path.exists() else set()
    candidates = [row for row in _iter_jsonl(candidates_path) if row["candidate_id"] not in completed]
    if limit is not None:
        candidates = candidates[:limit]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    counts = {"accepted": 0, "disagreed": 0, "invalid": 0, "skipped": len(completed)}
    attempted = 0
    with output_path.open("a", encoding="utf-8") as stream:
        for batch in _language_batches(candidates, batch_size):
            attempted += len(batch)
            started = time.monotonic()
            try:
                codex, codex_receipt = _codex_labels(batch, model=codex_model, timeout_seconds=timeout_seconds)
                claude, claude_receipt = _claude_labels(batch, model=claude_model, timeout_seconds=timeout_seconds)
                for candidate in batch:
                    candidate_id = candidate["candidate_id"]
                    primary = codex[candidate_id]
                    verifier = claude[candidate_id]
                    agreed, disagreements = _agreement(primary, verifier)
                    status = "accepted" if agreed else "disagreed"
                    counts[status] += 1
                    stream.write(_canonical({
                        "format": LABEL_FORMAT,
                        "candidate_id": candidate_id,
                        "input_digest": candidate["input_digest"],
                        "rubric_version": RUBRIC_VERSION,
                        "rubric_sha256": _digest(SYSTEM),
                        "status": status,
                        "accepted_label": primary if agreed else None,
                        "codex_label": primary,
                        "claude_label": verifier,
                        "disagreements": disagreements,
                        "codex_receipt": codex_receipt,
                        "claude_receipt": claude_receipt,
                    }) + "\n")
            except Exception as error:
                for candidate in batch:
                    counts["invalid"] += 1
                    stream.write(_canonical({
                        "format": LABEL_FORMAT,
                        "candidate_id": candidate["candidate_id"],
                        "input_digest": candidate["input_digest"],
                        "rubric_version": RUBRIC_VERSION,
                        "rubric_sha256": _digest(SYSTEM),
                        "status": "invalid",
                        "error_type": type(error).__name__,
                        "error": str(error)[:500],
                        "latency_seconds": time.monotonic() - started,
                    }) + "\n")
            stream.flush()
    return {
        "attempted": attempted,
        "counts": counts,
        "codex_model": codex_model,
        "claude_model": claude_model,
        "interfaces": ["codex_cli", "claude_cli"],
        "direct_provider_api": False,
        "output": str(output_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--codex-model", default="gpt-6-sol")
    parser.add_argument("--claude-model", default="opus")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    args = parser.parse_args()
    print(json.dumps(label(
        candidates_path=args.candidates, output_path=args.output,
        codex_model=args.codex_model, claude_model=args.claude_model,
        limit=args.limit, batch_size=args.batch_size,
        timeout_seconds=args.timeout_seconds,
    ), indent=2))


if __name__ == "__main__":
    main()
