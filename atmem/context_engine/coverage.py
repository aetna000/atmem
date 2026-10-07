"""Coverage and storage diagnostics for Context Engine V3."""

from __future__ import annotations

from typing import Any

from atmem.store.sqlite import SQLiteStore


def storage_report(store: SQLiteStore) -> dict[str, Any]:
    """Return logical byte accounting without decrypting or exporting content."""
    queries = {
        "canonical_source": "SELECT COALESCE(SUM(length(content_bytes)),0) FROM context_source_parts",
        "evidence_units": "SELECT COALESCE(SUM(length(compact_json)),0) FROM context_evidence_units",
        "links": "SELECT COALESCE(SUM(length(relation)),0) FROM context_evidence_links",
        "vectors": "SELECT COALESCE(SUM(length(vector_bytes)),0) FROM context_vectors",
        "coverage_loss": "SELECT COALESCE(SUM(length(COALESCE(reason_code,''))),0) FROM context_coverage",
    }
    categories = {
        name: int(store._conn.execute(sql).fetchone()[0])
        for name, sql in queries.items()
    }
    source = categories["canonical_source"]
    derived = sum(value for name, value in categories.items() if name != "canonical_source")
    # Compare a source part only with units that cite one of its ranges.  The
    # previous uncorrelated source-parts × evidence-units scan was quadratic
    # (and hex-encoded every encrypted source value), making the diagnostic
    # itself the dominant CPU load at realistic sizes.  Formation requires
    # every unit to carry a range, so this linked check is both stricter and
    # bounded by the number of unit/range edges.
    duplicate_rows = int(store._conn.execute(
        """SELECT COUNT(DISTINCT p.source_id || char(0) || p.part_id)
           FROM context_source_parts p
           JOIN context_source_ranges r
             ON r.source_id=p.source_id AND r.part_id=p.part_id
           JOIN context_unit_ranges ur ON ur.range_id=r.range_id
           JOIN context_evidence_units u
             ON u.generation_id=ur.generation_id AND u.unit_id=ur.unit_id
           WHERE length(p.content_bytes) > 0
             AND instr(CAST(u.compact_json AS TEXT),
                       CAST(p.content_bytes AS TEXT)) > 0"""
    ).fetchone()[0])
    return {
        "format": "atmem-context-storage-report-v1",
        "storage_ready": store.context_engine_storage_ready(),
        "bytes": categories,
        "derived_bytes": derived,
        "source_bytes": source,
        "derived_to_source_ratio": (derived / source) if source else 0.0,
        "source_duplication": {
            "duplicate_rows": duplicate_rows,
            "passed": duplicate_rows == 0,
        },
    }
