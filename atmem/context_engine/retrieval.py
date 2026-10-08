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
    "our", "its", "please", "send", "post", "inspect", "review", "comment",
    "find", "update", "short", "concise", "note", "document", "reference", "include",
    "state", "briefly", "actual", "another", "current", "earlier", "conversation",
    "would", "like", "user", "perform", "conclude", "task",
}


def _fts_terms(value: str) -> tuple[str, ...]:
    value = re.sub(r"^\s*\[\d{4}-\d{2}-\d{2}\]\s*", "", value)
    aliases = {
        "creating": "create", "created": "create", "creates": "create",
        "problems": "problem", "requests": "request", "fields": "field",
        "actions": "action", "steps": "step", "orders": "order",
    }
    terms = [
        aliases.get(token.casefold(), token.casefold())
        for token in re.findall(r"[^\W_]+", value, re.UNICODE)
        if token.casefold() not in _STOP and len(token) > 1
    ]
    return tuple(dict.fromkeys(terms))


def _fts_query(terms: tuple[str, ...], *, operator: str) -> str:
    if operator not in {"AND", "OR"}:
        raise ValueError("unsupported FTS operator")
    return f" {operator} ".join(
        f'"{term.replace(chr(34), chr(34) * 2)}"' for term in terms
    )


def _option_fields(query: str) -> tuple[str, ...]:
    fields: list[str] = []
    for line in re.findall(r"(?m)^\s*[A-Z]\s*[.)]\s*([^\n]+)$", query):
        fields.extend(
            " ".join(item.split()).strip(" ,.;")
            for item in re.split(r"\s*,\s*|\s*/\s*", line)
        )
    return tuple(dict.fromkeys(item for item in fields if len(item) > 1))


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
    withheld_obligation_ids: tuple[str, ...] = ()


class DeterministicRetriever:
    def __init__(self, store: SQLiteStore, *, budget: PoolBudget | None = None) -> None:
        self.store = store
        self.budget = budget or PoolBudget()
        self._cache: dict[tuple[object, ...], RetrievalResult] = {}
        self.cache_hits = 0

    def _pool(
        self, generation_id: str, kind: str, query: str,
        allowed_unit_ids: frozenset[str] | None = None,
        result_limit: int | None = None,
    ) -> list[RetrievedCandidate]:
        limit = result_limit or self.budget.per_pool
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
            max(32, limit * 32)
            if range_indexed else limit
        )
        parameters = (generation_id, kind, *allowed_params, row_limit)
        # Most fact queries contain at least one discriminating entity/value.
        # Intersect terms first so FTS does not rank every row containing common
        # words.  Fall back to the recall-oriented union only when the precise
        # query has no result.
        if range_indexed:
            # The range shortlist must be wider than the final source limit:
            # a repetitive form can contribute dozens of top BM25 ranges and
            # otherwise crowd every other source out before source-level
            # diversity is applied.
            shortlist = max(128, limit * 16)

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
        workflow_target = (
            next((term for term in terms if term != "create"), None)
            if "create" in terms else None
        )
        for source_id, source_rows in by_source.items():
            covered = {
                term
                for item in source_rows
                for term in _fts_terms(item.text)
                if term in query_terms
            }
            def workflow_match(item: RetrievedCandidate) -> bool:
                return bool(
                    workflow_target
                    and re.search(
                        rf"\bcreat(?:e|es|ed|ing)\b.{{0,32}}"
                        rf"\b{re.escape(workflow_target)}s?\b",
                        item.text,
                        re.IGNORECASE | re.DOTALL,
                    )
                )

            head = max(
                source_rows,
                key=lambda item: (
                    workflow_match(item),
                    workflow_match(item) and item.part_id == "trajectory-metadata",
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
        )[:limit]

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
        by_pool_query: dict[tuple[str, str], list[RetrievedCandidate]] = {}
        scanned = 0
        option_comparison_query = "which option" in query.casefold()
        for pool in POOL_KINDS:
            queries = plan.pool_queries.get(pool) or ()
            if not queries:
                continue
            merged: dict[str, RetrievedCandidate] = {}
            for pool_query in queries:
                if scanned >= self.budget.total_units:
                    break
                rows = self._pool(
                    generation_id, pool, pool_query, allowed_unit_ids,
                    result_limit=(
                        min(8, self.budget.per_pool)
                        if option_comparison_query
                        and pool_query != query
                        and len(_fts_terms(pool_query)) <= 6
                        else None
                    ),
                )
                by_pool_query[(pool, pool_query)] = rows
                scanned += len(rows)
                for item in rows:
                    prior = merged.get(item.unit_id)
                    if prior is None or item.score > prior.score:
                        merged[item.unit_id] = item
            by_pool[pool] = sorted(
                merged.values(),
                key=lambda item: (-item.score, item.source_id, item.unit_id),
            )
            if scanned >= self.budget.total_units:
                break
        selected: list[RetrievedCandidate] = []
        used_units: set[str] = set()
        used_sources: set[str] = set()
        supplemental_priority_units: set[str] = set()
        supplemental_intent_sources: set[str] = set()
        supplemental_query_hits: dict[str, set[str]] = {}
        for obligation in plan.obligations:
            preferred = {
                "comparison_side": ("entity", "fact", "raw_state"),
                "ordered_steps": ("procedure", "raw_state"),
                "before_action_after": ("transition", "raw_state"),
                "claim_support": ("gotcha", "fact", "raw_state"),
                "premise_check": ("premise", "raw_state"),
            }.get(obligation.kind, ("fact", "rule", "entity", "raw_state"))
            obligation_query = obligation.relation_or_action or query
            # Exact obligation queries remain eligible, but compact answer-
            # blind facets must also be able to ground an obligation. Earlier,
            # a useful facet could only fill a supplemental slot whenever the
            # verbose original query returned any noisy result.
            facet_hits: dict[str, set[str]] = {}
            intent_units: set[str] = set()
            for pool in preferred:
                for pool_query in plan.pool_queries.get(pool) or ():
                    for item in by_pool_query.get((pool, pool_query), ()):
                        facet_hits.setdefault(item.source_id, set()).add(pool_query)
                        facet_terms = _fts_terms(pool_query)
                        intent_match = re.fullmatch(
                            r"\s*create\s+([A-Za-z0-9_-]+)\s*",
                            pool_query,
                            re.IGNORECASE,
                        )
                        intent_tail = (
                            intent_match.group(1).casefold() if intent_match else None
                        )
                        if (
                            len(facet_terms) <= 4
                            and intent_tail is not None
                            and re.search(
                                rf"\bcreat(?:e|es|ed|ing)\b.{{0,32}}\b{re.escape(intent_tail)}s?\b",
                                item.text,
                                re.IGNORECASE | re.DOTALL,
                            )
                        ):
                            intent_units.add(item.unit_id)
            option_comparison = option_comparison_query
            supplemental_priority_units.update(intent_units)
            intent_items = [
                item
                for rows in by_pool_query.values()
                for item in rows
                if item.unit_id in intent_units
            ]
            # Prefer trajectories whose compact metadata states the requested
            # workflow. A UI state can mention “create problem” incidentally
            # (history, navigation, help text); treating every such source as
            # the same intent bucket reintroduces unrelated long states ahead
            # of the actual workflow evidence.
            metadata_intent_sources = {
                item.source_id
                for item in intent_items
                if item.part_id == "trajectory-metadata"
            }
            supplemental_intent_sources.update(
                metadata_intent_sources
                or {item.source_id for item in intent_items}
            )
            if option_comparison:
                for (_pool_name, pool_query), rows in by_pool_query.items():
                    for item in rows:
                        supplemental_query_hits.setdefault(item.unit_id, set()).add(
                            pool_query
                        )
            def intent_priority(item: RetrievedCandidate) -> int:
                if not intent_units:
                    return 0
                if item.unit_id in intent_units and item.part_id == "trajectory-metadata":
                    return 0
                if item.unit_id in intent_units:
                    return 1
                return 2

            candidates_by_unit: dict[
                str, tuple[tuple[int, int, int, int, float], RetrievedCandidate]
            ] = {}
            for pool_index, pool in enumerate(preferred):
                queries = plan.pool_queries.get(pool) or (obligation_query,)
                ordered_queries = (
                    sorted(queries, key=lambda value: (len(_fts_terms(value)), value))
                    if obligation.kind == "ordered_steps" else queries
                )
                for query_index, pool_query in enumerate(ordered_queries):
                    for item in by_pool_query.get((pool, pool_query), ()):
                        priority = (
                            intent_priority(item),
                            -len(facet_hits.get(item.source_id, ()))
                            if option_comparison else 0,
                            query_index, pool_index, -item.score,
                        )
                        prior = candidates_by_unit.get(item.unit_id)
                        if prior is None or priority < prior[0]:
                            candidates_by_unit[item.unit_id] = (priority, item)
                for item in by_pool.get(pool, ()):
                    priority = (
                        intent_priority(item),
                        -len(facet_hits.get(item.source_id, ()))
                        if option_comparison else 0,
                        len(ordered_queries), pool_index, -item.score,
                    )
                    prior = candidates_by_unit.get(item.unit_id)
                    if prior is None or priority < prior[0]:
                        candidates_by_unit[item.unit_id] = (priority, item)
            prioritized = sorted(candidates_by_unit.values(), key=lambda value: value[0])
            candidates = [item for _, item in prioritized]
            need_terms = set(_fts_terms(" ".join(filter(None, (
                obligation.entity, obligation.relation_or_action,
            )))))

            def grounded(item: RetrievedCandidate) -> bool:
                overlap = need_terms & set(_fts_terms(item.text))
                if obligation.kind == "comparison_side":
                    return bool(
                        obligation.entity
                        and obligation.entity.casefold() in item.text.casefold()
                    )
                if obligation.kind in {"claim_support", "premise_check"}:
                    return bool(overlap)
                return bool(overlap) and (
                    len(overlap) >= 2
                    or len(overlap) / max(1, len(need_terms)) >= 0.20
                )

            if option_comparison:
                pass
            elif obligation.entity:
                entity = obligation.entity.casefold()
                candidates.sort(
                    key=lambda item: (entity not in item.text.casefold(), -item.score, item.source_id)
                )
            elif obligation.kind != "ordered_steps":
                candidates.sort(key=lambda item: (-item.score, item.source_id))
            candidate = next(
                (
                    item for item in candidates
                    if item.unit_id not in used_units
                    and item.source_id not in used_sources
                    and grounded(item)
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
        # Multiple-choice field questions need one precise nomination per
        # explicit field, not merely the ranges that happen to mention the
        # largest number of option words. Keep those nominations constrained
        # to the answer-blind workflow-intent sources when such sources exist.
        # This preserves evidence for rare fields (for example Subcategory)
        # without importing similarly named fields from unrelated forms.
        if option_comparison_query and len(selected) < max_sources:
            for field in _option_fields(query):
                rows = [
                    item
                    for pool in ("fact", "entity", "raw_state")
                    for item in by_pool_query.get((pool, field), ())
                    if item.unit_id not in used_units
                ]
                if supplemental_intent_sources:
                    rows = [
                        item for item in rows
                        if item.source_id in supplemental_intent_sources
                    ]
                if not rows:
                    continue
                candidate = min(
                    rows,
                    key=lambda item: (
                        len(item.text.encode("utf-8")),
                        -item.score,
                        item.source_id,
                        item.unit_id,
                    ),
                )
                selected.append(candidate)
                used_units.add(candidate.unit_id)
                used_sources.add(candidate.source_id)
                supplemental_priority_units.add(candidate.unit_id)
                if len(selected) >= max_sources:
                    break
        if len(selected) < max_sources:
            remainder = sorted(
                (
                    item
                    for rows in (*by_pool.values(), *by_pool_query.values())
                    for item in rows
                    if item.unit_id not in used_units
                    and (
                        option_comparison_query
                        or item.source_id not in used_sources
                    )
                ),
                key=lambda item: (
                    item.source_id not in supplemental_intent_sources,
                    item.unit_id not in supplemental_priority_units,
                    item.part_id != "trajectory-metadata",
                    -len(supplemental_query_hits.get(item.unit_id, ())),
                    -item.score, item.source_id, item.unit_id,
                ),
            )
            for item in remainder:
                # The same source-backed unit may appear through several typed
                # views. Sorting materializes the remainder before selection,
                # so recheck here rather than relying only on the generator's
                # initial used-unit snapshot.
                if item.unit_id in used_units or (
                    not option_comparison_query and item.source_id in used_sources
                ):
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
        ordered_step_ids = {
            item.obligation_id for item in plan.obligations
            if item.kind == "ordered_steps"
        }
        neighbors = [
            neighbor
            for head in heads
            for neighbor in self._neighbors(
                generation_id,
                head,
                radius=(
                    12 if set(head.matched_obligation_ids) & ordered_step_ids else 2
                ),
            )
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
        selected_sources = {item.source_id for item in selected}
        withheld_sources: set[str] = set()
        if selected_sources:
            placeholders = ",".join("?" for _ in selected_sources)
            withheld_sources = {
                str(row["source_id"])
                for row in self.store._conn.execute(
                    f"""SELECT DISTINCT r.source_id
                         FROM context_coverage c
                         JOIN context_source_ranges r USING(range_id)
                         WHERE c.generation_id=? AND c.disposition='withheld'
                           AND r.source_id IN ({placeholders})""",
                    (generation_id, *sorted(selected_sources)),
                ).fetchall()
            }
        withheld_obligations: tuple[str, ...] = ()
        incomplete_rows = self.store._conn.execute(
            """SELECT DISTINCT missing_range.source_id,
                              missing_range.start_offset,
                              missing_range.end_offset,
                              p.content_bytes
               FROM context_coverage missing
               JOIN context_source_ranges missing_range
                 ON missing_range.range_id=missing.range_id
               JOIN context_source_parts p
                 ON p.source_id=missing_range.source_id
                AND p.part_id=missing_range.part_id
               WHERE missing.generation_id=? AND missing.disposition='withheld'
               ORDER BY missing_range.source_id, missing_range.start_offset LIMIT 256""",
            (generation_id,),
        ).fetchall()
        incomplete_source_terms: dict[str, set[str]] = {}
        for row in incomplete_rows:
            body = bytes(row["content_bytes"])
            start, end = int(row["start_offset"]), int(row["end_offset"])
            incomplete_source_terms.setdefault(str(row["source_id"]), set()).update(
                _fts_terms(body[start:end].decode("utf-8", errors="replace"))
            )
        active_context_rows = self.store._conn.execute(
            """SELECT DISTINCT missing_range.source_id, r.start_offset,
                              r.end_offset, p.content_bytes
               FROM context_coverage missing
               JOIN context_source_ranges missing_range
                 ON missing_range.range_id=missing.range_id
               JOIN context_source_ranges r
                 ON r.source_id=missing_range.source_id
               JOIN context_coverage active
                 ON active.generation_id=missing.generation_id
                AND active.range_id=r.range_id
               JOIN context_source_parts p
                 ON p.source_id=r.source_id AND p.part_id=r.part_id
               WHERE missing.generation_id=? AND missing.disposition='withheld'
                 AND active.disposition='represented'
               ORDER BY missing_range.source_id, r.start_offset LIMIT 512""",
            (generation_id,),
        ).fetchall()
        active_source_terms: dict[str, set[str]] = {}
        for row in active_context_rows:
            body = bytes(row["content_bytes"])
            start, end = int(row["start_offset"]), int(row["end_offset"])
            active_source_terms.setdefault(str(row["source_id"]), set()).update(
                _fts_terms(body[start:end].decode("utf-8", errors="replace"))
            )
        if withheld_sources or incomplete_source_terms:
            values: list[str] = []
            query_terms = set(_fts_terms(query))
            for obligation in plan.obligations:
                terms = set(_fts_terms(" ".join(filter(None, (
                    obligation.entity, obligation.relation_or_action,
                )))))
                relevant_incomplete_source = any(
                    item.source_id in withheld_sources
                    and bool(terms & set(_fts_terms(item.text)))
                    for item in selected
                )
                incomplete_overlap = max(
                    (len(terms & source_terms) for source_terms in incomplete_source_terms.values()),
                    default=0,
                )
                query_overlap = max(
                    (
                        len(query_terms & source_terms)
                        for source_terms in incomplete_source_terms.values()
                    ),
                    default=0,
                )
                active_source_overlap = max(
                    (
                        len(query_terms & source_terms)
                        for source_terms in active_source_terms.values()
                    ),
                    default=0,
                )
                if (
                    relevant_incomplete_source
                    or incomplete_overlap >= max(1, min(2, len(terms)))
                    or query_overlap >= max(1, min(2, len(query_terms)))
                    or active_source_overlap >= max(1, min(2, len(query_terms)))
                ):
                    values.append(obligation.obligation_id)
            withheld_obligations = tuple(values)
        value = RetrievalResult(
            candidates=tuple(selected), searched_pools=tuple(by_pool), scanned_units=scanned,
            exhausted=scanned >= self.budget.total_units,
            withheld_obligation_ids=withheld_obligations,
        )
        if len(self._cache) >= 256:
            self._cache.pop(next(iter(self._cache)))
        self._cache[cache_key] = value
        return value
