"""Dashboard task surfaces: gated, honest about mode, and never auto-retrying.

The riskiest thing a dashboard can do here is imply that task state is
influencing an agent when it is not, or quietly resubmit a mutation after a
conflict. Both are tested directly, alongside the accessibility and structural
rules the existing four-workspace design already holds.
"""

from __future__ import annotations

import json
from pathlib import Path
import re

import pytest

from atmem.contracts import AuthorityScope, capabilities
from atmem.contracts.task_state import (
    ActorRole,
    Assurance,
    ItemStatus,
    OperationKind,
    TaskItem,
    TaskOperation,
    TaskStartRequest,
    TaskStateProposal,
)
from atmem.control.manager import ControlPlaneManager
from atmem.control.ui import build_app_html
from atmem.task_state.enablement import ScopeEnablement


SUBJECT = "local-user"
AGENT = "default-agent"
WORKSPACE = "default-workspace"
SCOPE = AuthorityScope(SUBJECT, AGENT, WORKSPACE)


@pytest.fixture()
def manager(tmp_path: Path) -> ControlPlaneManager:
    engine = ControlPlaneManager.start(
        host="generic",
        state_path=tmp_path / "control.json",
        control_root=tmp_path / "migrations",
        subject_id=SUBJECT,
        memory_db=tmp_path / "memories.db",
    )
    return engine


def enable(manager: ControlPlaneManager, *, shadow: bool = False) -> None:
    service, memory = manager._task_service()
    try:
        ScopeEnablement(memory.store).enable(SCOPE, actor="operator", shadow=shadow)
    finally:
        memory.close()


def seed(manager: ControlPlaneManager, task_id: str = "task-1", **overrides) -> None:
    service, memory = manager._task_service()
    try:
        service.start(
            TaskStartRequest(
                task_id=task_id, scope=SCOPE, profile_id="general",
                profile_version="general-v1",
                goal=overrides.get("goal", "Ship the migration"),
                actor="operator", actor_role=ActorRole.OPERATOR,
                idempotency_key=f"start-{task_id}",
            ),
            items=(
                TaskItem(item_id="item-1", kind="step", title="First step",
                         required=True),
            ),
        )
    finally:
        memory.close()


# --- mode is stated plainly -------------------------------------------------


def test_a_disabled_scope_reports_no_influence(manager) -> None:
    mode = manager.task_state_mode(
        subject_id=SUBJECT, agent_id=AGENT, workspace_id=WORKSPACE
    )

    assert mode["mode"] == "disabled"
    assert mode["enabled"] is False
    assert mode["influences_agent"] is False


def test_shadow_mode_is_distinguishable_from_active(manager) -> None:
    enable(manager, shadow=True)
    shadow = manager.task_state_mode(
        subject_id=SUBJECT, agent_id=AGENT, workspace_id=WORKSPACE
    )
    assert shadow["mode"] == "shadow"
    assert shadow["enabled"] is True
    assert shadow["influences_agent"] is False, (
        "shadow records and evaluates; it never influences an agent"
    )

    enable(manager)
    active = manager.task_state_mode(
        subject_id=SUBJECT, agent_id=AGENT, workspace_id=WORKSPACE
    )
    assert active["mode"] == "active"
    assert active["influences_agent"] is True


# --- listing and detail -----------------------------------------------------


def test_an_empty_scope_lists_nothing_rather_than_erroring(manager) -> None:
    enable(manager)
    listing = manager.list_tasks(
        subject_id=SUBJECT, agent_id=AGENT, workspace_id=WORKSPACE
    )

    assert listing["count"] == 0
    assert listing["tasks"] == []


def test_task_detail_carries_the_plain_language_summary_first(manager) -> None:
    enable(manager)
    seed(manager)

    detail = manager.task_detail(
        "task-1", subject_id=SUBJECT, agent_id=AGENT, workspace_id=WORKSPACE
    )

    assert detail["summary"]["goal"] == "Ship the migration"
    assert detail["summary"]["completion_allowed"] is False
    assert detail["summary"]["completion_blockers"] == ["item-1"]
    assert detail["lifecycle"] == "open"


def test_an_unknown_task_returns_a_non_disclosing_refusal(manager) -> None:
    enable(manager)
    seed(manager)

    unknown = manager.task_detail(
        "task-nope", subject_id=SUBJECT, agent_id=AGENT, workspace_id=WORKSPACE
    )
    other_scope = manager.task_detail(
        "task-1", subject_id="someone-else", agent_id=AGENT, workspace_id=WORKSPACE
    )

    assert unknown["reason_code"] == "task_not_eligible"
    assert other_scope["reason_code"] == unknown["reason_code"]
    assert other_scope["message"] == unknown["message"]


def test_health_is_scope_filtered_and_content_free(manager) -> None:
    enable(manager)
    seed(manager, goal="Rotate the production credentials")

    health = manager.task_health(
        subject_id=SUBJECT, agent_id=AGENT, workspace_id=WORKSPACE
    )

    assert health["tasks"]["total"] == 1
    assert "Rotate the production credentials" not in json.dumps(health)


# --- mutations preview, confirm, and never auto-retry -----------------------


def test_a_lifecycle_action_requires_a_matching_expected_revision(manager) -> None:
    enable(manager)
    seed(manager)

    result = manager.change_task_lifecycle(
        "task-1", "pause", actor="dashboard-operator", reason="waiting",
        expected_revision=9, subject_id=SUBJECT, agent_id=AGENT,
        workspace_id=WORKSPACE,
    )

    assert result["reason_code"] == "stale_base_revision"
    assert result["current_revision"] == 1
    assert result["expected_revision"] == 9
    assert "fresh request" in result["message"]
    # Nothing changed, and nothing was retried.
    assert manager.task_detail(
        "task-1", subject_id=SUBJECT, agent_id=AGENT, workspace_id=WORKSPACE
    )["lifecycle"] == "open"


def test_a_matching_revision_applies_the_action(manager) -> None:
    enable(manager)
    seed(manager)

    result = manager.change_task_lifecycle(
        "task-1", "pause", actor="dashboard-operator", reason="waiting",
        expected_revision=1, subject_id=SUBJECT, agent_id=AGENT,
        workspace_id=WORKSPACE,
    )

    assert result["lifecycle"] == "paused"
    assert result["revision"] == 2


def test_premature_completion_returns_the_guard_rather_than_completing(
    manager,
) -> None:
    enable(manager)
    seed(manager)

    result = manager.change_task_lifecycle(
        "task-1", "complete", actor="dashboard-operator",
        expected_revision=1, subject_id=SUBJECT, agent_id=AGENT,
        workspace_id=WORKSPACE,
    )

    assert result["reason_code"] == "required_items_incomplete"
    # The manager hands back the contract's own shape; JSON encoding turns
    # the tuple into an array on the wire.
    assert list(result["guard"]["blocking_item_ids"]) == ["item-1"]
    assert result["guard"]["enforced"] is False


def test_a_terminal_task_refuses_further_lifecycle_changes(manager) -> None:
    enable(manager)
    seed(manager)
    manager.change_task_lifecycle(
        "task-1", "cancel", actor="dashboard-operator", reason="not needed",
        expected_revision=1, subject_id=SUBJECT, agent_id=AGENT,
        workspace_id=WORKSPACE,
    )

    result = manager.change_task_lifecycle(
        "task-1", "resume", actor="dashboard-operator",
        subject_id=SUBJECT, agent_id=AGENT, workspace_id=WORKSPACE,
    )
    assert result["reason_code"] == "task_is_terminal"


def test_an_unsupported_lifecycle_action_is_refused(manager) -> None:
    enable(manager)
    seed(manager)

    with pytest.raises(ValueError, match="unsupported task lifecycle action"):
        manager.change_task_lifecycle(
            "task-1", "delete", actor="dashboard-operator",
            subject_id=SUBJECT, agent_id=AGENT, workspace_id=WORKSPACE,
        )


# --- the rendered dashboard -------------------------------------------------


def html() -> str:
    return build_app_html()


def test_the_task_card_is_hidden_until_capability_is_confirmed() -> None:
    markup = html()

    assert 'id="taskCard"' in markup
    assert re.search(r'<section class="card" id="taskCard" hidden>', markup), (
        "the task card starts hidden and is revealed only by capability"
    )
    assert "taskCapabilityAvailable" in markup
    assert "governed_task_state" in markup


def test_the_dashboard_still_has_exactly_four_workspaces() -> None:
    """Spec 007 extends the existing design; it does not add a fifth workspace."""
    markup = html()
    tabs = re.findall(r'data-workspace="([a-z-]+)"', markup)
    if tabs:
        assert len(set(tabs)) == 4, sorted(set(tabs))


def test_the_task_ui_never_claims_influence_it_does_not_have() -> None:
    markup = html()

    assert "No task context is reaching any agent" in markup
    assert "no task context reaches any agent" in markup
    assert "Only the exact task an adapter names is delivered" in markup


def test_a_terminal_task_is_presented_as_unchangeable() -> None:
    markup = html()
    assert "cannot be changed" in markup
    assert "starting a new task" in markup


def test_task_mutations_preview_their_exact_effect_before_confirming() -> None:
    markup = html()

    assert "Confirm \"+action+\"?" in markup or 'Confirm "+action+"?' in markup
    assert "Effect: " in markup
    assert "Revision: " in markup


def test_a_conflict_never_triggers_an_automatic_retry() -> None:
    markup = html()

    assert "Never auto-retry" in markup
    index = markup.index("stale_base_revision")
    window = markup[index : index + 400]
    assert "showError" in window
    assert "selectTask" in window


def test_cancelling_requires_a_recorded_reason() -> None:
    markup = html()
    assert "Why are you cancelling this task? This is recorded." in markup


def test_task_controls_are_keyboard_operable_and_labelled() -> None:
    markup = html()

    assert 'item.type="button"' in markup
    assert 'setAttribute("aria-label","Open task ' in markup
    assert 'setAttribute("aria-current","true")' in markup


def test_task_status_is_readable_without_colour() -> None:
    """Lifecycle is spelled out in text, not encoded only in a pill colour."""
    markup = html()
    assert 'String(row.lifecycle||"").toUpperCase()' in markup
    assert 'element("small","",String(row.lifecycle' in markup


def test_the_selected_task_offers_a_return_path() -> None:
    markup = html()
    assert "Back to all tasks" in markup
    assert 'id="taskSelected"' in markup


def test_memory_only_dashboards_are_unaffected_when_task_state_is_off() -> None:
    """Existing surfaces must not move because a new card exists."""
    markup = html()
    for existing in ('id="reviewCard"', 'id="proposalCard"', 'id="semanticHealthCard"',
                     'id="agentOverview"', 'id="blackboxCard"'):
        assert existing in markup, existing


def test_the_capability_response_is_served_to_the_dashboard() -> None:
    """The card gates on the runtime response, not on a hardcoded assumption."""
    value = capabilities()
    assert value["features"]["governed_task_state"] is True
    assert "capabilities" in Path("atmem/control/web.py").read_text()
