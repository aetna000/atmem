"""Bounded obligation-first lexical retrieval over persistent V3 indexes."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re

from atmem.store.sqlite import SQLiteStore

from .contracts import QueryPlan
from .pools import POOL_KINDS, PoolBudget


_STOP = {
    "a", "an", "and", "as", "be", "does", "do", "for", "how", "in", "is", "of",
    "the", "to", "what", "when", "where", "which", "why", "on", "with", "my",
    "our", "its", "please", "create", "send", "post", "inspect", "review", "comment",
    "find", "update", "short", "concise", "note", "document", "reference", "include",
    "state", "briefly", "actual", "another", "current", "earlier", "conversation",
}


def _fts_terms(value: str) -> tuple[str, ...]:
    value = re.sub(r"^\s*\[\d{4}-\d{2}-\d{2}\]\s*", "", value)
    terms = [
        token.casefold() for token in re.findall(r"[^\W_]+", value, re.UNICODE)
        if token.casefold() not in _STOP and len(token) > 1
    ]
    return tuple(dict.fromkeys(terms))


def _fts_query(terms: tuple[str, ...], *, operator: str) -> str:
    if operator not in {"AND", "OR"}:
        raise ValueError("unsupported FTS operator")
    return f" {operator} ".join(
        f'"{term.replace(chr(34), chr(34) * 2)}"' for term in terms
    )


@dataclass(frozen=True, slots=True)
class RetrievedCandidate:
    unit_id: str
    kind: str
    source_id: str
    part_id: str
    start: int
    end: int
    text: str
    score: float
    matched_obligation_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    candidates: tuple[RetrievedCandidate, ...]
    searched_pools: tuple[str, ...]
    scanned_units: int
    exhausted: bool


class DeterministicRetriever:
    def __init__(self, store: SQLiteStore, *, budget: PoolBudget | None = None) -> None:
        self.store = store
        self.budget = budget or PoolBudget()
        self._cache: dict[tuple[object, ...], RetrievalResult] = {}
        self.cache_hits = 0

    def _pool(
        self, generation_id: str, kind: str, query: str,
        allowed_unit_ids: frozenset[str] | None = None,
    ) -> list[RetrievedCandidate]:
        terms = _fts_terms(query)
        range_indexed = bool(
            getattr(self.store, "_context_range_fts_enabled", False)
            and self.store._conn.execute(
                "SELECT 1 FROM context_range_fts_map WHERE generation_id=? LIMIT 1",
                (generation_id,),
            ).fetchone()
        )
        if not terms or not (range_indexed or self.store._context_fts_enabled):
            return []
        allowed_sql = ""
        allowed_params: tuple[str, ...] = ()
        if allowed_unit_ids is not None:
            if not allowed_unit_ids:
                return []
            unit_alias = "ur" if range_indexed else "m"
            allowed_sql = " AND " + unit_alias + ".unit_id IN (" + ",".join(
                "?" for _ in allowed_unit_ids
            ) + ")"
            allowed_params = tuple(sorted(allowed_unit_ids))
        if range_indexed:
            # Materialize a bounded lexical shortlist before relational joins
            # and force that join order. Otherwise SQLite may begin with every
            # unit in the encrypted generation for each typed pool.
            sql = f"""WITH ranked AS (
                        SELECT rowid, bm25(context_ranges_fts) AS rank
                        FROM context_ranges_fts
                        WHERE context_ranges_fts MATCH ?
                        ORDER BY rank LIMIT ?
                      )
                      SELECT ur.unit_id, ranked.rank AS rank,
                             r.source_id, r.part_id, r.start_offset, r.end_offset,
                             p.content_bytes
                      FROM ranked
                      CROSS JOIN context_range_fts_map m
                        ON m.fts_rowid=ranked.rowid
                      CROSS JOIN context_unit_ranges ur
                        ON ur.generation_id=m.generation_id AND ur.range_id=m.range_id
                      CROSS JOIN context_evidence_units u
                        ON u.generation_id=ur.generation_id AND u.unit_id=ur.unit_id
                      CROSS JOIN context_unit_views v
                        ON v.generation_id=u.generation_id AND v.unit_id=u.unit_id
                      CROSS JOIN context_source_ranges r ON r.range_id=m.range_id
                      CROSS JOIN context_source_parts p
                        ON p.source_id=r.source_id AND p.part_id=r.part_id
                      WHERE m.generation_id=?
                        AND v.kind=? AND u.lifecycle='active' {allowed_sql}
                      ORDER BY ranked.rank, ur.unit_id LIMIT ?"""
        else:
            sql = f"""SELECT m.unit_id, bm25(context_units_fts) AS rank
                      FROM context_units_fts
                      JOIN context_units_fts_map m ON m.fts_rowid=context_units_fts.rowid
                      JOIN context_evidence_units u
                        ON u.generation_id=m.generation_id AND u.unit_id=m.unit_id
                      WHERE context_units_fts MATCH ? AND m.generation_id=?
                        AND u.kind=? AND u.lifecycle='active' {allowed_sql}
                      ORDER BY rank, m.unit_id LIMIT ?"""
        row_limit = (
            max(96, self.budget.per_pool * 32)
            if range_indexed else self.budget.per_pool
        )
        parameters = (generation_id, kind, *allowed_params, row_limit)
        # Most fact queries contain at least one discriminating entity/value.
        # Intersect terms first so FTS does not rank every row containing common
        # words.  Fall back to the recall-oriented union only when the precise
        # query has no result.
        if range_indexed:
            shortlist = max(96, self.budget.per_pool * 4)

            def execute(operator: str):
                return self.store._conn.execute(
                    sql,
                    (_fts_query(terms, operator=operator), shortlist, *parameters),
                ).fetchall()
        else:
            def execute(operator: str):
                return self.store._conn.execute(
                    sql, (_fts_query(terms, operator=operator), *parameters)
                ).fetchall()
        rows = execute("AND")
        if not rows and len(terms) > 1:
            rows = execute("OR")
        values: list[RetrievedCandidate] = []
        for row in rows:
            evidence = row if range_indexed else self.store._conn.execute(
                """SELECT r.source_id, r.part_id, r.start_offset, r.end_offset,
                          p.content_bytes
                   FROM context_unit_ranges ur
                   JOIN context_source_ranges r USING(range_id)
                   JOIN context_source_parts p
                     ON p.source_id=r.source_id AND p.part_id=r.part_id
                   WHERE ur.generation_id=? AND ur.unit_id=?
                   ORDER BY ur.ordinal LIMIT 1""",
                (generation_id, row["unit_id"]),
            ).fetchone()
            if evidence is None:
                continue
            body = bytes(evidence["content_bytes"])
            start, end = int(evidence["start_offset"]), int(evidence["end_offset"])
            values.append(RetrievedCandidate(
                unit_id=str(row["unit_id"]), kind=kind,
                source_id=str(evidence["source_id"]), part_id=str(evidence["part_id"]),
                start=start, end=end, text=body[start:end].decode("utf-8", errors="replace"),
                score=-float(row["rank"]), matched_obligation_ids=(),
            ))
        if not range_indexed:
            return values
        # Rank source episodes by complementary term coverage, then publish
        # the strongest exact range as the head. This lets several short,
        # adjacent statements jointly nominate the right episode without
        # concatenating or duplicating canonical source.
        by_source: dict[str, list[RetrievedCandidate]] = {}
        for item in values:
            by_source.setdefault(item.source_id, []).append(item)
        ranked_sources: list[RetrievedCandidate] = []
        query_terms = set(terms)
        for source_id, source_rows in by_source.items():
            covered = {
                term
                for item in source_rows
                for term in _fts_terms(item.text)
                if term in query_terms
            }
            head = max(
                source_rows,
                key=lambda item: (
                    len(query_terms & set(_fts_terms(item.text))),
                    item.score,
                    item.unit_id,
                ),
            )
            coverage = len(covered) / max(1, len(query_terms))
            ranked_sources.append(RetrievedCandidate(
                unit_id=head.unit_id, kind=head.kind,
                source_id=source_id, part_id=head.part_id,
                start=head.start, end=head.end, text=head.text,
                # BM25 remains the primary signal. Coverage is only a bounded
                # source-level bonus; multiplying it by a large constant made
                # long, generic episodes outrank an exact short answer.
                score=head.score + coverage * 5.0,
                matched_obligation_ids=(),
            ))
        return sorted(
            ranked_sources,
            key=lambda item: (-item.score, item.source_id, item.unit_id),
        )[: self.budget.per_pool]

    def _neighbors(
        self, generation_id: str, head: RetrievedCandidate, *, radius: int = 2,
    ) -> tuple[RetrievedCandidate, ...]:
        """Return exact adjacent raw-state ranges around a nominated head."""
        rows = self.store._conn.execute(
            """SELECT u.unit_id, r.part_id, r.start_offset, r.end_offset,
                      p.content_bytes
               FROM context_evidence_units u
               JOIN context_unit_views v
                 ON v.generation_id=u.generation_id AND v.unit_id=u.unit_id
               JOIN context_unit_ranges ur
                 ON ur.generation_id=u.generation_id AND ur.unit_id=u.unit_id
               JOIN context_source_ranges r USING(range_id)
               JOIN context_source_parts p
                 ON p.source_id=r.source_id AND p.part_id=r.part_id
               WHERE u.generation_id=? AND r.source_id=?
                 AND u.lifecycle='active' AND v.kind='raw_state'
               ORDER BY p.ordinal, r.start_offset, r.end_offset, u.unit_id""",
            (generation_id, head.source_id),
        ).fetchall()
        position = next(
            (index for index, row in enumerate(rows) if row["unit_id"] == head.unit_id),
            None,
        )
        if position is None:
            return ()
        values: list[RetrievedCandidate] = []
        start = max(0, position - radius)
        end = min(len(rows), position + radius + 1)
        for row in rows[start:end]:
            unit_id = str(row["unit_id"])
            if unit_id == head.unit_id:
                continue
            body = bytes(row["content_bytes"])
            range_start, range_end = int(row["start_offset"]), int(row["end_offset"])
            values.append(RetrievedCandidate(
                unit_id=unit_id, kind="raw_state", source_id=head.source_id,
                part_id=str(row["part_id"]), start=range_start, end=range_end,
                text=body[range_start:range_end].decode("utf-8", errors="replace"),
                score=head.score, matched_obligation_ids=(),
            ))
        return tuple(values)

    def retrieve(
        self, *, generation_id: str, query: str, plan: QueryPlan, max_sources: int,
        allowed_unit_ids: frozenset[str] | None = None,
    ) -> RetrievalResult:
        if max_sources <= 0:
            raise ValueError("max_sources must be positive")
        generation = self.store._conn.execute(
            "SELECT state, revision FROM context_view_generations WHERE generation_id=?",
            (generation_id,),
        ).fetchone()
        if generation is None or generation["state"] == "retired":
            raise RuntimeError("context generation is unavailable or retired")
        allowed_digest = hashlib.sha256(
            "\n".join(sorted(allowed_unit_ids or ())).encode()
        ).hexdigest()
        cache_key = (
            generation_id, str(generation["state"]), int(generation["revision"]),
            plan.query_sha256, plan.plan_id, max_sources, allowed_digest,
            self.budget.per_pool, self.budget.total_units,
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            self.cache_hits += 1
            return cached
        by_pool: dict[str, list[RetrievedCandidate]] = {}
        scanned = 0
        for pool in POOL_KINDS:
            if not plan.pool_queries.get(pool):
                continue
            rows = self._pool(generation_id, pool, query, allowed_unit_ids)
            by_pool[pool] = rows
            scanned += len(rows)
            if scanned >= self.budget.total_units:
                break
        selected: list[RetrievedCandidate] = []
        used_units: set[str] = set()
        used_sources: set[str] = set()
        for obligation in plan.obligations:
            preferred = {
                "comparison_side": ("entity", "fact", "raw_state"),
                "ordered_steps": ("procedure", "raw_state"),
                "before_action_after": ("transition", "raw_state"),
                "claim_support": ("gotcha", "fact", "raw_state"),
                "premise_check": ("premise", "raw_state"),
            }.get(obligation.kind, ("fact", "rule", "entity", "raw_state"))
            candidates = [item for pool in preferred for item in by_pool.get(pool, ())]
            if obligation.entity:
                entity = obligation.entity.casefold()
                candidates.sort(
                    key=lambda item: (entity not in item.text.casefold(), -item.score, item.source_id)
                )
            else:
                candidates.sort(key=lambda item: (-item.score, item.source_id))
            candidate = next(
                (
                    item for item in candidates
                    if item.unit_id not in used_units
                    and item.source_id not in used_sources
                ),
                None,
            )
            if candidate is None:
                continue
            selected.append(RetrievedCandidate(
                **{name: getattr(candidate, name) for name in (
                    "unit_id", "kind", "source_id", "part_id", "start", "end", "text", "score"
                )},
                matched_obligation_ids=(obligation.obligation_id,),
            ))
            used_units.add(candidate.unit_id)
            used_sources.add(candidate.source_id)
            if len(selected) >= max_sources:
                break
        if len(selected) < max_sources:
            remainder = sorted(
                (
                    item for rows in by_pool.values() for item in rows
                    if item.unit_id not in used_units
                    and item.source_id not in used_sources
                ),
                key=lambda item: (-item.score, item.source_id, item.unit_id),
            )
            for item in remainder:
                # The same source-backed unit may appear through several typed
                # views. Sorting materializes the remainder before selection,
                # so recheck here rather than relying only on the generator's
                # initial used-unit snapshot.
                if item.unit_id in used_units or item.source_id in used_sources:
                    continue
                selected.append(item)
                used_units.add(item.unit_id)
                used_sources.add(item.source_id)
                if len(selected) >= max_sources:
                    break
        # Evidence is often distributed across adjacent statements in one
        # immutable episode. Reserve nomination breadth first, then replace
        # the lowest-ranked tail with exact neighbours of the strongest heads.
        # Neighbours remain obligation-neutral: adjacency can improve evidence
        # coverage but cannot by itself satisfy a requirement.
        heads = tuple(selected[: max(1, min(4, len(selected)))])
        neighbors = [
            neighbor
            for head in heads
            for neighbor in self._neighbors(generation_id, head)
            if neighbor.unit_id not in used_units
        ]
        for neighbor in neighbors:
            if len(selected) < max_sources:
                selected.append(neighbor)
            elif selected:
                displaced = selected.pop()
                used_units.discard(displaced.unit_id)
                selected.append(neighbor)
            used_units.add(neighbor.unit_id)
        value = RetrievalResult(
            candidates=tuple(selected), searched_pools=tuple(by_pool), scanned_units=scanned,
            exhausted=scanned >= self.budget.total_units,
        )
        if len(self._cache) >= 256:
            self._cache.pop(next(iter(self._cache)))
        self._cache[cache_key] = value
        return value
