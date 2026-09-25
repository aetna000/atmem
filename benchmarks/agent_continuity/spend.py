"""Independent benchmark accounting. No provider calls or product evidence store.

Amounts are integer micro-USD. A reservation permits ONE external attempt; callers
must disable implicit SDK retries. Unknown/in-flight charges keep their maximum.
This is not a provider-side billing limit and assumes valid caller upper bounds.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3


class BudgetStop(RuntimeError):
    pass


def encoded(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def integer(value, *, minimum=0):
    if type(value) is not int or not minimum <= value <= 1_000_000_000:
        raise ValueError("expected bounded integer micro-USD/token count")
    return value


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", value):
        raise ValueError("invalid identifier (not a free-text field)")
    return value


class SpendLedger:
    """Supervisor-owned ledger, outside killed workers and per-trial directories."""

    @classmethod
    def create(cls, path: Path, *, authorization_id: str, protocol_sha256: str,
               cap_micro_usd: int = 20_000_000):
        integer(cap_micro_usd, minimum=1)
        identifier(authorization_id)
        if not re.fullmatch(r"[a-f0-9]{64}", protocol_sha256):
            raise ValueError("invalid protocol digest")
        # Exclusive creation: a missing ledger on resume must never reset spending.
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
        db = sqlite3.connect(path)
        try:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            db.execute("CREATE TABLE config (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)")
            db.execute("CREATE TABLE events (seq INTEGER PRIMARY KEY, kind TEXT NOT NULL, attempt TEXT NOT NULL, payload TEXT NOT NULL, UNIQUE(kind,attempt))")
            db.execute("INSERT INTO config VALUES(1,?)", (encoded({
                "authorization_id": authorization_id, "protocol_sha256": protocol_sha256,
                "cap_micro_usd": cap_micro_usd, "currency": "USD", "schema_version": 1}),))
            db.commit()
        finally:
            db.close()
        return cls(path, authorization_id=authorization_id, protocol_sha256=protocol_sha256,
                   cap_micro_usd=cap_micro_usd)

    def __init__(self, path: Path, *, authorization_id: str, protocol_sha256: str,
                 cap_micro_usd: int = 20_000_000):
        self.path = path.resolve()
        with self._transaction() as db:
            config = json.loads(db.execute("SELECT payload FROM config WHERE id=1").fetchone()[0])
        expected = {"authorization_id": authorization_id, "protocol_sha256": protocol_sha256,
                    "cap_micro_usd": cap_micro_usd, "currency": "USD", "schema_version": 1}
        if config != expected:
            raise ValueError("ledger authorization/protocol/cap mismatch")
        self.config = config

    @contextmanager
    def _transaction(self):
        db = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=30)
        try:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _rows(db):
        return [{"sequence": seq, "kind": kind, "attempt_id": attempt, **json.loads(payload)}
                for seq, kind, attempt, payload in db.execute("SELECT * FROM events ORDER BY seq")]

    def _state(self, db):
        events = self._rows(db)
        reserved = {e["attempt_id"]: e for e in events if e["kind"] == "reserved"}
        settled = {e["attempt_id"]: e for e in events if e["kind"] == "settled"}
        known = unresolved = unknown = 0
        breached = False
        by_role = {}
        for attempt, reservation in reserved.items():
            limit = reservation["upper_micro_usd"]
            actual = settled.get(attempt, {}).get("estimated_micro_usd")
            subtotal = by_role.setdefault(reservation["role"], {"estimated_micro_usd": 0,
                "unresolved_reserve_micro_usd": 0, "unknown_attempts": 0})
            if actual is None:
                unresolved += limit
                unknown += 1
                subtotal["unresolved_reserve_micro_usd"] += limit
                subtotal["unknown_attempts"] += 1
            else:
                known += actual
                breached |= actual > limit
                subtotal["estimated_micro_usd"] += actual
        return {"estimated_micro_usd": known, "unresolved_reserve_micro_usd": unresolved,
                "budget_exposure_micro_usd": known + unresolved, "unknown_attempts": unknown,
                "attempts": len(reserved), "reservation_breached": breached,
                "usage_estimate_complete": unknown == 0, "provider_invoice_verified": False,
                "by_role": by_role}

    @staticmethod
    def _append(db, kind, attempt, payload):
        db.execute("INSERT INTO events(kind,attempt,payload) VALUES(?,?,?)",
                   (kind, attempt, encoded({**payload, "recorded_at": datetime.now(timezone.utc).isoformat()})))

    def reserve(self, attempt_id: str, *, upper_micro_usd: int, trial_id: str,
                arm: str, role: str, retry_of: str | None = None, recovery: bool = False):
        """Returns only after durable reservation. Duplicate ID is NEVER dispatchable."""
        for value in (attempt_id, trial_id, arm):
            identifier(value)
        if role not in {"agent", "simulator", "grader"} or type(recovery) is not bool:
            raise ValueError("invalid role/recovery")
        integer(upper_micro_usd, minimum=1)
        if retry_of is not None:
            identifier(retry_of)
        with self._transaction() as db:
            state = self._state(db)
            if state["reservation_breached"]:
                raise BudgetStop("previous bound underestimated; further dispatch stopped")
            if db.execute("SELECT 1 FROM events WHERE kind='reserved' AND attempt=?", (attempt_id,)).fetchone():
                raise BudgetStop("attempt already reserved; do not dispatch again")
            if retry_of is not None:
                previous = db.execute("SELECT payload FROM events WHERE kind='reserved' AND attempt=?", (retry_of,)).fetchone()
                if previous is None or any(json.loads(previous[0])[k] != v for k, v in
                                           {"trial_id": trial_id, "arm": arm, "role": role}.items()):
                    raise ValueError("retry must reference same trial/arm/role")
            if state["budget_exposure_micro_usd"] + upper_micro_usd > self.config["cap_micro_usd"]:
                raise BudgetStop("insufficient unreserved budget")
            self._append(db, "reserved", attempt_id, {"upper_micro_usd": upper_micro_usd,
                "trial_id": trial_id, "arm": arm, "role": role, "retry_of": retry_of, "recovery": recovery})

    def settle(self, attempt_id: str, *, estimated_micro_usd: int | None,
               input_tokens: int | None = None, output_tokens: int | None = None,
               reason: str | None = None, artifact_sha256: str | None = None):
        # Unknown settlements intentionally retain headroom permanently in this
        # pilot. Later provider reconciliation needs a separately audited event.
        identifier(attempt_id)
        if estimated_micro_usd is None:
            identifier(reason)
        else:
            integer(estimated_micro_usd)
            integer(input_tokens)
            integer(output_tokens)
            if reason is not None:
                raise ValueError("known estimate must not have unknown reason")
        for count in (input_tokens, output_tokens):
            if count is not None:
                integer(count)
        if artifact_sha256 is not None and not re.fullmatch(r"[a-f0-9]{64}", artifact_sha256):
            raise ValueError("invalid evidence artifact digest")
        payload = {"estimated_micro_usd": estimated_micro_usd, "input_tokens": input_tokens,
                   "output_tokens": output_tokens, "reason": reason, "artifact_sha256": artifact_sha256}
        with self._transaction() as db:
            if not db.execute("SELECT 1 FROM events WHERE kind='reserved' AND attempt=?", (attempt_id,)).fetchone():
                raise ValueError("unreserved attempt")
            prior = db.execute("SELECT payload FROM events WHERE kind='settled' AND attempt=?", (attempt_id,)).fetchone()
            if prior:
                previous = json.loads(prior[0])
                previous.pop("recorded_at")
                if previous != payload:
                    raise ValueError("conflicting settlement; original preserved")
                return
            self._append(db, "settled", attempt_id, payload)

    def snapshot(self):
        with self._transaction() as db:
            payload = {"config": self.config, "summary": self._state(db), "events": self._rows(db)}
        return {**payload, "payload_sha256": hashlib.sha256(encoded(payload).encode()).hexdigest()}

    def export(self, path: Path):
        """Never overwrite previous exports. Hash detects changes, not authenticity."""
        snapshot = self.snapshot()
        with path.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(snapshot, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        return snapshot
