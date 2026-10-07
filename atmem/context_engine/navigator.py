"""Authorized bounded source navigation for difficult context requests."""

from __future__ import annotations

from dataclasses import dataclass
import time

from atmem.store.sqlite import SQLiteStore

from .contracts import EvidenceRange, NavigationReceipt


@dataclass(frozen=True, slots=True)
class NavigationBudget:
    max_operations: int
    max_bytes: int
    max_elapsed_ms: int

    def __post_init__(self) -> None:
        if min(self.max_operations, self.max_bytes, self.max_elapsed_ms) <= 0:
            raise ValueError("navigation budgets must be positive")


@dataclass(frozen=True, slots=True)
class InspectedEvidence:
    unit_id: str
    source_range: EvidenceRange
    text: str


class EvidenceNavigator:
    identity = "context-navigator-bounded-v1"

    def __init__(
        self, store: SQLiteStore, *, generation_id: str,
        authorized_unit_ids: tuple[str, ...], budget: NavigationBudget,
    ) -> None:
        self.store = store
        self.generation_id = generation_id
        self.authorized = frozenset(authorized_unit_ids)
        self.budget = budget
        self.started = time.perf_counter()
        self.operations = 0
        self.bytes_used = 0
        self.searched_views: list[str] = []
        self.inspected: dict[str, InspectedEvidence] = {}
        self.exhausted = False

    def _operation(self) -> None:
        elapsed = int((time.perf_counter() - self.started) * 1000)
        if elapsed >= self.budget.max_elapsed_ms:
            self.exhausted = True
            raise RuntimeError("navigation elapsed-time budget exhausted")
        if self.operations >= self.budget.max_operations:
            self.exhausted = True
            raise RuntimeError("navigation operation budget exhausted")
        self.operations += 1

    def manifest(self) -> dict[str, object]:
        self._operation()
        if not self.authorized:
            counts: dict[str, int] = {}
        else:
            placeholders = ",".join("?" for _ in self.authorized)
            rows = self.store._conn.execute(
                f"""SELECT kind, COUNT(*) AS n FROM context_evidence_units
                    WHERE generation_id=? AND unit_id IN ({placeholders})
                    GROUP BY kind ORDER BY kind""",
                (self.generation_id, *sorted(self.authorized)),
            ).fetchall()
            counts = {str(row["kind"]): int(row["n"]) for row in rows}
        return {
            "format": "atmem-navigation-manifest-v1",
            "generation_id": self.generation_id,
            "view_counts": counts,
            "authorized_unit_count": len(self.authorized),
        }

    def search(self, query: str, *, kinds: tuple[str, ...] = ()) -> tuple[str, ...]:
        self._operation()
        from .retrieval import _fts_query, _fts_terms

        expression = _fts_query(_fts_terms(query), operator="OR")
        if not expression or not self.authorized or not self.store._context_fts_enabled:
            return ()
        unit_placeholders = ",".join("?" for _ in self.authorized)
        conditions = ""
        params: list[object] = [expression, self.generation_id, *sorted(self.authorized)]
        if kinds:
            kind_placeholders = ",".join("?" for _ in kinds)
            conditions = f" AND u.kind IN ({kind_placeholders})"
            params.extend(kinds)
            self.searched_views.extend(value for value in kinds if value not in self.searched_views)
        rows = self.store._conn.execute(
            f"""SELECT m.unit_id FROM context_units_fts
                JOIN context_units_fts_map m ON m.fts_rowid=context_units_fts.rowid
                JOIN context_evidence_units u
                  ON u.generation_id=m.generation_id AND u.unit_id=m.unit_id
                WHERE context_units_fts MATCH ? AND m.generation_id=?
                  AND m.unit_id IN ({unit_placeholders}) {conditions}
                ORDER BY bm25(context_units_fts), m.unit_id LIMIT 12""",
            tuple(params),
        ).fetchall()
        return tuple(str(row["unit_id"]) for row in rows)

    def inspect(self, unit_id: str) -> InspectedEvidence:
        self._operation()
        if unit_id not in self.authorized:
            raise PermissionError("unit is outside the authorized manifest")
        row = self.store._conn.execute(
            """SELECT r.source_id, r.part_id, r.start_offset, r.end_offset,
                      r.source_sha256, p.content_bytes
               FROM context_unit_ranges ur
               JOIN context_source_ranges r USING(range_id)
               JOIN context_source_parts p
                 ON p.source_id=r.source_id AND p.part_id=r.part_id
               JOIN context_evidence_units u
                 ON u.generation_id=ur.generation_id AND u.unit_id=ur.unit_id
               WHERE ur.generation_id=? AND ur.unit_id=? AND u.lifecycle='active'
               ORDER BY ur.ordinal LIMIT 1""",
            (self.generation_id, unit_id),
        ).fetchone()
        if row is None:
            raise RuntimeError("canonical range is unavailable or inactive")
        start, end = int(row["start_offset"]), int(row["end_offset"])
        body = bytes(row["content_bytes"])
        content = body[start:end]
        if self.bytes_used + len(content) > self.budget.max_bytes:
            self.exhausted = True
            raise RuntimeError("navigation byte budget exhausted")
        self.bytes_used += len(content)
        value = InspectedEvidence(
            unit_id=unit_id,
            source_range=EvidenceRange(
                source_id=str(row["source_id"]), part_id=str(row["part_id"]),
                start=start, end=end, source_sha256=str(row["source_sha256"]),
            ),
            text=content.decode("utf-8", errors="replace"),
        )
        self.inspected[unit_id] = value
        return value

    def follow(self, unit_id: str) -> tuple[str, ...]:
        """Return authorized units on immediately adjacent ordered source parts."""
        self._operation()
        if unit_id not in self.authorized:
            raise PermissionError("unit is outside the authorized manifest")
        unit_placeholders = ",".join("?" for _ in self.authorized)
        rows = self.store._conn.execute(
            f"""WITH origin AS (
                  SELECT r.source_id, p.ordinal
                  FROM context_unit_ranges ur
                  JOIN context_source_ranges r USING(range_id)
                  JOIN context_source_parts p
                    ON p.source_id=r.source_id AND p.part_id=r.part_id
                  WHERE ur.generation_id=? AND ur.unit_id=? LIMIT 1
                )
                SELECT DISTINCT adjacent.unit_id
                FROM origin o
                JOIN context_source_parts p
                  ON p.source_id=o.source_id AND abs(p.ordinal-o.ordinal)=1
                JOIN context_source_ranges r
                  ON r.source_id=p.source_id AND r.part_id=p.part_id
                JOIN context_unit_ranges adjacent ON adjacent.range_id=r.range_id
                WHERE adjacent.generation_id=?
                  AND adjacent.unit_id IN ({unit_placeholders})
                ORDER BY adjacent.unit_id LIMIT 12""",
            (self.generation_id, unit_id, self.generation_id, *sorted(self.authorized)),
        ).fetchall()
        return tuple(str(row["unit_id"]) for row in rows)

    def submit(self, plan_id: str, unit_ids: tuple[str, ...]) -> NavigationReceipt:
        self._operation()
        if any(unit_id not in self.inspected for unit_id in unit_ids):
            raise ValueError("submitted evidence must have been inspected")
        elapsed = int((time.perf_counter() - self.started) * 1000)
        return NavigationReceipt(
            plan_id=plan_id,
            searched_views=tuple(self.searched_views),
            inspected_ranges=tuple(item.source_range for item in self.inspected.values()),
            submitted_ranges=tuple(self.inspected[item].source_range for item in unit_ids),
            operations_used=self.operations,
            bytes_used=self.bytes_used,
            elapsed_ms=elapsed,
            exhausted=self.exhausted,
            navigator_identity=self.identity,
        )
