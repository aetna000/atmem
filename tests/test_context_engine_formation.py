from __future__ import annotations

from atmem.context_engine.formation import (
    FormationManager, ModelFormationProposal, SourceEpisode, SourcePart,
)
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


def test_storage_report_detects_linked_full_source_duplication() -> None:
    store = SQLiteStore(":memory:")
    try:
        manager = FormationManager(store)
        source_id = manager.retain_source(_episode())
        generation = manager.begin_generation(SCOPE, profile_id="context-fast")
        source_range = manager.add_range(
            source_id, "text-1", 0, len(b"I am 45 years old.")
        )
        manager.add_unit(
            generation,
            kind="fact",
            ranges=(source_range,),
            compact_value={"copied_source": "I am 45 years old."},
        )
        report = storage_report(store)
        assert report["source_duplication"] == {"duplicate_rows": 1, "passed": False}
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


def test_correction_links_and_supersedes_prior_fact_but_preserves_source() -> None:
    store = SQLiteStore(":memory:")
    try:
        manager = FormationManager(store)
        generation = manager.begin_generation(SCOPE, profile_id="context-fast")
        for episode, text in (
            ("old", "Deployment updates go to room amber."),
            ("new", "Correction: deployment updates now go to room cobalt, replacing amber."),
        ):
            source = manager.retain_source(SourceEpisode(
                episode_id=episode, scope=SCOPE,
                parts=(SourcePart("text", 0, "text", "text/plain", text.encode()),),
            ))
            manager.form_source(source, generation)
        links = store._conn.execute(
            "SELECT * FROM context_evidence_links WHERE relation='supersedes'"
        ).fetchall()
        assert links
        assert store._conn.execute(
            "SELECT COUNT(*) FROM context_evidence_units WHERE lifecycle='superseded'"
        ).fetchone()[0] >= 1
        assert store._conn.execute("SELECT COUNT(*) FROM context_source_episodes").fetchone()[0] == 2
    finally:
        store.close()


def test_duplicate_occurrence_is_linked_without_erasing_either_source() -> None:
    store = SQLiteStore(":memory:")
    try:
        manager = FormationManager(store)
        generation = manager.begin_generation(SCOPE, profile_id="context-fast")
        for episode in ("occurrence-1", "occurrence-2"):
            source = manager.retain_source(SourceEpisode(
                episode_id=episode, scope=SCOPE,
                parts=(SourcePart(
                    "text", 0, "text", "text/plain", b"The audit port is 7412.",
                ),),
            ))
            manager.form_source(source, generation)
        assert store._conn.execute(
            "SELECT COUNT(*) FROM context_evidence_links WHERE relation='duplicate_occurrence'"
        ).fetchone()[0] >= 1
        assert store._conn.execute(
            "SELECT COUNT(*) FROM context_source_episodes"
        ).fetchone()[0] == 2
    finally:
        store.close()


def test_optional_extraction_is_additive_grounded_and_fail_closed() -> None:
    store = SQLiteStore(":memory:")
    try:
        manager = FormationManager(store)
        source = manager.retain_source(_episode())
        generation = manager.begin_generation(SCOPE, profile_id="context-fast")
        result = manager.form_with_extractor(
            source, generation,
            lambda _parts: (
                ModelFormationProposal(
                    kind="fact", source_id=source, part_id="text-1", start=0, end=7,
                    compact_value={"subject": "person-1", "relation": "age", "value": 45},
                ),
                ModelFormationProposal(
                    kind="fact", source_id=source, part_id="text-1", start=0, end=999,
                    compact_value={"unsupported": True},
                ),
            ),
            producer_id="fixture-model@sha256:abc", timeout_seconds=1,
        )
        assert result["deterministic"].representation_complete is True
        assert len(result["optional"]["created_unit_ids"]) == 1
        assert len(result["optional"]["rejected"]) == 1
    finally:
        store.close()


def test_deterministic_views_stay_below_storage_amplification_limit() -> None:
    store = SQLiteStore(":memory:")
    try:
        manager = FormationManager(store)
        source = manager.retain_source(SourceEpisode(
            episode_id="storage", scope=SCOPE,
            parts=(SourcePart(
                "text", 0, "text", "text/plain",
                b"Before repair uploads failed; rotating the certificate restored uploads. "
                b"Release notices must go to eng-releases, never eng-all.",
            ),),
        ))
        generation = manager.begin_generation(SCOPE, profile_id="context-fast")
        manager.form_source(source, generation)
        report = storage_report(store)
        assert report["derived_to_source_ratio"] <= 1.5
    finally:
        store.close()
