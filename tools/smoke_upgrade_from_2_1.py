#!/usr/bin/env python3
"""Create a published-version fixture, then prove 2.2.6b3 upgrades it safely."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
import sqlite3

from atmem import Memory
from atmem.control.manager import ControlPlaneManager


SUBJECT = "upgrade-user"
MEMORY_TEXT = "My favorite lunch is burgers."
CANDIDATE_TEXT = "Remember that I prefer concise answers."


def _manager(value: object) -> ControlPlaneManager:
    # AtMem 2.1 returned the manager directly. AtMem 2.2 additionally reports
    # whether an existing shadow migration was reused.
    return value[0] if isinstance(value, tuple) else value  # type: ignore[index,return-value]


def create_fixture(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=False)
    database = root / "memory.db"
    memory = Memory(database)
    try:
        admission = memory.remember(
            SUBJECT,
            MEMORY_TEXT,
            session_id="upgrade-release-gate",
        )
        record_id = admission["records"][0]["id"]
        record_content = admission["records"][0]["content"]
        assert memory.verify(SUBJECT)["valid"] is True
    finally:
        memory.close()

    manager = _manager(
        ControlPlaneManager.start(
            host="generic",
            state_path=root / "control-plane.json",
            control_root=root / "migrations",
            subject_id=SUBJECT,
            memory_db=database,
        )
    )
    capture = manager.capture(
        CANDIDATE_TEXT,
        authenticated_user=True,
        subject_id=SUBJECT,
        agent_id="main",
    )
    state = manager.state()
    candidates = manager.candidates()
    manifest = {
        "source_version": importlib.metadata.version("atmem"),
        "record_id": record_id,
        "record_content": record_content,
        "migration_id": state.migration_id,
        "mode": state.mode.value,
        "candidate_ids": sorted(str(row["id"]) for row in candidates),
        "capture_candidate_ids": sorted(capture.get("candidate_ids") or []),
    }
    assert manifest["source_version"] in {"2.1.0", "2.2.3", "2.2.4", "2.2.5"}
    assert manifest["mode"] == "shadow"
    assert manifest["candidate_ids"]
    (root / "fixture.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def verify_upgrade(root: Path) -> None:
    manifest = json.loads((root / "fixture.json").read_text(encoding="utf-8"))
    assert importlib.metadata.version("atmem") == "2.2.6b3"
    assert importlib.metadata.version("atmem-atbot") == "0.1.0a4"

    database = root / "memory.db"
    memory = Memory(database)
    try:
        recalled = memory.recall(SUBJECT, "favorite lunch", min_score=0.0)
        matching = [row for row in recalled if row["id"] == manifest["record_id"]]
        assert matching and matching[0]["content"] == manifest["record_content"]
        assert memory.verify(SUBJECT)["valid"] is True
    finally:
        memory.close()

    with sqlite3.connect(database) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert {
        "protocol_sources",
        "protocol_candidate_sets",
        "semantic_index_registry",
        "record_generations",
    } <= tables
    assert Path(f"{database}.vectors.db").is_file()

    manager = ControlPlaneManager(root / "control-plane.json")
    state = manager.state()
    assert state.migration_id == manifest["migration_id"]
    assert state.mode.value == "shadow"
    candidate_ids = {str(row["id"]) for row in manager.candidates()}
    assert set(manifest["candidate_ids"]) <= candidate_ids
    evidence_db = Path(state.control_dir) / "evidence.db"
    with sqlite3.connect(evidence_db) as connection:
        schema_version = connection.execute(
            "SELECT value FROM schema_meta WHERE key = 'schema_version'"
        ).fetchone()[0]
    assert int(schema_version) == 5
    print("AtMem persisted-state -> 2.2.6b3 upgrade smoke test passed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("create", "verify"))
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    if args.mode == "create":
        create_fixture(args.root)
    else:
        verify_upgrade(args.root)


if __name__ == "__main__":
    main()
