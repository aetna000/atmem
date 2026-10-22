"""Offline experiment safeguards. No model, network or credential access."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import json
import random
import sqlite3
from pathlib import Path
from typing import Any, Iterable

ROLES = frozenset({"development", "validation", "confirmation"})


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                      allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class Task:
    task_id: str
    corpus: str
    role: str
    stratum: str
    clusters: tuple[str, ...]
    exposed: bool = False

    def __post_init__(self) -> None:
        if not all(isinstance(x, str) and x.strip() for x in
                   (self.task_id, self.corpus, self.stratum)):
            raise ValueError("task identity, corpus and stratum are required")
        if self.role not in ROLES or not self.clusters:
            raise ValueError("valid role and source/participant clusters required")
        if any(not isinstance(x, str) or not x.strip() for x in self.clusters):
            raise ValueError("empty cluster")
        if self.exposed and self.role != "development":
            raise ValueError("inspected tasks must be development-only")


def validate_splits(tasks: Iterable[Task]) -> None:
    seen: set[tuple[str, str]] = set()
    owners: dict[tuple[str, str], str] = {}
    for task in tasks:
        key = (task.corpus, task.task_id)
        if key in seen:
            raise ValueError("duplicate task identity")
        seen.add(key)
        for cluster in task.clusters:
            key = (task.corpus, cluster)
            if owners.setdefault(key, task.role) != task.role:
                raise ValueError("source/participant cluster crosses split roles")


def stratified_sample(tasks: Iterable[Task], *, role: str, per_stratum: int,
                      seed: int) -> tuple[Task, ...]:
    tasks = tuple(tasks)
    validate_splits(tasks)
    if role not in ROLES or type(per_stratum) is not int or per_stratum <= 0:
        raise ValueError("valid role and positive sample size required")
    groups: dict[tuple[str, str], list[Task]] = defaultdict(list)
    for task in tasks:
        if task.role == role:
            groups[(task.corpus, task.stratum)].append(task)
    if not groups:
        raise ValueError("no eligible tasks")
    rng = random.Random(seed)
    result = []
    for key in sorted(groups):
        group = sorted(groups[key], key=lambda t: t.task_id)
        if len(group) < per_stratum:
            raise ValueError("insufficient stratum; never silently undersample")
        result.extend(rng.sample(group, per_stratum))
    return tuple(result)


def microdollars(value: str | Decimal) -> int:
    if not isinstance(value, (str, Decimal)):
        raise ValueError("cost must be a decimal string, never binary float")
    try:
        number = Decimal(value)
        precise = number.quantize(Decimal(".000001")) if number.is_finite() else None
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("invalid cost") from exc
    if not number.is_finite() or number < 0 or number != precise:
        raise ValueError("cost must be nonnegative finite USD with <=6 decimals")
    return int(number * 1_000_000)


class CampaignLedger:
    """Cross-process reservations, including unknown/in-flight costs.

    Cost metadata only. Final-run reserves are ordinary named reservations and
    cannot be spent by a tuning reservation. Connections must be closed by caller.
    """

    def __init__(self, path: Path, *, ceiling: str = "250") -> None:
        self.db = sqlite3.connect(path, timeout=10, isolation_level=None)
        self.db.execute("PRAGMA busy_timeout=10000")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS budget(singleton INTEGER PRIMARY KEY CHECK(singleton=1), cap INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS entries(id TEXT PRIMARY KEY, state TEXT NOT NULL, amount INTEGER NOT NULL CHECK(amount>=0));
        """)
        cap = microdollars(ceiling)
        self.db.execute("INSERT OR IGNORE INTO budget VALUES(1,?)", (cap,))
        if self.db.execute("SELECT cap FROM budget").fetchone()[0] != cap:
            self.db.close()
            raise ValueError("campaign ceiling cannot change on reopen")

    def reserve(self, identity: str, usd: str) -> None:
        amount = microdollars(usd)
        if not identity.strip() or amount <= 0:
            raise ValueError("nonempty identity and positive reservation required")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            if self.db.execute("SELECT 1 FROM entries WHERE state='overrun' LIMIT 1").fetchone():
                raise ValueError("provider overrun requires reconciliation")
            existing = self.db.execute("SELECT state,amount FROM entries WHERE id=?", (identity,)).fetchone()
            if existing:
                if existing != ("reserved", amount):
                    raise ValueError("reservation identity conflict")
            else:
                used = self.db.execute("SELECT COALESCE(SUM(amount),0) FROM entries").fetchone()[0]
                cap = self.db.execute("SELECT cap FROM budget").fetchone()[0]
                if used + amount > cap:
                    raise ValueError("budget exhausted, including reserved funds")
                self.db.execute("INSERT INTO entries VALUES(?, 'reserved', ?)", (identity, amount))
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def settle(self, identity: str, usd: str | None) -> None:
        if usd is None:
            raise ValueError("unknown usage retains reservation; it is not zero")
        amount = microdollars(usd)
        overrun = False
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("SELECT state,amount FROM entries WHERE id=?", (identity,)).fetchone()
            if row is None:
                raise ValueError("missing reservation")
            if row[0] in {"spent", "overrun"}:
                if row[1] != amount:
                    raise ValueError("settlement identity conflict")
            else:
                overrun = amount > row[1]
                self.db.execute("UPDATE entries SET state=?,amount=? WHERE id=?",
                                ("overrun" if overrun else "spent", amount, identity))
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        if overrun:
            raise ValueError("actual cost exceeds reservation; retained, reconciliation required")

    def snapshot(self) -> dict[str, int]:
        rows = dict(self.db.execute("SELECT state,SUM(amount) FROM entries GROUP BY state"))
        return {"spent_micro_usd": rows.get("spent", 0) + rows.get("overrun", 0),
                "reserved_micro_usd": rows.get("reserved", 0),
                "ceiling_micro_usd": self.db.execute("SELECT cap FROM budget").fetchone()[0]}

    def close(self) -> None:
        self.db.close()
