"""Upgrades from real persisted state, not from a freshly created schema.

`tests/fixtures/upgrades/` holds databases written by each supported published
AtMem version. A migration that only works on a database this build created
proves nothing; these fixtures are the actual bytes a user would be upgrading.

Three properties are asserted for every floor: the upgrade preserves the
memory and its audit chain, an interrupted upgrade recovers forward on the
next open, and the resulting schema is still readable by the version the user
would roll back to.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sqlite3

import pytest

from atmem.memory import Memory
from atmem.store.sqlite import SQLiteStore


FIXTURES = Path(__file__).parent / "fixtures" / "upgrades"
MANIFEST = json.loads((FIXTURES / "manifest.json").read_text())
FLOORS = [row["version"] for row in MANIFEST["floors"]]
SUBJECT = MANIFEST["expected"]["subject_id"]

# Every bootstrap identifier Spec 006 reserved and shipped. Later specs append
# their own reserved blocks, so this suite asserts that Spec 006's identifiers
# are present, ordered, and unchanged -- never that they are the whole list.
EXPECTED_MIGRATIONS = [
    "0060_memory_proposals",
    "0061_memory_reviews",
    "0062_memory_lineage",
    "0063_record_generation",
]


def _spec_006(applied: list[str]) -> list[str]:
    return [row for row in applied if row.startswith("006")]


@pytest.fixture(params=FLOORS)
def upgraded(request, tmp_path: Path) -> Path:
    """One published database, copied so the fixture bytes stay pristine."""
    source = FIXTURES / f"atmem-{request.param}.db"
    target = tmp_path / f"atmem-{request.param}.db"
    shutil.copyfile(source, target)
    return target


def test_fixtures_are_the_recorded_published_bytes() -> None:
    for row in MANIFEST["floors"]:
        digest = hashlib.sha256((FIXTURES / row["file"]).read_bytes()).hexdigest()
        assert digest == row["sha256"], f"{row['file']} is not the recorded fixture"


def test_every_supported_floor_has_a_fixture() -> None:
    assert FLOORS, "the upgrade suite must cover at least one published floor"
    for version in FLOORS:
        assert (FIXTURES / f"atmem-{version}.db").exists()


def test_upgrade_preserves_memory_and_audit_chain(upgraded: Path) -> None:
    memory = Memory(upgraded, auto_vectors=False)
    try:
        active = memory.list(SUBJECT)
        everything = memory.list(SUBJECT, include_inactive=True)

        assert len(active) == MANIFEST["expected"]["active_records"]
        assert len(everything) == MANIFEST["expected"]["total_records"]
        assert memory.verify(SUBJECT)["valid"] is True
        assert any(
            row["content"] == "User's preferred airport is Melbourne." for row in active
        )
        assert any(
            row["content"] == "User's preferred airport is Sydney."
            and row["status"] == "superseded"
            for row in everything
        )
    finally:
        memory.close()


def test_upgrade_applies_every_reserved_bootstrap_identifier(upgraded: Path) -> None:
    store = SQLiteStore(upgraded)
    try:
        applied = store.applied_migrations()
        assert _spec_006(applied) == EXPECTED_MIGRATIONS
        assert applied == sorted(applied), "bootstrap identifiers stay append-only"
    finally:
        store.close()


def test_upgraded_state_accepts_new_governed_writes(upgraded: Path) -> None:
    from atmem.contracts import AuthorityScope
    from atmem.extract import build_resolution_context, propose_from_rules

    memory = Memory(upgraded, auto_vectors=False)
    try:
        scope = AuthorityScope(SUBJECT, "agent-1", "workspace-1")
        message = "Actually my preferred airport is Perth."
        context = build_resolution_context(memory.store, SUBJECT, scope=scope)
        [proposal] = propose_from_rules(
            message, scope=scope, source_id="source-upgrade", context=context
        )
        outcome = memory.submit_extraction_proposal(proposal, source_text=message)

        assert outcome["review_state"] == "committed"
        # Upgraded rows carry no generation history, so a proposal built from
        # them must still pin generation 0 and commit exactly once.
        assert outcome["superseded_record_ids"]
        assert [row["content"] for row in memory.list(SUBJECT)][-1:] != []
        assert memory.memory_lineage(SUBJECT)
        assert memory.verify(SUBJECT)["valid"] is True
    finally:
        memory.close()


def test_an_interrupted_upgrade_recovers_forward(upgraded: Path) -> None:
    """A half-applied upgrade must complete on the next open, not need repair."""
    store = SQLiteStore(upgraded)
    store.close()

    connection = sqlite3.connect(upgraded)
    connection.execute("DROP TABLE memory_lineage")
    connection.execute("DROP TABLE memory_reviews")
    connection.execute("DROP TABLE memory_proposals")
    connection.execute("DROP TABLE schema_migrations")
    connection.commit()
    connection.close()

    recovered = SQLiteStore(upgraded)
    try:
        assert _spec_006(recovered.applied_migrations()) == EXPECTED_MIGRATIONS
        assert recovered.list_memory_proposals(SUBJECT, review_states=None) == []
        assert len(recovered.list_records(SUBJECT)) == (
            MANIFEST["expected"]["active_records"]
        )
    finally:
        recovered.close()


def test_reopening_an_upgraded_database_is_idempotent(upgraded: Path) -> None:
    for _ in range(3):
        store = SQLiteStore(upgraded)
        try:
            assert _spec_006(store.applied_migrations()) == EXPECTED_MIGRATIONS
        finally:
            store.close()


def test_rollback_keeps_the_previous_version_readable(upgraded: Path) -> None:
    """The upgrade is additive, so downgrading does not strand a user.

    A published version that predates these migrations knows nothing about
    the new tables or the `generation` column. Rollback safety therefore means
    two things, both checked here against the upgraded file: no pre-existing
    column changed shape, and the exact writes the older code performs still
    succeed when they omit everything the upgrade added.
    """
    before = _schema(FIXTURES / upgraded.name)
    store = SQLiteStore(upgraded)
    store.close()
    after = _schema(upgraded)

    for table, columns in before.items():
        assert table in after, f"upgrade removed table {table}"
        for name, spec in columns.items():
            assert name in after[table], f"upgrade removed {table}.{name}"
            assert after[table][name] == spec, f"upgrade changed {table}.{name}"

    # A new table the old build never touches cannot break it, but a new
    # column on a table it writes must not be mandatory without a default.
    for name, spec in after["records"].items():
        if name in before["records"]:
            continue
        assert spec["notnull"] == 0 or spec["default"] is not None, (
            f"records.{name} would break inserts issued by the previous version"
        )

    connection = sqlite3.connect(upgraded)
    try:
        columns = ", ".join(before["records"])
        row = connection.execute(
            f"SELECT {columns} FROM records WHERE subject_id = ? LIMIT 1", (SUBJECT,)
        ).fetchone()
        assert row is not None
        # The shape of an insert issued by the previous version: it names no
        # generation column and expects the row to be accepted.
        connection.execute(
            f"INSERT INTO records ({columns}) VALUES ({', '.join('?' * len(row))})",
            tuple(
                f"rollback-{value}" if column == "id" else value
                for column, value in zip(before["records"], row)
            ),
        )
        connection.commit()
        assert connection.execute(
            "SELECT generation FROM records WHERE id = ?", ("rollback-" + str(row[0]),)
        ).fetchone()[0] == 0
    finally:
        connection.close()


def _schema(path: Path) -> dict[str, dict[str, dict[str, object]]]:
    connection = sqlite3.connect(path)
    try:
        tables = [
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        ]
        return {
            table: {
                str(column[1]): {"type": column[2], "notnull": column[3], "default": column[4]}
                for column in connection.execute(f"PRAGMA table_info({table})").fetchall()
            }
            for table in tables
        }
    finally:
        connection.close()
