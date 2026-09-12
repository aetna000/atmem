"""Host-neutral, non-task execution identity contracts.

The M0 contract deliberately records only identifiers supplied by an
authenticated host boundary.  Missing levels stay missing; no identifier is
promoted to another level and no relationship is inferred from time or text.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Mapping

from atmem.contracts.models import AuthorityScope, Contract


_FIELDS = frozenset(
    {
        "format",
        "scope",
        "host",
        "framework",
        "session_id",
        "session_generation",
        "job_id",
        "execution_id",
        "parent_execution_id",
        "attempt_id",
        "retry_of_attempt_id",
        "run_id",
        "turn_id",
        "tool_call_id",
        "step_id",
        "task_id",
    }
)


def _text(name: str, value: str | None, *, required: bool = False) -> str | None:
    if value is None:
        if required:
            raise ValueError(f"{name} is required")
        return None
    result = str(value).strip()
    if not result or len(result) > 512 or any(ord(char) < 32 for char in result):
        raise ValueError(f"{name} must be a printable identifier of at most 512 characters")
    return result


@dataclass(frozen=True, slots=True)
class ExecutionIdentity(Contract):
    """An authenticated execution address with intentionally distinct levels."""

    format: ClassVar[str] = "atmem-execution-identity-v1"
    scope: AuthorityScope
    host: str
    framework: str | None = None
    session_id: str | None = None
    session_generation: str | None = None
    job_id: str | None = None
    execution_id: str | None = None
    parent_execution_id: str | None = None
    attempt_id: str | None = None
    retry_of_attempt_id: str | None = None
    run_id: str | None = None
    turn_id: str | None = None
    tool_call_id: str | None = None
    step_id: str | None = None
    task_id: None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "host", _text("host", self.host, required=True))
        for name in (
            "framework",
            "session_id",
            "session_generation",
            "job_id",
            "execution_id",
            "parent_execution_id",
            "attempt_id",
            "retry_of_attempt_id",
            "run_id",
            "turn_id",
            "tool_call_id",
            "step_id",
        ):
            object.__setattr__(self, name, _text(name, getattr(self, name)))
        if self.session_generation is not None and self.session_id is None:
            raise ValueError("session_generation requires session_id")
        if self.parent_execution_id is not None and self.execution_id is None:
            raise ValueError("parent_execution_id requires execution_id")
        if self.retry_of_attempt_id is not None and self.attempt_id is None:
            raise ValueError("retry_of_attempt_id requires attempt_id")
        if self.task_id is not None:
            raise ValueError("the M0 non-task identity cannot contain task_id")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ExecutionIdentity":
        unknown = set(value) - _FIELDS
        if unknown:
            raise ValueError(f"unsupported execution identity field(s): {', '.join(sorted(unknown))}")
        if value.get("format") not in (None, cls.format):
            raise ValueError("unsupported execution identity format")
        raw_scope = value.get("scope")
        if not isinstance(raw_scope, Mapping):
            raise ValueError("scope is required")
        scope = AuthorityScope(
            subject_id=str(raw_scope.get("subject_id") or ""),
            agent_id=str(raw_scope.get("agent_id") or ""),
            workspace_id=str(raw_scope.get("workspace_id") or ""),
        )
        return cls(
            scope=scope,
            **{name: value.get(name) for name in _FIELDS - {"format", "scope"}},
        )
