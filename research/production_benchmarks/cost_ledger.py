"""Crash-safe reservation ledger for explicitly authorized paid benchmarks."""

from __future__ import annotations

import json
import os
from pathlib import Path
import uuid

from atmem.locking import ProcessFileLock


class DurableCostLedger:
    """Reserve worst-case spend before egress and refuse blind retries."""

    def __init__(self, path: str | Path, *, total_cap_usd: float) -> None:
        self.path = Path(path).expanduser().resolve()
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        self.total_cap_usd = float(total_cap_usd)
        if self.total_cap_usd <= 0:
            raise ValueError("total_cap_usd must be positive")

    def rows(self) -> list[dict]:
        if not self.path.exists():
            return []
        value = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(value, list):
            raise RuntimeError("paid-call ledger is malformed")
        return value

    def reserve(
        self, key: str, *, provider: str, maximum_usd: float,
        metadata: dict | None = None,
    ) -> dict:
        maximum = float(maximum_usd)
        if not key or not provider or maximum <= 0:
            raise ValueError("reservation key, provider and positive maximum are required")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with ProcessFileLock(self.lock_path, exclusive=True):
            rows = self.rows()
            if any(row.get("key") == key for row in rows):
                raise RuntimeError(
                    f"paid call {key} was already reserved; refusing a blind retry"
                )
            reserved = sum(float(row.get("reserved_max_usd") or 0.0) for row in rows)
            if reserved + maximum > self.total_cap_usd:
                raise RuntimeError("durable paid-call cost cap would be exceeded")
            row = {
                "key": key,
                "provider": provider,
                "state": "reserved",
                "reserved_max_usd": maximum,
                "cost_usd": None,
                "metadata": dict(metadata or {}),
            }
            rows.append(row)
            self._write(rows)
            return dict(row)

    def complete(self, key: str, *, cost_usd: float) -> dict:
        cost = float(cost_usd)
        if cost < 0:
            raise ValueError("cost_usd cannot be negative")
        with ProcessFileLock(self.lock_path, exclusive=True):
            rows = self.rows()
            matches = [row for row in rows if row.get("key") == key]
            if len(matches) != 1 or matches[0].get("state") != "reserved":
                raise RuntimeError(f"paid call {key} has no unique active reservation")
            row = matches[0]
            if cost > float(row["reserved_max_usd"]):
                raise RuntimeError(f"paid call {key} exceeded its reserved maximum")
            row["state"] = "completed"
            row["cost_usd"] = cost
            self._write(rows)
            return dict(row)

    def _write(self, rows: list[dict]) -> None:
        temporary = self.path.with_name(f".{self.path.name}.{uuid.uuid4().hex}.tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(rows, indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.path)
        if os.name != "nt":
            descriptor = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
