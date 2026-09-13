from __future__ import annotations

import pytest
import json
from pathlib import Path

from atmem.contracts.execution import ExecutionIdentity
from atmem.contracts.models import AuthorityScope


def test_non_task_execution_identity_preserves_every_supplied_level() -> None:
    identity = ExecutionIdentity(
        scope=AuthorityScope("subject-1", "agent-1", "workspace-1"),
        host="openclaw",
        framework="openclaw",
        session_id="session-1",
        session_generation="generation-2",
        execution_id="execution-1",
        parent_execution_id="execution-parent",
        attempt_id="attempt-2",
        retry_of_attempt_id="attempt-1",
        run_id="run-1",
        turn_id="turn-1",
        tool_call_id="call-1",
    )
    value = identity.to_dict()
    assert value["format"] == "atmem-execution-identity-v1"
    assert value["execution_id"] != value["run_id"] != value["turn_id"]
    assert value["task_id"] is None
    assert ExecutionIdentity.from_dict(value) == identity


def test_non_task_identity_never_fills_or_accepts_other_identity_levels() -> None:
    scope = AuthorityScope("subject-1", "agent-1", "workspace-1")
    identity = ExecutionIdentity(scope=scope, host="generic", run_id="only-run")
    assert identity.execution_id is None
    assert identity.turn_id is None
    with pytest.raises(ValueError, match="session_generation requires"):
        ExecutionIdentity(scope=scope, host="generic", session_generation="2")
    with pytest.raises(ValueError, match="non-task"):
        ExecutionIdentity.from_dict(
            {"scope": scope.to_dict(), "host": "generic", "task_id": "task-1"}
        )
    with pytest.raises(ValueError, match="unsupported execution identity field"):
        ExecutionIdentity.from_dict(
            {"scope": scope.to_dict(), "host": "generic", "authority": "caller"}
        )


def test_execution_identity_stores_normalized_identifiers() -> None:
    identity = ExecutionIdentity(
        scope=AuthorityScope("subject-1", "agent-1", "workspace-1"),
        host="  generic  ",
        execution_id="  execution-1  ",
    )
    assert identity.host == "generic"
    assert identity.execution_id == "execution-1"


def test_frozen_m0_identity_vectors() -> None:
    root = Path(__file__).parent / "fixtures/product/020"
    assert ExecutionIdentity.from_dict(json.loads((root / "execution-identity-valid.json").read_text())).execution_id == "execution-1"
    with pytest.raises(ValueError):
        ExecutionIdentity.from_dict(json.loads((root / "execution-identity-invalid.json").read_text()))
    scope = json.loads((root / "m0-scope.json").read_text())
    assert len(scope["in_scope"]) == 10
    assert "measured-human-usability" in scope["deferred"]
