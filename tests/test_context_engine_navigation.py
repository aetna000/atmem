from __future__ import annotations

import pytest

from atmem.context_engine.formation import FormationManager, SourceEpisode, SourcePart
from atmem.context_engine.navigator import EvidenceNavigator, NavigationBudget
from atmem.contracts.models import AuthorityScope
from atmem.store.sqlite import SQLiteStore


SCOPE = AuthorityScope("person-1", "agent-a", "workspace-1")


def _fixture() -> tuple[SQLiteStore, str, tuple[str, ...]]:
    store = SQLiteStore(":memory:")
    manager = FormationManager(store)
    generation = manager.begin_generation(SCOPE, profile_id="context-navigate")
    source = manager.retain_source(SourceEpisode(
        episode_id="episode-nav", scope=SCOPE,
        parts=(
            SourcePart("before", 0, "text", "text/plain", b"Before repair uploads failed."),
            SourcePart("action", 1, "text", "text/plain", b"The expired certificate was rotated."),
            SourcePart("after", 2, "text", "text/plain", b"After repair uploads succeeded."),
        ),
    ))
    manager.form_source(source, generation)
    units = tuple(
        str(row["unit_id"]) for row in store._conn.execute(
            "SELECT unit_id FROM context_evidence_units WHERE generation_id=? ORDER BY unit_id",
            (generation,),
        ).fetchall()
    )
    return store, generation, units


def test_manifest_is_content_free_and_inspection_is_authorized_and_bounded() -> None:
    store, generation, units = _fixture()
    try:
        navigator = EvidenceNavigator(
            store, generation_id=generation, authorized_unit_ids=units,
            budget=NavigationBudget(max_operations=5, max_bytes=256, max_elapsed_ms=1000),
        )
        manifest = navigator.manifest()
        assert "uploads" not in str(manifest)
        hits = navigator.search("certificate rotated", kinds=("fact", "raw_state"))
        assert hits
        inspected = navigator.inspect(hits[0])
        assert "certificate" in inspected.text
        assert navigator.follow(hits[0])
        receipt = navigator.submit("plan-1", (hits[0],))
        assert receipt.submitted_ranges == (inspected.source_range,)
        assert receipt.operations_used <= 5
        assert receipt.bytes_used <= 256
    finally:
        store.close()


def test_navigator_rejects_unmanifested_or_uninspected_submission() -> None:
    store, generation, units = _fixture()
    try:
        navigator = EvidenceNavigator(
            store, generation_id=generation, authorized_unit_ids=units[:1],
            budget=NavigationBudget(max_operations=3, max_bytes=256, max_elapsed_ms=1000),
        )
        with pytest.raises(PermissionError, match="authorized manifest"):
            navigator.inspect(units[-1])
        with pytest.raises(ValueError, match="inspected"):
            navigator.submit("plan-1", (units[0],))
    finally:
        store.close()


def test_navigator_fails_closed_when_operation_or_byte_budget_exhausts() -> None:
    store, generation, units = _fixture()
    try:
        navigator = EvidenceNavigator(
            store, generation_id=generation, authorized_unit_ids=units,
            budget=NavigationBudget(max_operations=1, max_bytes=4, max_elapsed_ms=1000),
        )
        navigator.manifest()
        with pytest.raises(RuntimeError, match="operation budget"):
            navigator.search("uploads")
        navigator = EvidenceNavigator(
            store, generation_id=generation, authorized_unit_ids=units,
            budget=NavigationBudget(max_operations=2, max_bytes=4, max_elapsed_ms=1000),
        )
        with pytest.raises(RuntimeError, match="byte budget"):
            navigator.inspect(units[0])
    finally:
        store.close()
