from __future__ import annotations

from atmem.context_engine.formation import SourcePart, SourceEpisode, FormationManager
from atmem.context_engine.coverage import storage_report
from atmem.contracts.models import AuthorityScope
from atmem.store.sqlite import SQLiteStore
from atmem import cli


SCOPE = AuthorityScope(subject_id="person-1", agent_id="agent-a", workspace_id="work-1")


def _episode() -> SourceEpisode:
    return SourceEpisode(
        episode_id="episode-1",
        scope=SCOPE,
        parts=(
            SourcePart("text-1", 0, "text", "text/plain", b"I am 45 years old."),
            SourcePart("image-1", 1, "image", "image/png", b"\x89PNG\r\nfixture"),
            SourcePart("text-2", 2, "text", "text/plain", b"Use the blue door."),
        ),
    )


def test_source_parts_are_ordered_stable_and_retained_once() -> None:
    store = SQLiteStore(":memory:")
    try:
        manager = FormationManager(store)
        first = manager.retain_source(_episode())
        second = manager.retain_source(_episode())

        assert first == second
        assert [item.part_id for item in manager.list_source_parts(first)] == [
            "text-1", "image-1", "text-2"
        ]
        assert store.context_source_storage(first)["source_body_rows"] == 3
        assert store.context_source_storage(first)["source_body_bytes"] == sum(
            len(part.content) for part in _episode().parts
        )
    finally:
        store.close()


def test_ranges_have_stable_identity_and_units_only_reference_source() -> None:
    store = SQLiteStore(":memory:")
    try:
        manager = FormationManager(store)
        source_id = manager.retain_source(_episode())
        generation = manager.begin_generation(SCOPE, profile_id="context-fast")
        left = manager.add_range(source_id, "text-1", 0, 7)
        again = manager.add_range(source_id, "text-1", 0, 7)
        unit_id = manager.add_unit(
            generation,
            kind="fact",
            ranges=(left,),
            compact_value={"subject": "person-1", "relation": "age", "value": 45},
        )

        assert left == again
        assert manager.get_unit(unit_id)["ranges"][0]["range_id"] == left.range_id
        assert store.context_source_storage(source_id)["derived_source_body_bytes"] == 0
    finally:
        store.close()


def test_persistent_plaintext_household_cannot_retain_v3_source(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "plain.db")
    try:
        manager = FormationManager(store)
        try:
            manager.retain_source(_episode())
        except RuntimeError as exc:
            assert "encrypted household" in str(exc)
        else:  # pragma: no cover - a security regression must be loud
            raise AssertionError("plaintext V3 formation unexpectedly succeeded")
    finally:
        store.close()


def test_storage_report_detects_no_source_body_duplication() -> None:
    store = SQLiteStore(":memory:")
    try:
        manager = FormationManager(store)
        source_id = manager.retain_source(_episode())
        generation = manager.begin_generation(SCOPE, profile_id="context-fast")
        source_range = manager.add_range(source_id, "text-1", 0, 7)
        manager.add_unit(
            generation, kind="fact", ranges=(source_range,),
            compact_value={"subject": "person-1", "relation": "age", "value": 45},
        )
        report = storage_report(store)
        assert report["source_duplication"] == {"duplicate_rows": 0, "passed": True}
        assert report["bytes"]["canonical_source"] > 0
        schema = store._conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='context_units_fts'"
        ).fetchone()
        assert schema is None or "content=''" in str(schema["sql"])
    finally:
        store.close()


def test_storage_report_has_machine_readable_cli(tmp_path, monkeypatch, capsys) -> None:
    path = tmp_path / "memory.db"
    store = SQLiteStore(path)
    store.close()
    monkeypatch.setattr(
        "sys.argv", ["atmem", "context-engine", "storage", str(path), "--json"]
    )
    cli.main()
    value = __import__("json").loads(capsys.readouterr().out)
    assert value["format"] == "atmem-context-storage-report-v1"
    assert value["storage_ready"]["reason"] == "encrypted_household_required"


def test_deterministic_formation_builds_all_eight_source_linked_views() -> None:
    store = SQLiteStore(":memory:")
    try:
        manager = FormationManager(store)
        episode = SourceEpisode(
            episode_id="episode-eight-views", scope=SCOPE,
            parts=(
                SourcePart(
                    "text", 0, "text", "text/plain",
                    (
                        b"Before repair the worker failed; rotating the certificate restored uploads. "
                        b"Restore in order: verify; decrypt; import. "
                        b"Release notices must go to eng-releases, never eng-all. "
                        b"Gotcha: an empty glob exits successfully but imports no records."
                    ),
                ),
            ),
        )
        source = manager.retain_source(episode)
        generation = manager.begin_generation(SCOPE, profile_id="context-fast")
        receipt = manager.form_source(source, generation)
        kinds = {
            row["kind"] for row in store._conn.execute(
                "SELECT kind FROM context_evidence_units WHERE generation_id=?",
                (generation,),
            ).fetchall()
        }
        assert kinds == {
            "raw_state", "transition", "fact", "entity", "procedure", "rule",
            "gotcha", "premise",
        }
        assert receipt.representation_complete is True
        assert receipt.loss_ranges == ()
        assert manager.coverage_report(generation)["coverage_ratio"] == 1.0
    finally:
        store.close()


def test_formation_replay_is_idempotent_with_stable_unit_occurrences() -> None:
    store = SQLiteStore(":memory:")
    try:
        manager = FormationManager(store)
        source = manager.retain_source(_episode())
        generation = manager.begin_generation(SCOPE, profile_id="context-fast")
        first = manager.form_source(source, generation)
        unit_count = store._conn.execute(
            "SELECT COUNT(*) FROM context_evidence_units WHERE generation_id=?",
            (generation,),
        ).fetchone()[0]
        second = manager.form_source(source, generation)
        assert second.formation_id == first.formation_id
        assert store._conn.execute(
            "SELECT COUNT(*) FROM context_evidence_units WHERE generation_id=?",
            (generation,),
        ).fetchone()[0] == unit_count
    finally:
        store.close()
