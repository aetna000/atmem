"""Canonical persistence for governed task state.

The properties that matter here are the ones an operator would never see until
they mattered: revisions cannot be rewritten, one base revision cannot grow two
successors, a task cannot be read from outside its scope, and pause accounting
survives a restart.
"""

from __future__ import annotations

from datetime import timedelta
import sqlite3

import pytest

from atmem.core.time import FixedUtcClock, to_iso
from atmem.store.sqlite import SQLiteStore

from conftest_task_state import (  # noqa: F401  (fixtures)
    MOMENT,
    SCOPE,
    seed_task,
    store,
)


EXPECTED_MIGRATIONS = [
    "0070_governed_task_profiles",
    "0071_governed_tasks",
    "0072_governed_task_revisions",
    "0073_governed_task_provenance",
    "0074_governed_task_proposals",
    "0075_governed_task_steps",
    "0076_governed_task_deliveries",
    "0077_governed_task_sequences",
    # Amendment A's session bindings. Appended inside Spec 007's reserved
    # 0070-0079 block, leaving 0079 as the last identifier available before the
    # Spec 010 registry must be used.
    "0078_governed_task_session_bindings",
]


def test_task_tables_are_created_in_the_reserved_bootstrap_block(
    store: SQLiteStore,
) -> None:
    applied = store.applied_migrations()

    assert EXPECTED_MIGRATIONS == [row for row in applied if row.startswith("007")]
    assert applied == sorted(applied), "bootstrap identifiers stay append-only"
    # Spec 006's block must be untouched by Spec 007's addition.
    assert [row for row in applied if row.startswith("006")] == [
        "0060_memory_proposals",
        "0061_memory_reviews",
        "0062_memory_lineage",
        "0063_record_generation",
    ]


def test_creating_the_schema_is_idempotent(store: SQLiteStore) -> None:
    path = store.path
    for _ in range(3):
        reopened = SQLiteStore(path)
        try:
            assert [
                row for row in reopened.applied_migrations() if row.startswith("007")
            ] == EXPECTED_MIGRATIONS
        finally:
            reopened.close()


# --- scope isolation --------------------------------------------------------


def test_a_task_is_never_readable_outside_its_exact_scope(store: SQLiteStore) -> None:
    seed_task(store, task_id="task-1")

    assert store.get_task(
        subject_id=SCOPE.subject_id, agent_id=SCOPE.agent_id,
        workspace_id=SCOPE.workspace_id, task_id="task-1",
    ) is not None
    for wrong in (
        {"subject_id": "other-subject"},
        {"agent_id": "other-agent"},
        {"workspace_id": "other-workspace"},
    ):
        lookup = {
            "subject_id": SCOPE.subject_id,
            "agent_id": SCOPE.agent_id,
            "workspace_id": SCOPE.workspace_id,
            "task_id": "task-1",
            **wrong,
        }
        assert store.get_task(**lookup) is None, wrong


def test_listing_is_scope_filtered_and_deterministically_ordered(
    store: SQLiteStore,
) -> None:
    for index in range(5):
        seed_task(store, task_id=f"task-{index}", created_offset_minutes=index)
    seed_task(store, task_id="other-task", subject_id="other-subject")

    rows = store.list_tasks(subject_id=SCOPE.subject_id)

    assert [row["task_id"] for row in rows] == [f"task-{i}" for i in range(5)]
    assert all(row["subject_id"] == SCOPE.subject_id for row in rows)


def test_listing_pages_deterministically_with_a_cursor(store: SQLiteStore) -> None:
    for index in range(5):
        seed_task(store, task_id=f"task-{index}", created_offset_minutes=index)

    first = store.list_tasks(subject_id=SCOPE.subject_id, limit=2)
    cursor = f"{first[-1]['created_at_utc']}|{first[-1]['task_id']}"
    second = store.list_tasks(subject_id=SCOPE.subject_id, limit=2, cursor=cursor)

    assert [row["task_id"] for row in first] == ["task-0", "task-1"]
    assert [row["task_id"] for row in second] == ["task-2", "task-3"]
    assert not set(row["task_id"] for row in first) & set(
        row["task_id"] for row in second
    )


# --- immutable revisions ----------------------------------------------------


def test_revisions_cannot_be_rewritten(store: SQLiteStore) -> None:
    seed_task(store, task_id="task-1")

    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        store._conn.execute(
            "UPDATE governed_task_revisions SET actor = 'someone-else' "
            "WHERE task_id = 'task-1'"
        )


def test_one_base_revision_can_have_at_most_one_successor(
    store: SQLiteStore,
) -> None:
    """The optimistic-concurrency guarantee, enforced by the database."""
    seed_task(store, task_id="task-1")
    store.insert_task_revision(
        task_id="task-1", revision=2, parent_revision=1, state={"revision": 2},
        state_sha256="sha256:" + "b" * 64, semantic_sha256="sha256:" + "c" * 64,
        actor="agent", actor_role="host_agent", reason_codes=["transition_accepted"],
        evidence=[], created_at_utc=to_iso(MOMENT),
    )

    with pytest.raises(sqlite3.IntegrityError):
        store.insert_task_revision(
            task_id="task-1", revision=3, parent_revision=1,
            state={"revision": 3}, state_sha256="sha256:" + "d" * 64,
            semantic_sha256="sha256:" + "e" * 64, actor="other",
            actor_role="host_agent", reason_codes=["transition_accepted"],
            evidence=[], created_at_utc=to_iso(MOMENT),
        )


def test_the_head_advances_only_from_the_expected_revision(
    store: SQLiteStore,
) -> None:
    seed_task(store, task_id="task-1")

    assert store.advance_task_head(
        task_id="task-1", expected_head=1, new_head=2,
        updated_at_utc=to_iso(MOMENT),
    ) is True
    # A second writer holding the stale head loses, and nothing changes.
    assert store.advance_task_head(
        task_id="task-1", expected_head=1, new_head=2,
        updated_at_utc=to_iso(MOMENT),
    ) is False
    task = store.get_task(
        subject_id=SCOPE.subject_id, agent_id=SCOPE.agent_id,
        workspace_id=SCOPE.workspace_id, task_id="task-1",
    )
    assert task["head_revision"] == 2


def test_lifecycle_values_outside_the_closed_set_are_refused(
    store: SQLiteStore,
) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        store.insert_task(
            task_id="task-bad", subject_id=SCOPE.subject_id,
            agent_id=SCOPE.agent_id, workspace_id=SCOPE.workspace_id,
            profile_id="general", profile_version="general-v1", goal="G",
            lifecycle="archived", head_revision=1,
            created_at_utc=to_iso(MOMENT), last_progress_at_utc=to_iso(MOMENT),
            expiry_rule={}, clock_source="fixed-utc-v1", idempotency_key="k-bad",
        )


@pytest.mark.parametrize(
    "lifecycle", ["open", "paused", "completed", "cancelled", "expired"]
)
def test_all_five_lifecycle_values_persist(store: SQLiteStore, lifecycle: str) -> None:
    seed_task(store, task_id=f"task-{lifecycle}", lifecycle=lifecycle)
    task = store.get_task(
        subject_id=SCOPE.subject_id, agent_id=SCOPE.agent_id,
        workspace_id=SCOPE.workspace_id, task_id=f"task-{lifecycle}",
    )
    assert task["lifecycle"] == lifecycle


def test_negative_pause_accounting_is_refused(store: SQLiteStore) -> None:
    seed_task(store, task_id="task-1")
    with pytest.raises(sqlite3.IntegrityError):
        store._conn.execute(
            "UPDATE governed_tasks SET no_progress_paused_ms = -1 "
            "WHERE task_id = 'task-1'"
        )


# --- pause accounting -------------------------------------------------------


def test_pause_accounting_accumulates_and_survives_restart(
    store: SQLiteStore,
) -> None:
    seed_task(store, task_id="task-1")
    clock = FixedUtcClock(MOMENT)

    store.advance_task_head(
        task_id="task-1", expected_head=1, new_head=2,
        updated_at_utc=to_iso(clock.now()), lifecycle="paused",
        paused_at_utc=to_iso(clock.now()),
    )
    clock.advance(minutes=30)
    store.advance_task_head(
        task_id="task-1", expected_head=2, new_head=3,
        updated_at_utc=to_iso(clock.now()), lifecycle="open",
        clear_paused_at=True, add_paused_ms=30 * 60 * 1000,
    )

    reopened = SQLiteStore(store.path)
    try:
        task = reopened.get_task(
            subject_id=SCOPE.subject_id, agent_id=SCOPE.agent_id,
            workspace_id=SCOPE.workspace_id, task_id="task-1",
        )
        assert task["no_progress_paused_ms"] == 30 * 60 * 1000
        assert task["paused_at_utc"] is None
        assert task["lifecycle"] == "open"
    finally:
        reopened.close()


def test_pause_accounting_can_be_rebuilt_from_immutable_history(
    store: SQLiteStore,
) -> None:
    """The accumulator is the fast path; history is the audit."""
    seed_task(store, task_id="task-1")
    clock = FixedUtcClock(MOMENT)

    clock.advance(minutes=5)
    store.insert_task_revision(
        task_id="task-1", revision=2, parent_revision=1,
        state={"lifecycle": "paused"}, state_sha256="sha256:" + "b" * 64,
        semantic_sha256="sha256:" + "c" * 64, actor="operator",
        actor_role="operator", reason_codes=["lifecycle_change_accepted"],
        evidence=[], created_at_utc=to_iso(clock.now()),
    )
    clock.advance(minutes=30)
    store.insert_task_revision(
        task_id="task-1", revision=3, parent_revision=2,
        state={"lifecycle": "open"}, state_sha256="sha256:" + "d" * 64,
        semantic_sha256="sha256:" + "e" * 64, actor="operator",
        actor_role="operator", reason_codes=["lifecycle_change_accepted"],
        evidence=[], created_at_utc=to_iso(clock.now()),
    )

    assert store.rebuild_task_pause_accounting("task-1") == 30 * 60 * 1000


def test_an_open_pause_is_not_yet_counted_as_completed(store: SQLiteStore) -> None:
    seed_task(store, task_id="task-1")
    clock = FixedUtcClock(MOMENT)
    clock.advance(minutes=5)
    store.insert_task_revision(
        task_id="task-1", revision=2, parent_revision=1,
        state={"lifecycle": "paused"}, state_sha256="sha256:" + "b" * 64,
        semantic_sha256="sha256:" + "c" * 64, actor="operator",
        actor_role="operator", reason_codes=["lifecycle_change_accepted"],
        evidence=[], created_at_utc=to_iso(clock.now()),
    )

    assert store.rebuild_task_pause_accounting("task-1") == 0


# --- proposals, steps, provenance, deliveries -------------------------------


def test_a_proposal_idempotency_key_is_unique_per_task(store: SQLiteStore) -> None:
    seed_task(store, task_id="task-1")
    arguments = dict(
        task_id="task-1", subject_id=SCOPE.subject_id, agent_id=SCOPE.agent_id,
        workspace_id=SCOPE.workspace_id, idempotency_key="delta-1",
        payload_sha256="sha256:" + "f" * 64, base_revision=1, actor="atbot",
        actor_role="atbot_intelligence", proposal={}, decision={},
        outcome="accepted", resulting_revision=2, created_at_utc=to_iso(MOMENT),
    )
    store.insert_task_proposal(proposal_id="proposal-1", **arguments)

    with pytest.raises(sqlite3.IntegrityError):
        store.insert_task_proposal(proposal_id="proposal-2", **arguments)
    assert store.find_task_proposal("task-1", "delta-1")["proposal_id"] == "proposal-1"


def test_steps_record_every_outcome_including_no_change(store: SQLiteStore) -> None:
    seed_task(store, task_id="task-1")
    for outcome in ("accepted", "rejected", "conflict", "no_change"):
        store.insert_task_step(
            task_id="task-1", step_kind="host_observation", outcome=outcome,
            base_revision=1, actor="agent", recorded_at_utc=to_iso(MOMENT),
            reason_codes=["transition_accepted"],
        )

    outcomes = [row["outcome"] for row in store.list_task_steps("task-1")]
    assert sorted(outcomes) == ["accepted", "conflict", "no_change", "rejected"]


def test_an_unknown_step_outcome_is_refused(store: SQLiteStore) -> None:
    seed_task(store, task_id="task-1")
    with pytest.raises(sqlite3.IntegrityError):
        store.insert_task_step(
            task_id="task-1", step_kind="host_observation", outcome="maybe",
            base_revision=1, actor="agent", recorded_at_utc=to_iso(MOMENT),
        )


def test_repeated_equivalent_actions_are_countable(store: SQLiteStore) -> None:
    seed_task(store, task_id="task-1")
    clock = FixedUtcClock(MOMENT)
    for _ in range(3):
        clock.advance(seconds=10)
        store.insert_task_step(
            task_id="task-1", step_kind="tool_result", outcome="no_change",
            base_revision=1, actor="agent", recorded_at_utc=to_iso(clock.now()),
            action_fingerprint="sha256:repeat",
        )
    store.insert_task_step(
        task_id="task-1", step_kind="tool_result", outcome="no_change",
        base_revision=1, actor="agent", recorded_at_utc=to_iso(clock.now()),
        action_fingerprint="sha256:different",
    )

    assert store.count_recent_equivalent_actions(
        "task-1", "sha256:repeat", since_utc=to_iso(MOMENT)
    ) == 3


def test_field_and_status_provenance_is_recorded_and_immutable(
    store: SQLiteStore,
) -> None:
    seed_task(store, task_id="task-1")
    store.insert_task_provenance(
        task_id="task-1", revision=1, target_kind="status", target_id="item-1",
        actor="atbot", actor_role="atbot_intelligence", method="model_delta",
        assurance="model_interpreted", observed_at_utc=to_iso(MOMENT),
        evidence=[{"kind": "tool_call", "reference_id": "call-1"}],
    )

    [row] = store.list_task_provenance("task-1", target_kind="status")
    assert row["target_id"] == "item-1"
    assert row["assurance"] == "model_interpreted"
    assert row["evidence"][0]["reference_id"] == "call-1"
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        store._conn.execute(
            "UPDATE governed_task_provenance SET assurance = 'independently_verified'"
        )


def test_delivery_exposure_is_confirmed_exactly_once(store: SQLiteStore) -> None:
    seed_task(store, task_id="task-1")
    delivery_id = store.insert_task_delivery(
        task_id="task-1", revision=1, subject_id=SCOPE.subject_id,
        agent_id=SCOPE.agent_id, workspace_id=SCOPE.workspace_id,
        disposition="injected", prepared_at_utc=to_iso(MOMENT),
        context_sha256="sha256:" + "a" * 64,
    )

    assert store.mark_task_delivery_exposed(delivery_id) is True
    assert store.mark_task_delivery_exposed(delivery_id) is False, (
        "confirming twice is not a second exposure"
    )


def test_an_unknown_delivery_disposition_is_refused(store: SQLiteStore) -> None:
    seed_task(store, task_id="task-1")
    with pytest.raises(sqlite3.IntegrityError):
        store.insert_task_delivery(
            task_id="task-1", revision=1, subject_id=SCOPE.subject_id,
            agent_id=SCOPE.agent_id, workspace_id=SCOPE.workspace_id,
            disposition="maybe", prepared_at_utc=to_iso(MOMENT),
        )


# --- profiles ---------------------------------------------------------------


def test_a_registered_profile_version_is_unique(store: SQLiteStore) -> None:
    store.insert_task_profile(
        version="custom-v1", profile_id="custom", digest="sha256:" + "a" * 64,
        profile={"profile_id": "custom"}, actor="admin",
    )

    with pytest.raises(sqlite3.IntegrityError):
        store.insert_task_profile(
            version="custom-v1", profile_id="custom", digest="sha256:" + "b" * 64,
            profile={"profile_id": "custom"}, actor="admin",
        )
    assert store.get_task_profile("custom-v1")["digest"] == "sha256:" + "a" * 64


# --- deletion ---------------------------------------------------------------


def test_deleting_a_task_removes_everything_derived_from_it(
    store: SQLiteStore,
) -> None:
    seed_task(store, task_id="task-1")
    store.insert_task_step(
        task_id="task-1", step_kind="host_observation", outcome="accepted",
        base_revision=1, actor="agent", recorded_at_utc=to_iso(MOMENT),
    )
    store.insert_task_provenance(
        task_id="task-1", revision=1, target_kind="task", target_id="task-1",
        actor="operator", actor_role="operator", method="start",
        assurance="operator_confirmed", observed_at_utc=to_iso(MOMENT),
    )
    store.insert_task_delivery(
        task_id="task-1", revision=1, subject_id=SCOPE.subject_id,
        agent_id=SCOPE.agent_id, workspace_id=SCOPE.workspace_id,
        disposition="withheld", prepared_at_utc=to_iso(MOMENT),
    )

    result = store.delete_task(
        subject_id=SCOPE.subject_id, agent_id=SCOPE.agent_id,
        workspace_id=SCOPE.workspace_id, task_id="task-1",
    )

    assert result["deleted"] is True
    assert result["removed"]["governed_tasks"] == 1
    assert result["removed"]["governed_task_revisions"] == 1
    assert store.get_task(
        subject_id=SCOPE.subject_id, agent_id=SCOPE.agent_id,
        workspace_id=SCOPE.workspace_id, task_id="task-1",
    ) is None
    assert store.list_task_steps("task-1") == []
    assert store.list_task_provenance("task-1") == []
    assert store.list_task_deliveries("task-1") == []


def test_deleting_out_of_scope_removes_nothing(store: SQLiteStore) -> None:
    seed_task(store, task_id="task-1")

    result = store.delete_task(
        subject_id="other-subject", agent_id=SCOPE.agent_id,
        workspace_id=SCOPE.workspace_id, task_id="task-1",
    )

    assert result["deleted"] is False
    assert store.get_task(
        subject_id=SCOPE.subject_id, agent_id=SCOPE.agent_id,
        workspace_id=SCOPE.workspace_id, task_id="task-1",
    ) is not None


def test_resetting_a_subject_removes_its_governed_tasks(store: SQLiteStore) -> None:
    seed_task(store, task_id="task-1")
    seed_task(store, task_id="task-other", subject_id="other-subject")

    store.reset_subject(SCOPE.subject_id)

    assert store.list_tasks(subject_id=SCOPE.subject_id) == []
    assert len(store.list_tasks(subject_id="other-subject")) == 1
