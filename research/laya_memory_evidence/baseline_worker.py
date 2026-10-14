"""Chronological, restart-safe adjudication of authentic baseline observations."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

from atmem import Memory
from atmem.contracts import AuthorityScope, SourceCaptureRequest
from atmem.core.canonical import canonical_json, sha256_hex
from atmem.extract.context import build_resolution_context
from atmem.extract.formation import form_typed_proposals
from atmem.laya_formation.formation_v2 import (
    FormationRulingV2, apply_ruling_to_proposals,
)

from .label_dataset import _codex_structured


FORMAT = "atmem-baseline-adjudication-v2"
OPERATIONS = (
    "STORE_NEW", "UPDATE_EXISTING", "SUPERSEDE_EXISTING", "DUPLICATE",
    "DO_NOT_STORE", "FORGET_EXISTING", "REVIEW",
)
ITEM_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "observation_id": {"type": "string"},
        "operation": {"type": "string", "enum": list(OPERATIONS)},
        "memory_class": {
            "type": "string", "enum": [
                "preference", "durable_fact", "procedure", "commitment",
                "relationship", "episode", "temporary_state", "sensitive",
                "non_memory",
            ],
        },
        "target_memory_id": {"type": ["string", "null"]},
        "context_sufficient": {"type": "boolean"},
        "durable": {"type": "boolean"},
        "future_utility_level": {"type": "integer", "minimum": 0, "maximum": 4},
        "evidence_memory_ids": {"type": "array", "items": {"type": "string"}},
        "reason_codes": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "observation_id", "operation", "memory_class", "target_memory_id",
        "context_sufficient", "durable", "future_utility_level",
        "evidence_memory_ids", "reason_codes",
    ],
}
BATCH_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"decisions": {"type": "array", "items": ITEM_SCHEMA}},
    "required": ["decisions"],
}
SYSTEM = """You are an independent memory-state-transition adjudicator. Every
observation is an authentic conversation row and every current memory is the
actual authorized state for that row's isolated scope. Decide the supported
transition; do not rewrite, summarize, translate, or generate memory text.

STORE_NEW: durable meaning is new. UPDATE_EXISTING: compatible detail changes
one target. SUPERSEDE_EXISTING: explicit correction/replacement of one target.
DUPLICATE: same durable meaning already exists. DO_NOT_STORE: transient,
incidental, quoted, hypothetical, unsupported, or not useful later.
FORGET_EXISTING: explicit deletion/non-retention request targeting one memory.
REVIEW: ambiguity or insufficient authorized context.

Relational operations require exactly one supplied target_memory_id. Other
operations require null. Evidence IDs must come from supplied current memories.
Judge the original language directly. Return every observation once, in input
order, and only the requested JSON schema."""


def decisions_agree(first: dict[str, Any], verification: dict[str, Any]) -> bool:
    """Require agreement on every field that becomes supervised truth."""

    return all(
        first[key] == verification[key]
        for key in (
            "operation", "memory_class", "target_memory_id",
            "context_sufficient", "durable", "future_utility_level",
        )
    ) and sorted(first["evidence_memory_ids"]) == sorted(
        verification["evidence_memory_ids"]
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(
        canonical_json(value).encode("utf-8")
    ).hexdigest()


def _migrate(connection: sqlite3.Connection) -> None:
    connection.executescript("""
    CREATE TABLE IF NOT EXISTS baseline_judgment(
      observation_id TEXT NOT NULL REFERENCES baseline_observation(observation_id),
      judge TEXT NOT NULL,
      pass_kind TEXT NOT NULL CHECK(pass_kind IN ('first','verification','adjudication')),
      decision_json TEXT NOT NULL CHECK(json_valid(decision_json)),
      input_digest TEXT NOT NULL,
      receipt_json TEXT NOT NULL CHECK(json_valid(receipt_json)),
      decision_digest TEXT NOT NULL,
      created_at TEXT NOT NULL,
      PRIMARY KEY(observation_id,judge,pass_kind)
    ) STRICT;
    CREATE TABLE IF NOT EXISTS baseline_worker_run(
      run_id TEXT PRIMARY KEY,
      judge TEXT NOT NULL,
      pass_kind TEXT NOT NULL,
      model TEXT NOT NULL,
      requested_rows INTEGER NOT NULL,
      completed_rows INTEGER NOT NULL,
      receipt_digest TEXT NOT NULL,
      created_at TEXT NOT NULL
    ) STRICT;
    """)
    connection.commit()


def _scope(scope_id: str) -> AuthorityScope:
    return AuthorityScope(scope_id, "baseline-agent", "baseline-workspace")


def _state(memory: Memory, scope_id: str) -> list[dict[str, Any]]:
    rows = memory.store.list_records(scope_id, statuses=("active",))
    result = []
    for row in rows:
        raw = row.get("raw") or {}
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (TypeError, ValueError):
                raw = {}
        result.append({
            "id": str(row["id"]), "content": str(row.get("content") or ""),
            "status": str(row.get("status") or "active"),
            "generation": int(row.get("generation") or 0),
            "memory_class": str(raw.get("memory_class") or "unknown"),
        })
    return result


def _state_digest(memory: Memory, scope_id: str) -> str:
    return _sha(_state(memory, scope_id))


def _ready_rows(
    connection: sqlite3.Connection, limit: int, *, judge: str, pass_kind: str,
) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT b.* FROM baseline_observation b
        WHERE b.status='awaiting_adjudication'
          AND NOT EXISTS (
            SELECT 1 FROM baseline_observation earlier
            WHERE earlier.group_id=b.group_id AND earlier.ordinal < b.ordinal
              AND earlier.status='awaiting_adjudication'
          )
          AND NOT EXISTS (
            SELECT 1 FROM baseline_judgment j
            WHERE j.observation_id=b.observation_id
              AND j.judge=? AND j.pass_kind=?
          )
          AND (
            ? != 'verification' OR EXISTS (
              SELECT 1 FROM baseline_judgment first_pass
              WHERE first_pass.observation_id=b.observation_id
                AND first_pass.judge=? AND first_pass.pass_kind='first'
            )
          )
        ORDER BY b.ordinal,b.group_id,b.observation_id LIMIT ?
        """, (judge, pass_kind, pass_kind, judge, limit),
    ).fetchall()


def _inputs(memory: Memory, rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [
        {
            "observation_id": row["observation_id"],
            "observation": {"role": row["role"], "content": row["content"]},
            "current_memories": _state(memory, row["scope_id"]),
            "allowed_operations": list(OPERATIONS),
        }
        for row in rows
    ]


def _validate_decisions(
    rows: list[sqlite3.Row], inputs: list[dict[str, Any]], payload: dict[str, Any],
) -> list[dict[str, Any]]:
    decisions = payload.get("decisions")
    if not isinstance(decisions, list) or len(decisions) != len(rows):
        raise ValueError("judge returned the wrong decision count")
    expected_ids = [row["observation_id"] for row in rows]
    observed_ids = [item.get("observation_id") for item in decisions]
    if len(set(observed_ids)) != len(observed_ids) or set(observed_ids) != set(expected_ids):
        raise ValueError("judge returned missing, duplicate, or unknown observations")
    by_id = {item["observation_id"]: item for item in decisions}
    decisions = [by_id[identity] for identity in expected_ids]
    relational = {
        "UPDATE_EXISTING", "SUPERSEDE_EXISTING", "DUPLICATE", "FORGET_EXISTING",
    }
    for item, judge_input in zip(decisions, inputs):
        known = {row["id"] for row in judge_input["current_memories"]}
        target = item["target_memory_id"]
        evidence = item["evidence_memory_ids"]
        if len(evidence) != len(set(evidence)) or not set(evidence) <= known:
            raise ValueError("judge cited unknown or duplicate evidence")
        if item["operation"] in relational:
            if target not in known:
                raise ValueError("relational decision requires an authorized target")
        elif target is not None:
            raise ValueError("non-relational decision must not select a target")
    return [dict(item) for item in decisions]


def _judge_codex(
    inputs: list[dict[str, Any]], *, model: str, timeout_seconds: int,
    system: str = SYSTEM,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    prompt = system + "\n\nINPUT:\n" + canonical_json({"items": inputs})
    payload, receipt = _codex_structured(
        prompt, BATCH_SCHEMA, model=model, timeout_seconds=timeout_seconds,
    )
    return payload, receipt


def _judge_validated(
    rows: list[sqlite3.Row], inputs: list[dict[str, Any]], *,
    model: str, timeout_seconds: int, system: str = SYSTEM,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Retry malformed packets by splitting; never accept partial coverage."""

    try:
        payload, receipt = _judge_codex(
            inputs, model=model, timeout_seconds=timeout_seconds, system=system,
        )
        return _validate_decisions(rows, inputs, payload), receipt
    except (RuntimeError, ValueError) as exc:
        if len(rows) <= 1:
            # A malformed singleton must not terminate a multi-hour run and it
            # must never become training truth.  Preserve the failure as a
            # fail-closed REVIEW; adjudication marks REVIEW rows rejected.
            return [{
                "observation_id": rows[0]["observation_id"],
                "operation": "REVIEW", "memory_class": "non_memory",
                "target_memory_id": None, "context_sufficient": False,
                "durable": False, "future_utility_level": 0,
                "evidence_memory_ids": [],
                "reason_codes": ["judge_output_validation_failed"],
            }], {
                "interface": "authenticated_cli", "cli": "codex",
                "model": model, "validation_failed": True,
                "error_type": type(exc).__name__,
            }
        midpoint = len(rows) // 2
        left, left_receipt = _judge_validated(
            rows[:midpoint], inputs[:midpoint], model=model,
            timeout_seconds=timeout_seconds, system=system,
        )
        right, right_receipt = _judge_validated(
            rows[midpoint:], inputs[midpoint:], model=model,
            timeout_seconds=timeout_seconds, system=system,
        )
        receipt = {
            "interface": "authenticated_cli", "cli": "codex",
            "model": model, "packet_split": True,
            "child_receipt_digests": [_sha(left_receipt), _sha(right_receipt)],
            "validation_failure_count": sum(
                int(item.get("validation_failure_count", item.get("validation_failed", False)))
                for item in (left_receipt, right_receipt)
            ),
        }
        return left + right, receipt


def _packets(
    rows: list[sqlite3.Row], inputs: list[dict[str, Any]], *,
    batch_size: int, max_packet_chars: int = 120_000,
) -> list[tuple[list[sqlite3.Row], list[dict[str, Any]]]]:
    """Bound packets by both row count and serialized prompt size."""

    result: list[tuple[list[sqlite3.Row], list[dict[str, Any]]]] = []
    packet_rows: list[sqlite3.Row] = []
    packet_inputs: list[dict[str, Any]] = []
    packet_chars = 0
    for row, judge_input in zip(rows, inputs):
        item_chars = len(canonical_json(judge_input))
        if packet_rows and (
            len(packet_rows) >= batch_size
            or packet_chars + item_chars > max_packet_chars
        ):
            result.append((packet_rows, packet_inputs))
            packet_rows, packet_inputs, packet_chars = [], [], 0
        packet_rows.append(row)
        packet_inputs.append(judge_input)
        packet_chars += item_chars
    if packet_rows:
        result.append((packet_rows, packet_inputs))
    return result


def run_pass(
    work_db: Path, atmem_db: Path, *, judge: str, pass_kind: str,
    model: str, batch_size: int, row_limit: int | None,
    timeout_seconds: int, workers: int = 1,
) -> dict[str, Any]:
    if judge != "codex":
        raise ValueError("stateful Claude adapter is not enabled; use codex")
    if pass_kind not in {"first", "verification"}:
        raise ValueError("pass_kind must be first or verification")
    connection = sqlite3.connect(work_db)
    connection.row_factory = sqlite3.Row
    _migrate(connection)
    memory = Memory(atmem_db, auto_vectors=False, allow_insecure_typed_development=True)
    completed = 0
    run_receipts: list[dict[str, Any]] = []
    try:
        while row_limit is None or completed < row_limit:
            capacity = batch_size * max(1, workers)
            remaining = capacity if row_limit is None else min(capacity, row_limit - completed)
            rows = _ready_rows(
                connection, remaining, judge=judge, pass_kind=pass_kind,
            )
            if not rows:
                break
            inputs = _inputs(memory, rows)
            packets = _packets(rows, inputs, batch_size=batch_size)
            with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
                judged = list(executor.map(
                    lambda packet: _judge_validated(
                        packet[0], packet[1], model=model,
                        timeout_seconds=timeout_seconds,
                    ),
                    packets,
                ))
            decisions = [decision for packet, _receipt in judged for decision in packet]
            row_receipts = [
                receipt for (packet_rows, _packet_inputs), (_decisions, receipt)
                in zip(packets, judged) for _ in packet_rows
            ]
            with connection:
                for row, judge_input, decision, receipt in zip(
                    rows, inputs, decisions, row_receipts,
                ):
                    connection.execute(
                        "INSERT INTO baseline_judgment VALUES (?,?,?,?,?,?,?,?)",
                        (
                            row["observation_id"], judge, pass_kind,
                            canonical_json(decision), _sha(judge_input),
                            canonical_json(receipt), _sha(decision), _now(),
                        ),
                    )
            completed += len(rows)
            run_receipts.extend(receipt for _decisions, receipt in judged)
    finally:
        memory.close()
        connection.close()
    return {
        "judge": judge, "pass_kind": pass_kind, "model": model,
        "completed_rows": completed, "receipt_digest": _sha(run_receipts),
    }


RESOLUTION_SYSTEM = SYSTEM + """

This is a disagreement adjudication pass. Each input also contains
candidate_decisions from two independent passes. Re-evaluate the authentic
observation against current_memories, resolve every supervised field, and
return one final decision. Do not vote mechanically and do not preserve an
unsupported mutation merely to increase coverage."""


def resolve_disagreements(
    work_db: Path, atmem_db: Path, *, model: str, batch_size: int,
    timeout_seconds: int, workers: int = 1,
) -> dict[str, int]:
    connection = sqlite3.connect(work_db)
    connection.row_factory = sqlite3.Row
    _migrate(connection)
    memory = Memory(atmem_db, auto_vectors=False, allow_insecure_typed_development=True)
    try:
        candidates = connection.execute(
            """SELECT b.* FROM baseline_observation b
               WHERE b.status='awaiting_adjudication'
                 AND NOT EXISTS (
                   SELECT 1 FROM baseline_observation earlier
                   WHERE earlier.group_id=b.group_id AND earlier.ordinal < b.ordinal
                     AND earlier.status='awaiting_adjudication'
                 )
                 AND (SELECT COUNT(*) FROM baseline_judgment j
                      WHERE j.observation_id=b.observation_id
                        AND j.pass_kind IN ('first','verification'))=2
                 AND NOT EXISTS (
                   SELECT 1 FROM baseline_judgment j
                   WHERE j.observation_id=b.observation_id
                     AND j.pass_kind='adjudication'
                 )
               ORDER BY b.ordinal,b.group_id,b.observation_id"""
        ).fetchall()
        rows: list[sqlite3.Row] = []
        inputs: list[dict[str, Any]] = []
        for row in candidates:
            values = connection.execute(
                "SELECT pass_kind,decision_json FROM baseline_judgment WHERE observation_id=?",
                (row["observation_id"],),
            ).fetchall()
            decisions = {item["pass_kind"]: json.loads(item["decision_json"]) for item in values}
            if decisions_agree(decisions["first"], decisions["verification"]):
                continue
            judge_input = _inputs(memory, [row])[0]
            judge_input["candidate_decisions"] = [
                decisions["first"], decisions["verification"],
            ]
            rows.append(row)
            inputs.append(judge_input)
        completed = 0
        for offset in range(0, len(rows), batch_size * max(1, workers)):
            batch_rows = rows[offset:offset + batch_size * max(1, workers)]
            batch_inputs = inputs[offset:offset + batch_size * max(1, workers)]
            packets = _packets(batch_rows, batch_inputs, batch_size=batch_size)
            with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
                judged = list(executor.map(
                    lambda packet: _judge_validated(
                        packet[0], packet[1], model=model,
                        timeout_seconds=timeout_seconds, system=RESOLUTION_SYSTEM,
                    ), packets,
                ))
            decisions = [decision for packet, _receipt in judged for decision in packet]
            receipts = [
                receipt for (packet_rows, _packet_inputs), (_decisions, receipt)
                in zip(packets, judged) for _ in packet_rows
            ]
            with connection:
                for row, judge_input, decision, receipt in zip(
                    batch_rows, batch_inputs, decisions, receipts,
                ):
                    connection.execute(
                        "INSERT INTO baseline_judgment VALUES (?,?,?,?,?,?,?,?)",
                        (row["observation_id"], "codex", "adjudication",
                         canonical_json(decision), _sha(judge_input),
                         canonical_json(receipt), _sha(decision), _now()),
                    )
            completed += len(batch_rows)
        return {"completed": completed}
    finally:
        memory.close()
        connection.close()


def _apply_decision(
    memory: Memory, row: sqlite3.Row, decision: dict[str, Any],
) -> tuple[bool, str, str]:
    scope = _scope(row["scope_id"])
    before = _state_digest(memory, row["scope_id"])
    operation = decision["operation"]
    if operation in {"DO_NOT_STORE", "REVIEW"}:
        return False, before, before
    if operation == "FORGET_EXISTING":
        memory.forget_record(
            row["scope_id"], str(decision["target_memory_id"]),
            actor="baseline-adjudicator",
        )
        return True, before, _state_digest(memory, row["scope_id"])

    source_id = "source-" + sha256_hex(canonical_json([
        row["observation_id"], row["source_digest"],
    ]))[:24]
    memory.capture_source(SourceCaptureRequest(
        source_id=source_id,
        idempotency_key="baseline-" + row["observation_id"],
        scope=scope, message=row["content"], source_type="user_message",
    ))
    try:
        proposals = form_typed_proposals(
            row["content"], scope=scope, source_id=source_id,
            formation_id="formation-" + row["observation_id"],
        )
    except ValueError:
        # Authentic prose can resemble a supported deterministic structure
        # while violating its bounded/source-grounded payload contract. Such a
        # row is a rejected baseline transition, never a reason to abort or to
        # weaken the canonical-memory validator.
        return False, before, before
    if not proposals:
        return False, before, before
    target_id = decision["target_memory_id"]
    target_rows = [
        item for item in _state(memory, row["scope_id"])
        if item["id"] == target_id
    ]
    ruling = FormationRulingV2(
        operation=operation, target_memory_id=target_id,
        memory_class=decision["memory_class"],
        operation_probability=1.0, target_probability=1.0 if target_id else None,
        context_sufficient_probability=float(decision["context_sufficient"]),
        durable_probability=float(decision["durable"]),
        future_utility_score=float(decision["future_utility_level"]),
        review_required=False, review_reason=None,
    )
    try:
        governed = apply_ruling_to_proposals(
            ruling, proposals, authorized_targets=target_rows,
        )
    except ValueError:
        return False, before, before
    context = build_resolution_context(
        memory.store, row["scope_id"], scope=scope, window=64,
    )
    outcomes = [
        memory.submit_extraction_proposal(
            proposal, source_text=row["content"],
            actor="baseline-adjudicator", _resolution_context=context,
            _semantic_authority="laya-v2",
        )
        for proposal in governed
    ]
    accepted = bool(outcomes) and all(
        outcome["review_state"] in {"committed", "noop"} for outcome in outcomes
    )
    return accepted, before, _state_digest(memory, row["scope_id"])


def adjudicate(work_db: Path, atmem_db: Path) -> dict[str, Any]:
    connection = sqlite3.connect(work_db)
    connection.row_factory = sqlite3.Row
    _migrate(connection)
    memory = Memory(atmem_db, auto_vectors=False, allow_insecure_typed_development=True)
    accepted = rejected = 0
    try:
        rows = connection.execute(
            "SELECT * FROM baseline_observation WHERE status='awaiting_adjudication' ORDER BY ordinal,group_id"
        ).fetchall()
        for row in rows:
            judgments = connection.execute(
                "SELECT pass_kind,decision_json FROM baseline_judgment WHERE observation_id=? AND judge='codex' ORDER BY pass_kind",
                (row["observation_id"],),
            ).fetchall()
            if len(judgments) < 2:
                continue
            decisions = {
                item["pass_kind"]: json.loads(item["decision_json"])
                for item in judgments
            }
            first, verification = decisions["first"], decisions["verification"]
            agreed = decisions_agree(first, verification)
            if not agreed and "adjudication" not in decisions:
                continue
            decision = first if agreed else decisions["adjudication"]
            resolved = agreed or "adjudication" in decisions
            did_apply, before, after = _apply_decision(memory, row, decision)
            final_accepted = bool(resolved and (
                decision["operation"] in {"DO_NOT_STORE", "DUPLICATE"} or did_apply
            ))
            expected = {
                "format": "atmem-expected-transition-v2",
                "operation": decision["operation"],
                "memory_class": decision["memory_class"],
                "target_memory_id": decision["target_memory_id"],
                "context_sufficient": decision["context_sufficient"],
                "durable": decision["durable"],
                "future_utility_level": decision["future_utility_level"],
                "evidence_memory_ids": decision["evidence_memory_ids"],
                "reason_codes": decision["reason_codes"],
            }
            receipt_core = {
                "format": FORMAT, "observation_id": row["observation_id"],
                "expected": expected, "pre_state_digest": before,
                "post_state_digest": after, "accepted": final_accepted,
                "judgment_digests": [_sha(first), _sha(verification)] + (
                    [_sha(decision)] if not agreed else []
                ),
            }
            receipt_digest = _sha(receipt_core)
            with connection:
                connection.execute(
                    "INSERT INTO baseline_adjudication VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        "receipt-" + receipt_digest[7:31], row["observation_id"],
                        decision["operation"], decision["target_memory_id"],
                        canonical_json(expected), before, after,
                        ("codex-two-pass" if agreed else "codex-two-pass-plus-adjudication"),
                        "gpt-6-luna", receipt_digest,
                        int(final_accepted), _now(),
                    ),
                )
                connection.execute(
                    "UPDATE baseline_observation SET status=? WHERE observation_id=?",
                    ("accepted" if final_accepted else "rejected", row["observation_id"]),
                )
            accepted += int(final_accepted)
            rejected += int(not final_accepted)
    finally:
        memory.close()
        connection.close()
    return {"accepted": accepted, "rejected": rejected}


def run_pipeline(
    work_db: Path, atmem_db: Path, *, model: str, batch_size: int,
    row_limit: int | None, timeout_seconds: int, workers: int = 1,
) -> dict[str, Any]:
    """Run two stateless judge calls then apply each chronological frontier."""

    total_first = total_verification = total_accepted = total_rejected = 0
    while row_limit is None or total_first < row_limit:
        capacity = batch_size * max(1, workers)
        limit = capacity if row_limit is None else min(capacity, row_limit - total_first)
        # Resume an interrupted frontier before asking for any new first-pass
        # decisions.  Otherwise first-pass receipts can strand rows forever.
        pending_verification = run_pass(
            work_db, atmem_db, judge="codex", pass_kind="verification",
            model=model, batch_size=batch_size, row_limit=limit,
            timeout_seconds=timeout_seconds, workers=workers,
        )
        if pending_verification["completed_rows"]:
            resolve_disagreements(
                work_db, atmem_db, model=model, batch_size=batch_size,
                timeout_seconds=timeout_seconds, workers=workers,
            )
            final = adjudicate(work_db, atmem_db)
            total_verification += pending_verification["completed_rows"]
            total_accepted += final["accepted"]
            total_rejected += final["rejected"]
            print(json.dumps({
                "event": "baseline_frontier_resumed",
                "first_pass_rows": total_first,
                "verification_rows": total_verification,
                "accepted": total_accepted, "rejected": total_rejected,
            }, sort_keys=True), flush=True)
            continue
        first = run_pass(
            work_db, atmem_db, judge="codex", pass_kind="first", model=model,
            batch_size=batch_size, row_limit=limit, timeout_seconds=timeout_seconds,
            workers=workers,
        )
        if not first["completed_rows"]:
            break
        verification = run_pass(
            work_db, atmem_db, judge="codex", pass_kind="verification", model=model,
            batch_size=batch_size, row_limit=first["completed_rows"],
            timeout_seconds=timeout_seconds, workers=workers,
        )
        if verification["completed_rows"] != first["completed_rows"]:
            raise RuntimeError("verification pass did not cover the complete frontier")
        resolve_disagreements(
            work_db, atmem_db, model=model, batch_size=batch_size,
            timeout_seconds=timeout_seconds, workers=workers,
        )
        final = adjudicate(work_db, atmem_db)
        total_first += first["completed_rows"]
        total_verification += verification["completed_rows"]
        total_accepted += final["accepted"]
        total_rejected += final["rejected"]
        print(json.dumps({
            "event": "baseline_frontier_completed",
            "first_pass_rows": total_first,
            "verification_rows": total_verification,
            "accepted": total_accepted, "rejected": total_rejected,
        }, sort_keys=True), flush=True)
    return {
        "first_pass_rows": total_first,
        "verification_rows": total_verification,
        "accepted": total_accepted, "rejected": total_rejected,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-db", type=Path, required=True)
    parser.add_argument("--atmem-db", type=Path, required=True)
    parser.add_argument(
        "--action", choices=("first", "verification", "adjudicate", "pipeline"),
        required=True,
    )
    parser.add_argument("--model", default="gpt-6-luna")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--row-limit", type=int)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    if args.action == "pipeline":
        result = run_pipeline(
            args.work_db, args.atmem_db, model=args.model,
            batch_size=args.batch_size, row_limit=args.row_limit,
            timeout_seconds=args.timeout_seconds, workers=args.workers,
        )
    elif args.action == "adjudicate":
        result = adjudicate(args.work_db, args.atmem_db)
    else:
        result = run_pass(
            args.work_db, args.atmem_db, judge="codex", pass_kind=args.action,
            model=args.model, batch_size=args.batch_size,
            row_limit=args.row_limit, timeout_seconds=args.timeout_seconds,
            workers=args.workers,
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
