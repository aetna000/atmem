"""Database-view self-review passes for a frozen CLI judge history."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import uuid
from typing import Any, Callable

from . import label_dataset
from .workdb import REVIEW_VIEWS, initialize, transaction


REVIEW_ITEM_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "candidate_id": {"type": "string"},
        "label": label_dataset.LABEL_SCHEMA,
        "change_reason": {"type": "string", "minLength": 1, "maxLength": 500},
    },
    "required": ["candidate_id", "label", "change_reason"],
}
REVIEW_BATCH_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"labels": {"type": "array", "items": REVIEW_ITEM_SCHEMA}},
    "required": ["labels"],
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _latest(connection: sqlite3.Connection, judge: str) -> dict[str, sqlite3.Row]:
    return {
        row["candidate_id"]: row
        for row in connection.execute(
            "SELECT * FROM latest_valid_judgment WHERE judge=? ORDER BY candidate_id", (judge,)
        )
    }


def select_review_candidates(
    connection: sqlite3.Connection, judge: str, view: str,
) -> list[list[str]]:
    if view not in REVIEW_VIEWS:
        raise ValueError(f"unknown review view: {view}")
    latest = _latest(connection, judge)
    if view == "duplicate_clusters":
        groups: list[list[str]] = []
        for row in connection.execute(
            """SELECT dm.cluster_id, group_concat(dm.candidate_id)
               FROM duplicate_member dm GROUP BY dm.cluster_id HAVING COUNT(*) > 1
               ORDER BY dm.cluster_id"""
        ):
            members = [candidate_id for candidate_id in row[1].split(",") if candidate_id in latest]
            if len(members) > 1:
                groups.append(sorted(members))
        return groups

    selected: list[str] = []
    if view == "scope_chronology":
        for row in connection.execute(
            "SELECT candidate_id, authorized_input_json FROM candidate ORDER BY candidate_id"
        ):
            if row[0] not in latest:
                continue
            state = json.loads(row[1])
            if sum(turn.get("role") == "user" for turn in state["turns"]) > 1:
                selected.append(row[0])
    elif view == "stratified":
        strata: dict[tuple[str, str, str], list[str]] = {}
        languages = dict(connection.execute("SELECT candidate_id, language FROM candidate"))
        for candidate_id, judgment in latest.items():
            confidence = float(judgment["confidence"])
            band = "low" if confidence < 0.7 else "mid" if confidence < 0.9 else "high"
            decision = json.loads(judgment["decision_json"])
            key = (languages[candidate_id], decision["disposition"], band)
            strata.setdefault(key, []).append(candidate_id)
        for members in strata.values():
            members.sort(key=lambda value: hashlib.sha256(value.encode()).digest())
            selected.extend(members[: max(5, min(50, round(len(members) * 0.02)))])
    else:
        cluster_labels: dict[str, set[str]] = {}
        for row in connection.execute(
            """SELECT dm.cluster_id, dm.candidate_id FROM duplicate_member dm
               ORDER BY dm.cluster_id, dm.candidate_id"""
        ):
            if row[1] in latest:
                decision = json.loads(latest[row[1]]["decision_json"])
                cluster_labels.setdefault(row[0], set()).add(decision["disposition"])
        conflicting = {
            row[1]
            for row in connection.execute(
                "SELECT cluster_id, candidate_id FROM duplicate_member ORDER BY cluster_id"
            )
            if len(cluster_labels.get(row[0], set())) > 1
        }
        for candidate_id, judgment in latest.items():
            decision = json.loads(judgment["decision_json"])
            if (
                float(judgment["confidence"]) < 0.75
                or decision["disposition"] in {"UPDATE", "DUPLICATE", "FORGET", "REVIEW"}
                or candidate_id in conflicting
            ):
                selected.append(candidate_id)
    return [[candidate_id] for candidate_id in sorted(set(selected))]


def build_review_queue(
    database: Path, judge: str, view: str, pass_number: int,
    *, target_tokens: int = 24_000, max_rows: int = 80,
) -> dict[str, int]:
    connection = initialize(database)
    try:
        groups = select_review_candidates(connection, judge, view)
        lengths = dict(connection.execute(
            "SELECT candidate_id, length(authorized_input_json) FROM candidate"
        ))
        packets: list[list[str]] = []
        current: list[str] = []
        tokens = 0
        for group in groups:
            group_tokens = sum(max(1, int(lengths[item] / 3.2)) + 400 for item in group)
            if current and (tokens + group_tokens > target_tokens or len(current) + len(group) > max_rows):
                packets.append(current)
                current, tokens = [], 0
            current.extend(group)
            tokens += group_tokens
        if current:
            packets.append(current)
        with transaction(connection):
            for index, candidate_ids in enumerate(packets):
                connection.execute(
                    """INSERT OR IGNORE INTO work_queue(
                       judge, pass_kind, cluster_key, candidate_ids_json, token_estimate,
                       state, attempts
                    ) VALUES (?, ?, ?, ?, ?, 'pending', 0)""",
                    (
                        judge, view, f"p{pass_number}:{index:08d}", _canonical(candidate_ids),
                        sum(max(1, int(lengths[item] / 3.2)) + 400 for item in candidate_ids),
                    ),
                )
        return {"packets": len(packets), "candidates": sum(len(packet) for packet in packets)}
    finally:
        connection.close()


def _review_prompt(view: str, items: list[dict[str, Any]]) -> str:
    return label_dataset.SYSTEM + f"""

SELF-REVIEW PASS: {view}
You are reviewing only your own earlier frozen decisions. Re-evaluate every
item through this named database view. Return the prior label unchanged when it
is correct. If it changes, change_reason must name the concrete evidence and
error; otherwise use "unchanged after {view} review". Do not infer that a
cross-user semantic cluster is a same-user DUPLICATE.

REVIEW ITEMS:
{_canonical(items)}
"""


def run_review_pass(
    database: Path, judge: str, model: str, view: str, pass_number: int,
    *, max_packets: int | None = None, timeout_seconds: int = 1_800,
    reviewer: Callable[..., tuple[dict[str, Any], dict[str, Any]]] | None = None,
) -> dict[str, int]:
    if reviewer is None:
        reviewer = lambda prompt, **kwargs: label_dataset._codex_structured(  # noqa: E731
            prompt, REVIEW_BATCH_SCHEMA, **kwargs
        )
    connection = initialize(database)
    try:
        run_row = connection.execute(
            "SELECT run_id FROM judge_run WHERE judge=? AND pass_kind=? AND pass_number=?",
            (judge, view, pass_number),
        ).fetchone()
        if run_row:
            run_id = run_row[0]
        else:
            run_id = f"{judge}-{view}-{pass_number}-{uuid.uuid4().hex[:12]}"
            with transaction(connection):
                connection.execute(
                    "INSERT INTO judge_run VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'running', ?, NULL, NULL)",
                    (
                        run_id, judge, "codex-cli-0.162.1", model,
                        _digest(label_dataset.SYSTEM), _digest(REVIEW_BATCH_SCHEMA),
                        view, pass_number, _now(),
                    ),
                )
        completed = changed = reviewed = 0
        while max_packets is None or completed < max_packets:
            with transaction(connection):
                work = connection.execute(
                    """SELECT * FROM work_queue WHERE judge=? AND pass_kind=?
                       AND cluster_key LIKE ? AND state IN ('pending','failed') AND attempts < 3
                       ORDER BY work_id LIMIT 1""",
                    (judge, view, f"p{pass_number}:%"),
                ).fetchone()
                if work is not None:
                    connection.execute(
                        """UPDATE work_queue SET state='leased', lease_owner=?,
                           lease_expires_at=?, attempts=attempts+1 WHERE work_id=?""",
                        (
                            f"{judge}-review-{uuid.uuid4().hex[:12]}",
                            (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat().replace("+00:00", "Z"),
                            work["work_id"],
                        ),
                    )
            if work is None:
                break
            ids = json.loads(work["candidate_ids_json"])
            latest = _latest(connection, judge)
            items = []
            candidates: dict[str, dict[str, Any]] = {}
            for candidate_id in ids:
                candidate = connection.execute(
                    "SELECT authorized_input_json FROM candidate WHERE candidate_id=?", (candidate_id,)
                ).fetchone()
                state = json.loads(candidate[0])
                candidates[candidate_id] = {"candidate_id": candidate_id, "authorized_input": state}
                items.append({
                    "candidate_id": candidate_id,
                    "state": state,
                    "prior_label": json.loads(latest[candidate_id]["decision_json"]),
                })
            try:
                payload, receipt = reviewer(
                    _review_prompt(view, items), model=model, timeout_seconds=timeout_seconds,
                )
                outputs = payload.get("labels")
                if not isinstance(outputs, list) or [item.get("candidate_id") for item in outputs] != ids:
                    raise ValueError("review output IDs/order differ from work packet")
                receipt_id = f"query-{uuid.uuid4().hex}"
                packet_changes = 0
                with transaction(connection):
                    connection.execute(
                        "INSERT INTO query_receipt VALUES (?, ?, NULL, ?, ?, ?, ?, ?)",
                        (
                            receipt_id, run_id, view,
                            _canonical({"pass_number": pass_number, "candidate_ids": ids}),
                            _canonical(ids), _digest(ids), _now(),
                        ),
                    )
                    for output in outputs:
                        candidate_id = output["candidate_id"]
                        decision = output["label"]
                        label_dataset._validate(candidates[candidate_id], decision)
                        prior = latest[candidate_id]
                        decision_digest = _digest(decision)
                        if decision_digest != prior["decision_digest"]:
                            packet_changes += 1
                        connection.execute(
                            """INSERT INTO judgment(
                               candidate_id, run_id, judge, pass_kind, pass_number,
                               prior_judgment_id, disposition, memory_class, decision_json,
                               decision_digest, change_reason, query_receipt_ids_json,
                               output_digest, confidence, validation_state, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'valid', ?)""",
                            (
                                candidate_id, run_id, judge, view, pass_number,
                                prior["judgment_id"], decision["disposition"], decision["memory_class"],
                                _canonical(decision), decision_digest, output["change_reason"],
                                _canonical([receipt_id]), receipt["output_sha256"],
                                float(decision["confidence"]), _now(),
                            ),
                        )
                    connection.execute(
                        """UPDATE work_queue SET state='complete', lease_owner=NULL,
                           lease_expires_at=NULL WHERE work_id=?""", (work["work_id"],)
                    )
                completed += 1
                reviewed += len(ids)
                changed += packet_changes
            except Exception as exc:
                with transaction(connection):
                    connection.execute(
                        """UPDATE work_queue SET state='failed', lease_owner=NULL,
                           lease_expires_at=NULL, last_error=? WHERE work_id=?""",
                        (str(exc)[-1000:], work["work_id"]),
                    )
                if work["attempts"] + 1 >= 3:
                    raise
        remaining = connection.execute(
            """SELECT COUNT(*) FROM work_queue WHERE judge=? AND pass_kind=?
               AND cluster_key LIKE ? AND state!='complete'""",
            (judge, view, f"p{pass_number}:%"),
        ).fetchone()[0]
        if remaining == 0:
            with transaction(connection):
                connection.execute(
                    "UPDATE judge_run SET status='complete', completed_at=?, run_digest=? WHERE run_id=?",
                    (_now(), _digest({"reviewed": reviewed, "changed": changed}), run_id),
                )
        return {"packets": completed, "reviewed": reviewed, "changed": changed, "remaining": remaining}
    finally:
        connection.close()


def freeze_judge(database: Path, judge: str) -> dict[str, Any]:
    connection = initialize(database)
    try:
        first_pass = connection.execute(
            "SELECT COUNT(*) FROM judgment WHERE judge=? AND pass_kind='first_pass'", (judge,)
        ).fetchone()[0]
        completed = {
            row[0] for row in connection.execute(
                "SELECT DISTINCT pass_kind FROM judge_run WHERE judge=? AND status='complete'", (judge,)
            )
        }
        missing = set(REVIEW_VIEWS) - completed
        if not first_pass or missing:
            raise RuntimeError(f"judge cannot freeze; first_pass={first_pass}, missing_views={sorted(missing)}")
        history = [tuple(row) for row in connection.execute(
            "SELECT candidate_id, decision_digest FROM latest_valid_judgment WHERE judge=? ORDER BY candidate_id",
            (judge,),
        )]
        with transaction(connection):
            connection.execute(
                "INSERT INTO judge_freeze VALUES (?, ?, ?, ?, ?)",
                (judge, _now(), first_pass, _canonical(list(REVIEW_VIEWS)), _digest(history)),
            )
        return {"judge": judge, "first_pass_rows": first_pass, "history_digest": _digest(history)}
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--judge", choices=("codex",), default="codex")
    parser.add_argument("--model", default="gpt-5.6-sol")
    parser.add_argument("--view", choices=REVIEW_VIEWS)
    parser.add_argument("--pass-number", type=int, default=1)
    parser.add_argument("--build-queue", action="store_true")
    parser.add_argument("--max-packets", type=int)
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()
    if args.freeze:
        print(json.dumps(freeze_judge(args.database, args.judge), indent=2))
        return
    if not args.view:
        parser.error("--view is required unless --freeze is used")
    if args.build_queue:
        print(json.dumps(build_review_queue(
            args.database, args.judge, args.view, args.pass_number,
        ), indent=2))
    print(json.dumps(run_review_pass(
        args.database, args.judge, args.model, args.view, args.pass_number,
        max_packets=args.max_packets,
    ), indent=2))


if __name__ == "__main__":
    main()
