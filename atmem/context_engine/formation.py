"""Source-once formation and atomic derived-generation lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Literal
import uuid

from atmem.contracts.models import AuthorityScope
from atmem.core.canonical import canonical_json, sha256_hex
from atmem.store.sqlite import SQLiteStore, utc_now

from .contracts import EvidenceRange, FormationReceiptV2


PartKind = Literal["text", "image", "audio", "video", "file", "tool"]
UnitKind = Literal[
    "raw_state", "transition", "fact", "entity", "procedure", "rule", "gotcha", "premise"
]


def _digest(value: bytes | str) -> str:
    return "sha256:" + sha256_hex(value)


@dataclass(frozen=True, slots=True)
class SourcePart:
    part_id: str
    ordinal: int
    kind: PartKind
    mime_type: str
    content: bytes

    def __post_init__(self) -> None:
        if not self.part_id or self.ordinal < 0 or not self.mime_type or not self.content:
            raise ValueError("source part identity, order, MIME type and content are required")


@dataclass(frozen=True, slots=True)
class SourceEpisode:
    episode_id: str
    scope: AuthorityScope
    parts: tuple[SourcePart, ...]

    def __post_init__(self) -> None:
        if not self.episode_id or not self.parts:
            raise ValueError("source episode identity and parts are required")
        if len({part.part_id for part in self.parts}) != len(self.parts):
            raise ValueError("source part IDs must be unique")
        if tuple(part.ordinal for part in self.parts) != tuple(range(len(self.parts))):
            raise ValueError("source parts must have contiguous canonical ordering")


@dataclass(frozen=True, slots=True)
class StoredRange:
    range_id: str
    evidence: EvidenceRange


class FormationManager:
    """Own source retention and rebuildable V3 generation state.

    The manager intentionally stores original bytes in exactly one table. All
    derived rows carry stable range IDs and compact projections only.
    """

    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def retain_source(self, episode: SourceEpisode, *, legacy_episode_id: str | None = None) -> str:
        self.store.require_context_engine_storage()
        manifest = [
            {
                "part_id": part.part_id,
                "ordinal": part.ordinal,
                "kind": part.kind,
                "mime_type": part.mime_type,
                "content_sha256": _digest(part.content),
            }
            for part in episode.parts
        ]
        source_sha = _digest(canonical_json({
            "episode_id": episode.episode_id,
            "scope": episode.scope.to_dict(),
            "parts": manifest,
        }))
        source_id = "src3_" + sha256_hex(canonical_json({
            "episode_id": episode.episode_id,
            "scope": episode.scope.to_dict(),
        }))[:32]
        with self.store.transaction():
            current = self.store._conn.execute(
                "SELECT source_sha256 FROM context_source_episodes WHERE source_id=?",
                (source_id,),
            ).fetchone()
            if current is not None:
                if str(current["source_sha256"]) != source_sha:
                    raise ValueError("source episode identity was replayed with different bytes")
                return source_id
            self.store._conn.execute(
                """INSERT INTO context_source_episodes(
                     source_id, legacy_episode_id, subject_id, agent_id, workspace_id,
                     source_sha256, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    source_id, legacy_episode_id, episode.scope.subject_id,
                    episode.scope.agent_id, episode.scope.workspace_id, source_sha, utc_now(),
                ),
            )
            self.store._conn.executemany(
                """INSERT INTO context_source_parts(
                     source_id, part_id, ordinal, kind, mime_type, content_sha256, content_bytes
                   ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        source_id, part.part_id, part.ordinal, part.kind, part.mime_type,
                        _digest(part.content), part.content,
                    )
                    for part in episode.parts
                ],
            )
        return source_id

    def list_source_parts(self, source_id: str) -> tuple[SourcePart, ...]:
        rows = self.store._conn.execute(
            """SELECT part_id, ordinal, kind, mime_type, content_bytes
               FROM context_source_parts WHERE source_id=? ORDER BY ordinal""",
            (source_id,),
        ).fetchall()
        return tuple(
            SourcePart(
                part_id=str(row["part_id"]), ordinal=int(row["ordinal"]),
                kind=str(row["kind"]), mime_type=str(row["mime_type"]),
                content=bytes(row["content_bytes"]),
            )
            for row in rows
        )

    def add_range(self, source_id: str, part_id: str, start: int, end: int) -> StoredRange:
        row = self.store._conn.execute(
            """SELECT e.source_sha256, p.content_bytes
               FROM context_source_episodes e JOIN context_source_parts p USING(source_id)
               WHERE e.source_id=? AND p.part_id=?""",
            (source_id, part_id),
        ).fetchone()
        if row is None or start < 0 or end <= start or end > len(bytes(row["content_bytes"])):
            raise ValueError("source range is outside the retained source part")
        range_id = "range3_" + sha256_hex(
            canonical_json([source_id, part_id, start, end, row["source_sha256"]])
        )[:32]
        with self.store.transaction():
            self.store._conn.execute(
                """INSERT OR IGNORE INTO context_source_ranges(
                     range_id, source_id, part_id, start_offset, end_offset,
                     source_sha256, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (range_id, source_id, part_id, start, end, row["source_sha256"], utc_now()),
            )
        return StoredRange(
            range_id,
            EvidenceRange(
                source_id=source_id, part_id=part_id, start=start, end=end,
                source_sha256=str(row["source_sha256"]),
            ),
        )

    def begin_generation(
        self, scope: AuthorityScope, *, profile_id: str,
        canonical_generation: int = 0, configuration: dict[str, Any] | None = None,
    ) -> str:
        self.store.require_context_engine_storage()
        generation_id = "gen3_" + uuid.uuid4().hex
        configuration_sha = _digest(canonical_json(configuration or {}))
        with self.store.transaction():
            self.store._conn.execute(
                """INSERT INTO context_view_generations(
                     generation_id, subject_id, agent_id, workspace_id, profile_id,
                     state, canonical_generation, configuration_sha256, created_at
                   ) VALUES (?, ?, ?, ?, ?, 'building', ?, ?, ?)""",
                (
                    generation_id, scope.subject_id, scope.agent_id, scope.workspace_id,
                    profile_id, canonical_generation, configuration_sha, utc_now(),
                ),
            )
        return generation_id

    def add_unit(
        self, generation_id: str, *, kind: UnitKind, ranges: tuple[StoredRange, ...],
        compact_value: dict[str, Any], lifecycle: str = "active",
        search_text: str | None = None,
    ) -> str:
        if not ranges:
            raise ValueError("an evidence unit requires at least one source range")
        compact = canonical_json(compact_value)
        unit_id = "unit3_" + sha256_hex(canonical_json({
            "kind": kind, "ranges": [item.range_id for item in ranges],
            "compact_sha256": _digest(compact),
        }))[:32]
        with self.store.transaction():
            generation = self.store._conn.execute(
                "SELECT state FROM context_view_generations WHERE generation_id=?",
                (generation_id,),
            ).fetchone()
            if generation is None or generation["state"] != "building":
                raise RuntimeError("evidence units may only be added to a building generation")
            inserted = self.store._conn.execute(
                """INSERT OR IGNORE INTO context_evidence_units(
                     generation_id, unit_id, kind, compact_json, compact_sha256,
                     lifecycle, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (generation_id, unit_id, kind, compact, _digest(compact), lifecycle, utc_now()),
            )
            self.store._conn.executemany(
                """INSERT OR IGNORE INTO context_unit_ranges(
                     generation_id, unit_id, range_id, ordinal
                   ) VALUES (?, ?, ?, ?)""",
                [
                    (generation_id, unit_id, item.range_id, ordinal)
                    for ordinal, item in enumerate(ranges)
                ],
            )
            self.store._conn.executemany(
                """INSERT OR REPLACE INTO context_coverage(
                     generation_id, range_id, disposition, reason_code
                   ) VALUES (?, ?, 'represented', NULL)""",
                [(generation_id, item.range_id) for item in ranges],
            )
            self.store.index_context_unit(generation_id, unit_id, search_text or compact)
            if inserted.rowcount:
                self.store._conn.execute(
                    "UPDATE context_view_generations SET revision=revision+1 WHERE generation_id=?",
                    (generation_id,),
                )
        return unit_id

    def form_source(self, source_id: str, generation_id: str) -> FormationReceiptV2:
        """Create deterministic additive views while preserving full source coverage."""
        generation = self.store._conn.execute(
            "SELECT state FROM context_view_generations WHERE generation_id=?",
            (generation_id,),
        ).fetchone()
        if generation is None or generation["state"] != "building":
            raise RuntimeError("formation requires a building generation")
        represented: list[EvidenceRange] = []
        units_before = int(self.store._conn.execute(
            "SELECT COUNT(*) FROM context_evidence_units WHERE generation_id=?",
            (generation_id,),
        ).fetchone()[0])
        for part in self.list_source_parts(source_id):
            source_range = self.add_range(source_id, part.part_id, 0, len(part.content))
            represented.append(source_range.evidence)
            text = part.content.decode("utf-8", errors="replace")
            lowered = text.casefold()
            base = {
                "source_id": source_id,
                "part_id": part.part_id,
                "modality": part.kind,
                "mime_type": part.mime_type,
            }
            kinds: set[UnitKind] = {"raw_state"}
            if part.kind == "text":
                kinds.update(("fact", "entity"))
                if re.search(r"\b(before|after|changed|replacing|restored|now)\b", lowered):
                    kinds.add("transition")
                if re.search(r"\b(in order|step|first|then|finally|restore)\b", lowered):
                    kinds.add("procedure")
                if re.search(r"\b(must|required|should|never|always)\b", lowered):
                    kinds.add("rule")
                if re.search(r"\b(gotcha|failed|failure|error|zero records|doing nothing)\b", lowered):
                    kinds.add("gotcha")
                if re.search(r"\b(no|not|never|only|without|cannot|can't)\b", lowered):
                    kinds.add("premise")
            entities = sorted(set(re.findall(r"\b[A-Z][A-Za-z0-9_-]*\b", text)))[:32]
            for kind in sorted(kinds):
                compact = {
                    **base,
                    "view": kind,
                    "entities": entities if kind == "entity" else [],
                    "polarity": "negative" if kind == "premise" else "unknown",
                }
                self.add_unit(
                    generation_id,
                    kind=kind,
                    ranges=(source_range,),
                    compact_value=compact,
                    search_text=text,
                )
        units_after = int(self.store._conn.execute(
            "SELECT COUNT(*) FROM context_evidence_units WHERE generation_id=?",
            (generation_id,),
        ).fetchone()[0])
        coverage = self.coverage_report(generation_id)
        formation_id = "formation3_" + sha256_hex(
            canonical_json([source_id, generation_id, "deterministic-formation-v1"])
        )[:32]
        return FormationReceiptV2(
            formation_id=formation_id,
            episode_id=source_id,
            generation_id=generation_id,
            source_generation=0,
            producer_id="deterministic-formation-v1",
            represented_ranges=tuple(represented),
            loss_ranges=(),
            units_created=units_after - units_before,
            units_reconciled=units_before if units_after == units_before else 0,
            units_rejected=0,
            storage_bytes_by_category={
                "source": self.store.context_source_storage(source_id)["source_body_bytes"],
                "derived": int(coverage["derived_bytes"]),
            },
            processing_complete=True,
            representation_complete=coverage["coverage_ratio"] == 1.0,
        )

    def coverage_report(self, generation_id: str) -> dict[str, Any]:
        total = int(self.store._conn.execute(
            """SELECT COUNT(*) FROM context_source_parts p
               JOIN context_source_episodes e USING(source_id)
               JOIN context_view_generations g
                 ON g.subject_id=e.subject_id AND g.workspace_id=e.workspace_id
                AND g.agent_id=e.agent_id
               WHERE g.generation_id=?""",
            (generation_id,),
        ).fetchone()[0])
        represented = int(self.store._conn.execute(
            """SELECT COUNT(DISTINCT r.source_id || ':' || r.part_id)
               FROM context_coverage c JOIN context_source_ranges r USING(range_id)
               WHERE c.generation_id=? AND c.disposition='represented'""",
            (generation_id,),
        ).fetchone()[0])
        derived_bytes = int(self.store._conn.execute(
            "SELECT COALESCE(SUM(length(compact_json)),0) FROM context_evidence_units WHERE generation_id=?",
            (generation_id,),
        ).fetchone()[0])
        return {
            "total_parts": total,
            "represented_parts": represented,
            "coverage_ratio": represented / total if total else 1.0,
            "derived_bytes": derived_bytes,
        }

    def get_unit(self, unit_id: str, *, generation_id: str | None = None) -> dict[str, Any]:
        params: tuple[str, ...]
        where = "u.unit_id=?"
        params = (unit_id,)
        if generation_id is not None:
            where += " AND u.generation_id=?"
            params = (unit_id, generation_id)
        row = self.store._conn.execute(
            f"SELECT u.* FROM context_evidence_units u WHERE {where} ORDER BY u.created_at DESC LIMIT 1",
            params,
        ).fetchone()
        if row is None:
            raise KeyError(unit_id)
        ranges = self.store._conn.execute(
            """SELECT r.* FROM context_unit_ranges ur
               JOIN context_source_ranges r USING(range_id)
               WHERE ur.generation_id=? AND ur.unit_id=? ORDER BY ur.ordinal""",
            (row["generation_id"], unit_id),
        ).fetchall()
        value = dict(row)
        value["compact"] = json.loads(value.pop("compact_json"))
        value["ranges"] = [dict(item) for item in ranges]
        return value

    def verify_generation(self, generation_id: str) -> dict[str, Any]:
        with self.store.transaction():
            row = self.store._conn.execute(
                "SELECT state FROM context_view_generations WHERE generation_id=?",
                (generation_id,),
            ).fetchone()
            if row is None or row["state"] != "building":
                raise RuntimeError("only a building generation can be verified")
            orphan = self.store._conn.execute(
                """SELECT COUNT(*) AS n FROM context_evidence_units u
                   WHERE u.generation_id=? AND NOT EXISTS (
                     SELECT 1 FROM context_unit_ranges r
                     WHERE r.generation_id=u.generation_id AND r.unit_id=u.unit_id
                   )""",
                (generation_id,),
            ).fetchone()
            report = {"orphan_units": int(orphan["n"]), "verified": int(orphan["n"]) == 0}
            if not report["verified"]:
                raise RuntimeError("generation verification found source-less evidence units")
            self.store._conn.execute(
                """UPDATE context_view_generations SET state='verified',
                   verification_json=?, verified_at=? WHERE generation_id=?""",
                (canonical_json(report), utc_now(), generation_id),
            )
        return report

    def activate_generation(self, generation_id: str) -> None:
        self.store.require_context_engine_storage()
        with self.store.transaction():
            row = self.store._conn.execute(
                "SELECT * FROM context_view_generations WHERE generation_id=?",
                (generation_id,),
            ).fetchone()
            if row is None or row["state"] != "verified":
                raise RuntimeError("generation must be verified before activation")
            now = utc_now()
            self.store._conn.execute(
                """UPDATE context_view_generations SET state='retired', retired_at=?
                   WHERE subject_id=? AND workspace_id=? AND agent_id=? AND state='active'""",
                (now, row["subject_id"], row["workspace_id"], row["agent_id"]),
            )
            self.store._conn.execute(
                """UPDATE context_view_generations SET state='active', activated_at=?
                   WHERE generation_id=?""",
                (now, generation_id),
            )

    def active_generation(self, scope: AuthorityScope) -> dict[str, Any] | None:
        row = self.store._conn.execute(
            """SELECT * FROM context_view_generations
               WHERE subject_id=? AND workspace_id=? AND agent_id=? AND state='active'""",
            (scope.subject_id, scope.workspace_id, scope.agent_id),
        ).fetchone()
        return dict(row) if row else None

    def retire_generation(self, generation_id: str) -> None:
        with self.store.transaction():
            changed = self.store._conn.execute(
                """UPDATE context_view_generations SET state='retired', retired_at=?
                   WHERE generation_id=? AND state IN ('verified','active')""",
                (utc_now(), generation_id),
            ).rowcount
            if not changed:
                raise RuntimeError("only a verified or active generation can be retired")

    def discard_generation(self, generation_id: str) -> None:
        with self.store.transaction():
            row = self.store._conn.execute(
                "SELECT state FROM context_view_generations WHERE generation_id=?",
                (generation_id,),
            ).fetchone()
            if row is None:
                return
            if row["state"] == "active":
                raise RuntimeError("active generation must be retired before deletion")
            self.store._delete_context_fts_generation(generation_id)
            self.store._conn.execute(
                "DELETE FROM context_view_generations WHERE generation_id=?",
                (generation_id,),
            )

    def rebuild_generation(self, generation_id: str) -> str:
        """Rebuild one inactive generation from retained range-linked projections.

        This is a deterministic, source-linked rebuild: compact unit identities
        and range identities remain stable, while the generation identity is
        new and inactive until independently verified and activated.
        """
        source = self.store._conn.execute(
            "SELECT * FROM context_view_generations WHERE generation_id=?",
            (generation_id,),
        ).fetchone()
        if source is None:
            raise KeyError(generation_id)
        rebuilt = "gen3_" + uuid.uuid4().hex
        with self.store.transaction():
            self.store._conn.execute(
                """INSERT INTO context_view_generations(
                     generation_id, subject_id, agent_id, workspace_id, profile_id,
                     state, canonical_generation, configuration_sha256, created_at
                   ) VALUES (?, ?, ?, ?, ?, 'building', ?, ?, ?)""",
                (
                    rebuilt, source["subject_id"], source["agent_id"],
                    source["workspace_id"], source["profile_id"],
                    source["canonical_generation"], source["configuration_sha256"], utc_now(),
                ),
            )
            self.store._conn.execute(
                """INSERT INTO context_evidence_units(
                     generation_id, unit_id, kind, compact_json, compact_sha256,
                     lifecycle, created_at
                   ) SELECT ?, unit_id, kind, compact_json, compact_sha256,
                            lifecycle, ? FROM context_evidence_units
                     WHERE generation_id=?""",
                (rebuilt, utc_now(), generation_id),
            )
            self.store._conn.execute(
                """INSERT INTO context_unit_ranges(generation_id, unit_id, range_id, ordinal)
                   SELECT ?, unit_id, range_id, ordinal FROM context_unit_ranges
                   WHERE generation_id=?""",
                (rebuilt, generation_id),
            )
            self.store._conn.execute(
                """INSERT INTO context_evidence_links(
                     generation_id, from_unit_id, to_unit_id, relation
                   ) SELECT ?, from_unit_id, to_unit_id, relation
                     FROM context_evidence_links WHERE generation_id=?""",
                (rebuilt, generation_id),
            )
            self.store._conn.execute(
                """INSERT INTO context_coverage(generation_id, range_id, disposition, reason_code)
                   SELECT ?, range_id, disposition, reason_code FROM context_coverage
                   WHERE generation_id=?""",
                (rebuilt, generation_id),
            )
            self.store._conn.execute(
                """INSERT INTO context_loss_receipts(
                     generation_id, range_id, reason_code, detail_json, created_at
                   ) SELECT ?, range_id, reason_code, detail_json, ?
                     FROM context_loss_receipts WHERE generation_id=?""",
                (rebuilt, utc_now(), generation_id),
            )
            rows = self.store._conn.execute(
                "SELECT unit_id, compact_json FROM context_evidence_units WHERE generation_id=?",
                (rebuilt,),
            ).fetchall()
            for row in rows:
                self.store.index_context_unit(rebuilt, str(row["unit_id"]), str(row["compact_json"]))
        return rebuilt

    def backfill_legacy_sources(self, scope: AuthorityScope, *, limit: int = 100) -> dict[str, Any]:
        self.store.require_context_engine_storage()
        state = self.store._conn.execute(
            """SELECT cursor_episode_id FROM context_backfill_state
               WHERE subject_id=? AND workspace_id=? AND agent_id=?""",
            (scope.subject_id, scope.workspace_id, scope.agent_id),
        ).fetchone()
        cursor = str(state["cursor_episode_id"] or "") if state else ""
        rows = self.store._conn.execute(
            """SELECT id, message FROM episodes WHERE subject_id=? AND id>?
               ORDER BY id LIMIT ?""",
            (scope.subject_id, cursor, limit),
        ).fetchall()
        for row in rows:
            self.retain_source(
                SourceEpisode(
                    episode_id=str(row["id"]), scope=scope,
                    parts=(SourcePart("text", 0, "text", "text/plain", str(row["message"]).encode()),),
                ),
                legacy_episode_id=str(row["id"]),
            )
        next_cursor = str(rows[-1]["id"]) if rows else cursor
        with self.store.transaction():
            self.store._conn.execute(
                """INSERT INTO context_backfill_state(
                     subject_id, workspace_id, agent_id, cursor_episode_id, completed, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(subject_id, workspace_id, agent_id) DO UPDATE SET
                     cursor_episode_id=excluded.cursor_episode_id,
                     completed=excluded.completed, updated_at=excluded.updated_at""",
                (
                    scope.subject_id, scope.workspace_id, scope.agent_id, next_cursor,
                    int(len(rows) < limit), utc_now(),
                ),
            )
        return {"processed": len(rows), "cursor_episode_id": next_cursor, "complete": len(rows) < limit}

    def delete_source(self, source_id: str) -> dict[str, Any]:
        """Delete canonical V3 source and invalidate every dependent generation."""
        source = self.store._conn.execute(
            "SELECT subject_id FROM context_source_episodes WHERE source_id=?",
            (source_id,),
        ).fetchone()
        if source is None:
            return {"deleted": False, "source_id": source_id, "invalidated_generations": ()}
        generations = tuple(
            str(row["generation_id"])
            for row in self.store._conn.execute(
                """SELECT DISTINCT ur.generation_id
                   FROM context_unit_ranges ur
                   JOIN context_source_ranges r USING(range_id)
                   WHERE r.source_id=? ORDER BY ur.generation_id""",
                (source_id,),
            ).fetchall()
        )
        with self.store.transaction():
            for generation_id in generations:
                self.store._delete_context_fts_generation(generation_id)
                self.store._conn.execute(
                    "DELETE FROM context_view_generations WHERE generation_id=?",
                    (generation_id,),
                )
            self.store._conn.execute(
                "DELETE FROM context_source_episodes WHERE source_id=?", (source_id,)
            )
        return {
            "deleted": True,
            "source_id": source_id,
            "invalidated_generations": generations,
        }
