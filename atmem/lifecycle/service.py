"""Canonical lifecycle evaluation and generation-checked transitions."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import uuid
from typing import Any

from .invalidation import InvalidationRegistry, invalidation_registry
from .models import ALLOWED_TRANSITIONS, LifecycleState, LifecycleTransition, TransitionReceipt


def _utc(value: str | None = None) -> datetime:
    parsed = datetime.now(timezone.utc) if value is None else datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("lifecycle evaluation time must include a timezone")
    return parsed.astimezone(timezone.utc)


class LifecycleService:
    def __init__(self, store: Any, *, invalidators: InvalidationRegistry | None = None) -> None:
        self.store = store
        self.invalidators = invalidators or invalidation_registry

    def inspect(self, subject_id: str, record_id: str, *, evaluated_at: str | None = None) -> dict[str, Any]:
        record = self.store.get_record(subject_id, record_id)
        if record is None:
            raise KeyError(record_id)
        row = self.store._conn.execute(
            "SELECT * FROM memory_lifecycle WHERE subject_id = ? AND record_id = ?",
            (subject_id, record_id),
        ).fetchone()
        if row is None:
            state = self._legacy_state(str(record["status"]))
            learned_at = str(record["created_at"])
            now = datetime.now(timezone.utc).isoformat()
            with self.store.transaction():
                self.store._conn.execute(
                    "INSERT OR IGNORE INTO memory_lifecycle(subject_id,record_id,state,generation,learned_at,updated_at) VALUES(?,?,?,1,?,?)",
                    (subject_id, record_id, state.value, learned_at, now),
                )
            row = self.store._conn.execute(
                "SELECT * FROM memory_lifecycle WHERE subject_id = ? AND record_id = ?", (subject_id, record_id)
            ).fetchone()
        value = dict(row)
        at = _utc(evaluated_at)
        eligible, reasons = self._eligibility(value, at)
        policy = json.loads(value.pop("policy_json", "{}"))
        return {
            "format": "atmem-memory-lifecycle-v1",
            **value,
            "policy": policy,
            "evaluated_at": at.isoformat(),
            "eligible": eligible,
            "reason_codes": reasons,
            "allowed_transitions": sorted(item.value for item in ALLOWED_TRANSITIONS[LifecycleState(value["state"])]),
            "timeline": self.history(subject_id, record_id),
        }

    def transition(self, request: LifecycleTransition) -> TransitionReceipt:
        current = self.inspect(request.subject_id, request.record_id, evaluated_at=request.occurred_at)
        source = LifecycleState(current["state"])
        if request.base_generation != int(current["generation"]):
            raise RuntimeError("lifecycle generation precondition failed")
        if request.to_state not in ALLOWED_TRANSITIONS[source]:
            raise ValueError(f"transition {source.value} -> {request.to_state.value} is not allowed")
        if not request.actor.strip() or not request.reason.strip():
            raise ValueError("actor and reason are required")
        occurred = _utc(request.occurred_at).isoformat()
        transition_id = f"lct_{uuid.uuid4().hex}"
        resulting = request.base_generation + 1
        invalidations = self.invalidators.invalidate(request.subject_id, request.record_id)
        timestamp_column = {
            LifecycleState.SUPERSEDED: "replaced_at",
            LifecycleState.ARCHIVED: "archived_at",
            LifecycleState.FORGOTTEN: "deleted_at",
        }.get(request.to_state)
        with self.store.transaction():
            changed = self.store._conn.execute(
                "UPDATE memory_lifecycle SET state=?,generation=?,updated_at=? WHERE subject_id=? AND record_id=? AND generation=?",
                (request.to_state.value, resulting, occurred, request.subject_id, request.record_id, request.base_generation),
            ).rowcount
            if changed != 1:
                raise RuntimeError("lifecycle generation precondition failed")
            if timestamp_column:
                self.store._conn.execute(
                    f"UPDATE memory_lifecycle SET {timestamp_column}=? WHERE subject_id=? AND record_id=?",
                    (occurred, request.subject_id, request.record_id),
                )
            self.store._conn.execute(
                "INSERT INTO memory_lifecycle_transitions VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (transition_id, request.subject_id, request.record_id, source.value, request.to_state.value, request.base_generation, resulting, request.actor, request.reason, json.dumps(list(request.evidence)), json.dumps(invalidations, sort_keys=True), occurred),
            )
        return TransitionReceipt(transition_id, request.record_id, request.subject_id, source, request.to_state, request.base_generation, resulting, request.actor, request.reason, occurred, invalidations)

    def history(self, subject_id: str, record_id: str) -> list[dict[str, Any]]:
        rows = self.store._conn.execute(
            "SELECT * FROM memory_lifecycle_transitions WHERE subject_id=? AND record_id=? ORDER BY occurred_at, transition_id",
            (subject_id, record_id),
        ).fetchall()
        return [{**dict(row), "evidence": json.loads(row["evidence_json"]), "invalidations": json.loads(row["invalidation_json"])} for row in rows]

    @staticmethod
    def _legacy_state(status: str) -> LifecycleState:
        return {"active": LifecycleState.ACTIVE, "quarantined": LifecycleState.QUARANTINED, "superseded": LifecycleState.SUPERSEDED, "tombstoned": LifecycleState.FORGOTTEN}.get(status, LifecycleState.QUARANTINED)

    @staticmethod
    def _eligibility(value: dict[str, Any], at: datetime) -> tuple[bool, list[str]]:
        state = LifecycleState(str(value["state"]))
        reasons: list[str] = []
        if state is not LifecycleState.ACTIVE:
            reasons.append(f"state_{state.value}")
        for field, relation in (("valid_from", "before_valid_from"), ("valid_to", "after_valid_to"), ("expires_at", "expired")):
            if value.get(field):
                boundary = _utc(str(value[field]))
                if (field == "valid_from" and at < boundary) or (field != "valid_from" and at >= boundary):
                    reasons.append(relation)
        return not reasons, reasons or ["eligible"]
