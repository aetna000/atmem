"""Freeze a complete adjudicated AtMem SQLite/vector baseline."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
from typing import Any

from atmem import Memory
from atmem.core.canonical import canonical_json
from atmem.semantic import SemanticIndex, SentenceTransformersEmbedder, default_index_path


FORMAT = "atmem-stateful-memory-snapshot-v2"
DEFAULT_EMBEDDER = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def _sha(value: Any) -> str:
    return _sha_bytes(canonical_json(value).encode("utf-8"))


def _integrity(path: Path) -> None:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        result = connection.execute("PRAGMA quick_check").fetchone()[0]
    finally:
        connection.close()
    if result != "ok":
        raise RuntimeError(f"SQLite integrity failed for {path}: {result}")


def _adjudication_manifest(work_db: Path) -> dict[str, Any]:
    connection = sqlite3.connect(f"file:{work_db}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        counts = dict(connection.execute(
            "SELECT status,COUNT(*) FROM baseline_observation GROUP BY status"
        ).fetchall())
        total = sum(counts.values())
        receipts = [dict(row) for row in connection.execute(
            """SELECT observation_id,expected_operation,expected_target_id,
                      pre_state_digest,post_state_digest,judge,judge_revision,
                      receipt_digest,accepted
               FROM baseline_adjudication ORDER BY observation_id"""
        )]
        judgments = connection.execute(
            "SELECT judge,pass_kind,COUNT(*) FROM baseline_judgment GROUP BY judge,pass_kind ORDER BY judge,pass_kind"
        ).fetchall()
    finally:
        connection.close()
    if total < 1 or counts.get("awaiting_adjudication", 0) != 0 or len(receipts) != total:
        raise RuntimeError("baseline adjudication is incomplete")
    return {
        "observation_counts": counts, "adjudication_count": len(receipts),
        "accepted_count": sum(int(row["accepted"]) for row in receipts),
        "rejected_count": sum(not int(row["accepted"]) for row in receipts),
        "judgment_counts": [list(row) for row in judgments],
        "adjudication_set_digest": _sha(receipts),
    }


def _split_scope_manifest(work_db: Path) -> dict[str, Any]:
    """Prove that a scope and its baseline prefix belong to one split family."""

    connection = sqlite3.connect(f"file:{work_db}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        conflicts = [dict(row) for row in connection.execute(
            """SELECT scope_id,COUNT(DISTINCT split_family) AS family_count
                 FROM scale_group GROUP BY scope_id
               HAVING COUNT(DISTINCT split_family) != 1
               ORDER BY scope_id"""
        )]
        missing_prefixes = [dict(row) for row in connection.execute(
            """SELECT b.observation_id,b.scope_id,b.group_id
                 FROM baseline_observation b
            LEFT JOIN scale_group g ON g.group_id=b.group_id
                WHERE g.group_id IS NULL OR g.scope_id != b.scope_id
             ORDER BY b.observation_id"""
        )]
        rows = [dict(row) for row in connection.execute(
            """SELECT scope_id,split_family,COUNT(*) AS group_count,
                      SUM(history_count) AS history_count,
                      SUM(challenge_count) AS challenge_count
                 FROM scale_group
             GROUP BY scope_id,split_family
             ORDER BY scope_id,split_family"""
        )]
    finally:
        connection.close()
    if conflicts or missing_prefixes:
        raise RuntimeError("scope/split-family isolation failed")
    return {
        "scope_count": len(rows),
        "conflict_count": 0,
        "missing_prefix_count": 0,
        "scope_family_digest": _sha(rows),
    }


def freeze(
    work_db: Path, atmem_db: Path, output_dir: Path, *, embedding_model: str,
) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"snapshot output already exists: {output_dir}")
    _integrity(work_db)
    _integrity(atmem_db)
    adjudication = _adjudication_manifest(work_db)
    split_scopes = _split_scope_manifest(work_db)

    memory = Memory(atmem_db, auto_vectors=False, allow_insecure_typed_development=True)
    vector_path = default_index_path(atmem_db)
    index = SemanticIndex(vector_path, policy=memory.policy)
    embedder = SentenceTransformersEmbedder(embedding_model)
    vector_receipts: list[dict[str, Any]] = []
    try:
        subject_ids = [
            str(row[0]) for row in memory.store._conn.execute(
                "SELECT DISTINCT subject_id FROM records WHERE status='active' ORDER BY subject_id"
            ).fetchall()
        ]
        for subject_id in subject_ids:
            vector_receipts.append(index.build(memory, subject_id, embedder))
        # SQLiteStore intentionally does not expose a public checkpoint method.
        # Freeze from a fully checkpointed main database rather than copying a
        # file whose committed pages may still live in a WAL sidecar.
        memory.store._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        index.checkpoint_storage()
    finally:
        index.close()
        memory.close()
    _integrity(atmem_db)
    _integrity(vector_path)

    output_dir.mkdir(parents=True)
    artifacts = {
        "atmem.sqlite3": atmem_db,
        "atmem.vectors.sqlite3": vector_path,
        "transition-work.sqlite3": work_db,
    }
    inventory: list[dict[str, Any]] = []
    for name, source in artifacts.items():
        destination = output_dir / name
        shutil.copy2(source, destination)
        _integrity(destination)
        inventory.append({
            "path": name, "size": destination.stat().st_size,
            "sha256": _sha_file(destination),
        })
    init_manifest = json.loads(
        (work_db.parent / "init-manifest.json").read_text(encoding="utf-8")
    )
    manifest = {
        "format": FORMAT, "created_at": _now(),
        "experiment_scale_percent": init_manifest["experiment_scale_percent"],
        "source_init_manifest_digest": init_manifest["manifest_digest"],
        "source_database": init_manifest["source_database"],
        "selection": init_manifest["selection"],
        "scale_manifest_digest": init_manifest["scale_manifest"]["group_assignment_digest"],
        "adjudication": adjudication,
        "split_scope_isolation": split_scopes,
        "embedder": embedder.identity,
        "vector_subject_count": len(vector_receipts),
        "vector_receipts_digest": _sha(vector_receipts),
        "inventory": inventory,
    }
    manifest["manifest_digest"] = _sha(manifest)
    (output_dir / "snapshot-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-db", type=Path, required=True)
    parser.add_argument("--atmem-db", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDER)
    args = parser.parse_args()
    result = freeze(
        args.work_db, args.atmem_db, args.output_dir,
        embedding_model=args.embedding_model,
    )
    print(json.dumps({
        "manifest_digest": result["manifest_digest"],
        "adjudication": result["adjudication"],
        "vector_subject_count": result["vector_subject_count"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
