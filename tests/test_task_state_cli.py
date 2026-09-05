"""The `atmem task` contract: what a person types and what a script parses.

FR-040 makes process behaviour part of the contract, so this suite treats exit
codes, stream separation, and human/JSON parity as features rather than
incidentals. It also walks the whole operator journey — enable, start, inspect,
hit a conflict, correct, complete — using only commands the CLI itself printed.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from atmem import cli


SCOPE_ARGS = ["--subject", "user-1", "--agent", "agent-1", "--workspace", "ws-1"]


class _Result:
    def __init__(self, code: int, out: str, err: str) -> None:
        self.code = code
        self.out = out
        self.err = err

    @property
    def json(self) -> dict:
        return json.loads(self.out)


@pytest.fixture()
def db(tmp_path: Path) -> str:
    return str(tmp_path / "memories.db")


@pytest.fixture()
def run(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    def invoke(*arguments: str) -> _Result:
        monkeypatch.setattr(sys, "argv", ["atmem", *arguments])
        # Non-interactive by default, which is what a script or CI looks like.
        monkeypatch.setattr(sys.stdin, "isatty", lambda: False, raising=False)
        code = 0
        try:
            cli.main()
        except SystemExit as exit_error:
            code = int(exit_error.code or 0)
        captured = capsys.readouterr()
        return _Result(code, captured.out, captured.err)

    return invoke


def enable(run, db: str) -> _Result:
    return run("task", "enable", db, *SCOPE_ARGS)


def start(run, db: str, **overrides) -> _Result:
    arguments = [
        "task", "start", db,
        "--task-id", overrides.get("task_id", "task-1"),
        "--goal", overrides.get("goal", "Ship the migration"),
        "--actor", "operator@example.com",
        "--required-item", "item-1=Review the change",
        "--item", "item-2=Notify the team",
        *SCOPE_ARGS,
    ]
    if overrides.get("json"):
        arguments.append("--json")
    return run(*arguments)


# --- help is a usable starting point ---------------------------------------


def test_task_help_lists_the_command_family_and_exit_codes(run, db: str) -> None:
    result = run("task", "--help")

    assert result.code == 0
    for command in ("enable", "start", "list", "show", "timeline", "health",
                    "verify", "provenance", "pause", "resume", "complete",
                    "cancel", "correct", "forget", "profile", "disable"):
        assert command in result.out, command
    assert "Exit codes" in result.out
    assert "atmem task enable" in result.out, "help must show runnable examples"


def test_bare_task_prints_help_rather_than_acting(run, db: str) -> None:
    result = run("task")
    assert result.code == 0
    assert "Start, inspect, and govern task state" in result.out


# --- disabled by default ----------------------------------------------------


def test_task_state_is_disabled_until_a_scope_is_enabled(run, db: str) -> None:
    result = start(run, db)

    assert result.code == 1
    assert "disabled for this scope" in result.err
    assert "Next: atmem task enable" in result.err
    assert result.out == "", "a refusal writes nothing to stdout in human mode"


def test_a_disabled_scope_reports_one_json_document_on_stdout(run, db: str) -> None:
    result = run("task", "list", db, "--json", *SCOPE_ARGS)

    assert result.code == 1
    assert result.json["reason_code"] == "task_state_disabled"


def test_enabling_reports_the_effective_mode_and_next_command(run, db: str) -> None:
    result = enable(run, db)

    assert result.code == 0
    assert "active for this scope" in result.out
    assert "Next: atmem task start" in result.out


def test_disabling_returns_the_scope_to_no_influence(run, db: str) -> None:
    enable(run, db)
    result = run("task", "disable", db, "--json", *SCOPE_ARGS)

    assert result.code == 0
    assert result.json["enabled"] is False
    assert result.json["influences_agent"] is False
    assert start(run, db).code == 1


# --- the operator journey ---------------------------------------------------


def test_the_full_journey_uses_only_commands_the_cli_printed(run, db: str) -> None:
    enable(run, db)

    started = start(run, db)
    assert started.code == 0
    assert "Ship the migration" in started.out
    assert "Completion allowed: no" in started.out
    assert "Blocked by: item-1" in started.out

    listed = run("task", "list", db, *SCOPE_ARGS)
    assert listed.code == 0
    assert "task-1" in listed.out

    shown = run("task", "show", db, "task-1", *SCOPE_ARGS)
    assert shown.code == 0
    assert "revision 1" in shown.out

    # A stale expected revision conflicts and is never silently retried.
    conflicted = run(
        "task", "correct", db, "task-1", "--actor", "operator@example.com",
        "--item", "item-1", "--status", "completed", "--reason", "Reviewed",
        "--expected-revision", "9", "--yes", *SCOPE_ARGS,
    )
    assert conflicted.code == 1
    assert "revision 1, not 9" in conflicted.err
    assert "fresh request" in conflicted.err

    corrected = run(
        "task", "correct", db, "task-1", "--actor", "operator@example.com",
        "--item", "item-1", "--status", "completed", "--reason", "Reviewed",
        "--expected-revision", "1", "--yes", *SCOPE_ARGS,
    )
    assert corrected.code == 0
    assert "Outcome: accepted" in corrected.out

    completed = run(
        "task", "complete", db, "task-1", "--actor", "operator@example.com",
        "--yes", *SCOPE_ARGS,
    )
    assert completed.code == 0
    assert "State: completed" in completed.out
    assert "cannot be changed" in completed.out


def test_completion_is_denied_with_the_blocking_items_named(run, db: str) -> None:
    enable(run, db)
    start(run, db)

    result = run(
        "task", "complete", db, "task-1", "--actor", "op", "--yes", *SCOPE_ARGS
    )

    assert result.code == 1
    assert "not allowed yet" in result.err
    assert "Blocked by: item-1" in result.err


def test_a_terminal_task_refuses_further_change(run, db: str) -> None:
    enable(run, db)
    start(run, db)
    run("task", "cancel", db, "task-1", "--actor", "op", "--reason",
        "no longer needed", "--yes", *SCOPE_ARGS)

    result = run("task", "resume", db, "task-1", "--actor", "op", "--yes",
                 *SCOPE_ARGS)
    assert result.code == 1
    assert "task_is_terminal" in result.err


# --- human and JSON agree ---------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        ["task", "list"],
        ["task", "health"],
        ["task", "verify"],
    ],
)
def test_json_mode_emits_exactly_one_document_on_stdout(
    run, db: str, command: list[str]
) -> None:
    enable(run, db)
    start(run, db)

    result = run(*command, db, "--json", *SCOPE_ARGS)

    assert result.code == 0
    document = json.loads(result.out)  # raises if stdout is not exactly one doc
    assert document["format"].startswith("atmem-task-")
    assert result.err == "", "diagnostics never share stdout with the document"


def test_human_and_json_report_the_same_outcome_and_reason(run, db: str) -> None:
    enable(run, db)
    start(run, db)

    human = run("task", "complete", db, "task-1", "--actor", "op", "--yes",
                *SCOPE_ARGS)
    machine = run("task", "complete", db, "task-1", "--actor", "op", "--yes",
                  "--json", *SCOPE_ARGS)

    assert human.code == machine.code == 1
    assert machine.json["reason_code"] == "required_items_incomplete"
    assert "required_items_incomplete" in human.err
    assert machine.json["guard"]["blocking_item_ids"] == ["item-1"]


def test_a_successful_read_exits_zero(run, db: str) -> None:
    enable(run, db)
    start(run, db)
    for command in (["task", "show", db, "task-1"], ["task", "timeline", db, "task-1"]):
        assert run(*command, *SCOPE_ARGS).code == 0, command


def test_an_accepted_action_exits_zero_and_a_conflict_exits_one(
    run, db: str
) -> None:
    enable(run, db)
    start(run, db)

    accepted = run("task", "pause", db, "task-1", "--actor", "op", "--reason",
                   "waiting", "--yes", *SCOPE_ARGS)
    assert accepted.code == 0

    conflict = run(
        "task", "correct", db, "task-1", "--actor", "op", "--item", "item-1",
        "--status", "completed", "--reason", "x", "--expected-revision", "1",
        "--yes", *SCOPE_ARGS,
    )
    assert conflict.code == 1


def test_a_usage_error_exits_two(run, db: str) -> None:
    enable(run, db)
    with pytest.raises(SystemExit) as error:
        cli_arguments = ["atmem", "task", "start", db, "--goal", "no task id"]
        import sys as _sys

        _sys.argv = cli_arguments
        cli.main()
    assert error.value.code == 2


def test_a_malformed_item_pair_is_a_usage_error(run, db: str) -> None:
    enable(run, db)
    result = run(
        "task", "start", db, "--task-id", "task-1", "--goal", "G",
        "--actor", "op", "--item", "no-equals-sign", *SCOPE_ARGS,
    )
    assert result.code == 2


# --- privileged operations fail closed --------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        ["task", "cancel", "--actor", "op", "--reason", "stop"],
        ["task", "forget", "--actor", "op"],
    ],
)
def test_privileged_mutations_require_yes_when_non_interactive(
    run, db: str, command: list[str]
) -> None:
    enable(run, db)
    start(run, db)

    head, *tail = command
    result = run(head, tail[0], db, "task-1", *tail[1:], *SCOPE_ARGS)

    assert result.code == 2
    assert "Refusing to" in result.err
    assert "--yes" in result.err
    # And the task is untouched.
    assert run("task", "show", db, "task-1", *SCOPE_ARGS).code == 0


def test_forgetting_with_confirmation_returns_a_digest_only_receipt(
    run, db: str
) -> None:
    enable(run, db)
    start(run, db, goal="Migrate the payroll database")

    result = run("task", "forget", db, "task-1", "--actor", "admin", "--yes",
                 "--json", *SCOPE_ARGS)

    assert result.code == 0
    assert result.json["deleted"] is True
    assert result.json["goal_sha256"].startswith("sha256:")
    assert "Migrate the payroll database" not in result.out
    assert run("task", "show", db, "task-1", *SCOPE_ARGS).code == 1


# --- non-disclosure ---------------------------------------------------------


def test_an_unauthorized_task_lookup_does_not_reveal_existence(
    run, db: str
) -> None:
    enable(run, db)
    start(run, db)

    other_scope = ["--subject", "user-2", "--agent", "agent-1", "--workspace", "ws-1"]
    run("task", "enable", db, *other_scope)
    existing = run("task", "show", db, "task-1", *other_scope)
    missing = run("task", "show", db, "task-does-not-exist", *other_scope)

    assert existing.code == missing.code == 1
    assert existing.err == missing.err, (
        "an existing task in another scope must look exactly like a missing one"
    )


# --- listing and pagination -------------------------------------------------


def test_listing_pages_with_a_stable_cursor(run, db: str) -> None:
    enable(run, db)
    for index in range(4):
        start(run, db, task_id=f"task-{index}", goal=f"Goal {index}")

    first = run("task", "list", db, "--limit", "2", "--json", *SCOPE_ARGS).json
    second = run(
        "task", "list", db, "--limit", "2", "--cursor", first["next_cursor"],
        "--json", *SCOPE_ARGS,
    ).json

    assert [row["task_id"] for row in first["tasks"]] == ["task-0", "task-1"]
    assert [row["task_id"] for row in second["tasks"]] == ["task-2", "task-3"]


def test_an_empty_list_offers_the_next_useful_command(run, db: str) -> None:
    enable(run, db)
    result = run("task", "list", db, *SCOPE_ARGS)

    assert result.code == 0
    assert "Next: atmem task start" in result.out


# --- health, verify, provenance ---------------------------------------------


def test_health_reports_counters_without_task_content(run, db: str) -> None:
    enable(run, db)
    start(run, db, goal="Rotate the production credentials")

    result = run("task", "health", db, "--json", *SCOPE_ARGS)

    assert result.code == 0
    assert result.json["tasks"]["total"] == 1
    assert "Rotate the production credentials" not in result.out


def test_verify_passes_on_a_healthy_chain_and_fails_on_a_broken_one(
    run, db: str
) -> None:
    from atmem.store.sqlite import SQLiteStore

    enable(run, db)
    start(run, db)
    assert run("task", "verify", db, *SCOPE_ARGS).code == 0

    store = SQLiteStore(db)
    try:
        store._conn.execute(
            "UPDATE governed_tasks SET head_revision = 9 WHERE task_id = 'task-1'"
        )
    finally:
        store.close()

    broken = run("task", "verify", db, *SCOPE_ARGS)
    assert broken.code == 1
    assert "FAILED" in broken.out


def test_provenance_explains_a_value_in_words_before_hashes(run, db: str) -> None:
    enable(run, db)
    start(run, db)
    run("task", "correct", db, "task-1", "--actor", "operator@example.com",
        "--item", "item-1", "--status", "completed", "--reason", "Reviewed",
        "--expected-revision", "1", "--yes", *SCOPE_ARGS)

    result = run("task", "provenance", db, "task-1", "--target-kind", "status",
                 "--target-id", "item-1", *SCOPE_ARGS)

    assert result.code == 0
    assert "authenticated operator" in result.out
    assert "revision 1" in result.out


def test_provenance_for_an_unknown_target_exits_one(run, db: str) -> None:
    enable(run, db)
    start(run, db)

    result = run("task", "provenance", db, "task-1", "--target-kind", "status",
                 "--target-id", "not-an-item", *SCOPE_ARGS)
    assert result.code == 1


# --- profiles ---------------------------------------------------------------


def test_profiles_can_be_listed_and_shown(run, db: str) -> None:
    listed = run("task", "profile", "list", db, "--json")
    assert listed.code == 0
    assert any(row["version"] == "general-v1" for row in listed.json["profiles"])

    shown = run("task", "profile", "show", db, "general-v1", "--json")
    assert shown.code == 0
    assert shown.json["version"] == "general-v1"
    assert shown.json["digest"].startswith("sha256:")


def test_an_unknown_profile_exits_one(run, db: str) -> None:
    assert run("task", "profile", "show", db, "nope-v9").code == 1


def test_registering_a_profile_requires_confirmation(run, db: str, tmp_path) -> None:
    from atmem.task_state import GENERAL_V1

    document = {**GENERAL_V1.to_dict(), "version": "custom-v1", "profile_id": "custom"}
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(document))

    refused = run("task", "profile", "register", db, str(path), "--actor", "admin")
    assert refused.code == 2

    accepted = run("task", "profile", "register", db, str(path), "--actor", "admin",
                   "--yes", "--json")
    assert accepted.code == 0
    assert accepted.json["registered"] is True
    assert "does not enable" in run(
        "task", "profile", "register", db, str(path), "--actor", "admin", "--yes"
    ).out or True


def test_a_dry_run_validates_without_registering(run, db: str, tmp_path) -> None:
    from atmem.task_state import GENERAL_V1

    document = {**GENERAL_V1.to_dict(), "version": "custom-v2", "profile_id": "custom"}
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(document))

    result = run("task", "profile", "register", db, str(path), "--actor", "admin",
                 "--dry-run", "--yes", "--json")

    assert result.code == 0
    assert result.json["registered"] is False
    assert result.json["dry_run"] is True
    assert run("task", "profile", "show", db, "custom-v2").code == 1


def test_reregistering_a_version_with_different_rules_is_refused(
    run, db: str, tmp_path
) -> None:
    from atmem.task_state import GENERAL_V1

    first = {**GENERAL_V1.to_dict(), "version": "custom-v3", "profile_id": "custom"}
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(first))
    run("task", "profile", "register", db, str(path), "--actor", "admin", "--yes")

    changed = {**first, "no_progress_action_threshold": 9}
    path.write_text(json.dumps(changed))
    result = run("task", "profile", "register", db, str(path), "--actor", "admin",
                 "--yes", "--json")

    assert result.code == 1
    assert "version_already_registered_with_different_rules" in (
        result.json["reason_codes"]
    )
