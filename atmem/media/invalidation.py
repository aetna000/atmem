"""Media invalidation registration for Spec 015 lifecycle ordering."""

from __future__ import annotations

from atmem.lifecycle.invalidation import InvalidationRegistry


def register_media_invalidation(registry: InvalidationRegistry, service, *, order: int = 40) -> None:
    def invalidate(subject_id: str, record_id: str):
        rows=service.store._conn.execute("SELECT artifact_id FROM governed_media_observations WHERE subject_id=? AND observation_id=?",(subject_id,record_id)).fetchall()
        receipts=[service.revoke(str(row["artifact_id"])) for row in rows]
        return {"verified": all(item["observations_tombstoned"] >= 0 for item in receipts),"receipts":receipts}
    registry.register("media",invalidate,order=order)
