"""Closed, versioned JSON contracts shared by coding-agent adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import re
from typing import Any, Literal


_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,127}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_HOSTS = frozenset({"muse", "claude", "grok", "copilot", "codex", "test"})
_KINDS = frozenset({"user_turn", "tool_outcome", "task_outcome"})
_ASSURANCE = frozenset({"submitted", "host_acknowledged", "model_input_observed"})


def _closed(value: Any, fields: set[str], format_id: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields | {"format"}:
        raise ValueError(f"{format_id} fields do not match the contract")
    if value["format"] != format_id:
        raise ValueError(f"unsupported {format_id} format")
    return value


def _id(name: str, value: Any) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError(f"{name} must be a bounded opaque identifier")
    return value


def _text(name: str, value: Any, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.encode("utf-8")) > limit:
        raise ValueError(f"{name} must be nonempty UTF-8 within {limit} bytes")
    return value


def _timestamp(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("observed_at must be a timezone-aware ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("observed_at must be a timezone-aware ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("observed_at must include a timezone")
    return value


def _sha256(name: str, value: Any) -> str:
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise ValueError(f"{name} must be 64 lowercase hexadecimal characters")
    return value


@dataclass(frozen=True, slots=True)
class CodeScope:
    """One local authorized project lane; no name-based cross-user sharing."""

    subject_id: str
    project_id: str
    profile_id: str
    agent_id: str

    format = "atmem-code-scope-v1"

    def __post_init__(self) -> None:
        for name in ("subject_id", "project_id", "profile_id", "agent_id"):
            _id(name, getattr(self, name))

    def to_dict(self) -> dict[str, str]:
        return {"format": self.format, "subject_id": self.subject_id,
                "project_id": self.project_id, "profile_id": self.profile_id,
                "agent_id": self.agent_id}

    @classmethod
    def from_dict(cls, value: Any) -> "CodeScope":
        row = _closed(value, {"subject_id", "project_id", "profile_id", "agent_id"}, cls.format)
        return cls(row["subject_id"], row["project_id"], row["profile_id"], row["agent_id"])


@dataclass(frozen=True, slots=True)
class CodeObservation:
    event_id: str
    session_id: str
    turn_id: str
    host: str
    kind: Literal["user_turn", "tool_outcome", "task_outcome"]
    content: str
    observed_at: str
    source_ref: str
    git_revision: str | None
    scope: CodeScope

    format = "atmem-code-observation-v1"

    def __post_init__(self) -> None:
        for name in ("event_id", "session_id", "turn_id"):
            _id(name, getattr(self, name))
        if self.host not in _HOSTS or self.kind not in _KINDS:
            raise ValueError("unsupported code host or observation kind")
        _text("content", self.content, 32_768)
        _timestamp(self.observed_at)
        _text("source_ref", self.source_ref, 1_024)
        if self.git_revision is not None:
            if not isinstance(self.git_revision, str) or not re.fullmatch(r"[0-9a-f]{7,64}", self.git_revision):
                _id("git_revision", self.git_revision)
        if not isinstance(self.scope, CodeScope):
            raise ValueError("scope must be a CodeScope")

    @property
    def content_sha256(self) -> str:
        return sha256(self.content.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {"format": self.format, "event_id": self.event_id,
                "session_id": self.session_id, "turn_id": self.turn_id,
                "host": self.host, "kind": self.kind, "content": self.content,
                "observed_at": self.observed_at, "source_ref": self.source_ref,
                "git_revision": self.git_revision, "scope": self.scope.to_dict()}

    @classmethod
    def from_dict(cls, value: Any) -> "CodeObservation":
        row = _closed(value, {"event_id", "session_id", "turn_id", "host", "kind", "content",
                              "observed_at", "source_ref", "git_revision", "scope"}, cls.format)
        return cls(row["event_id"], row["session_id"], row["turn_id"], row["host"],
                   row["kind"], row["content"], row["observed_at"], row["source_ref"],
                   row["git_revision"], CodeScope.from_dict(row["scope"]))


@dataclass(frozen=True, slots=True)
class CodeMemoryCandidate:
    observation_id: str
    content: str
    memory_class: Literal["preference", "project_fact", "decision", "workflow", "failure_fix"]
    source_sha256: str
    scope: CodeScope

    format = "atmem-code-memory-candidate-v1"

    def __post_init__(self) -> None:
        _id("observation_id", self.observation_id)
        _text("content", self.content, 2_000)
        if self.memory_class not in {"preference", "project_fact", "decision", "workflow", "failure_fix"}:
            raise ValueError("unsupported memory class")
        _sha256("source_sha256", self.source_sha256)
        if not isinstance(self.scope, CodeScope):
            raise ValueError("scope must be a CodeScope")

    def to_dict(self) -> dict[str, Any]:
        return {"format": self.format, "observation_id": self.observation_id,
                "content": self.content, "memory_class": self.memory_class,
                "source_sha256": self.source_sha256, "scope": self.scope.to_dict()}


@dataclass(frozen=True, slots=True)
class CodeContextRequest:
    request_id: str
    session_id: str
    turn_id: str
    task: str
    max_context_bytes: int
    scope: CodeScope

    format = "atmem-code-context-request-v1"

    def __post_init__(self) -> None:
        for name in ("request_id", "session_id", "turn_id"):
            _id(name, getattr(self, name))
        _text("task", self.task, 8_192)
        if type(self.max_context_bytes) is not int or not 256 <= self.max_context_bytes <= 32_768:
            raise ValueError("max_context_bytes must be between 256 and 32768")
        if not isinstance(self.scope, CodeScope):
            raise ValueError("scope must be a CodeScope")

    def to_dict(self) -> dict[str, Any]:
        return {"format": self.format, "request_id": self.request_id,
                "session_id": self.session_id, "turn_id": self.turn_id,
                "task": self.task, "max_context_bytes": self.max_context_bytes,
                "scope": self.scope.to_dict()}

    @classmethod
    def from_dict(cls, value: Any) -> "CodeContextRequest":
        row = _closed(value, {"request_id", "session_id", "turn_id", "task",
                              "max_context_bytes", "scope"}, cls.format)
        return cls(row["request_id"], row["session_id"], row["turn_id"], row["task"],
                   row["max_context_bytes"], CodeScope.from_dict(row["scope"]))


@dataclass(frozen=True, slots=True)
class CodeContextPackage:
    request_id: str
    content: str
    content_sha256: str
    memory_ids: tuple[str, ...]

    format = "atmem-code-context-package-v1"

    def __post_init__(self) -> None:
        _id("request_id", self.request_id)
        if not isinstance(self.content, str) or len(self.content.encode("utf-8")) > 32_768:
            raise ValueError("context package exceeds 32768 bytes")
        _sha256("content_sha256", self.content_sha256)
        if sha256(self.content.encode("utf-8")).hexdigest() != self.content_sha256:
            raise ValueError("context content digest mismatch")
        if not isinstance(self.memory_ids, tuple) or len(self.memory_ids) > 128:
            raise ValueError("memory_ids must be a bounded tuple")
        for item in self.memory_ids:
            _id("memory_id", item)

    def to_dict(self) -> dict[str, Any]:
        return {"format": self.format, "request_id": self.request_id,
                "content": self.content, "content_sha256": self.content_sha256,
                "memory_ids": list(self.memory_ids)}


@dataclass(frozen=True, slots=True)
class CodeExposureReceipt:
    request_id: str
    content_sha256: str
    assurance: Literal["submitted", "host_acknowledged", "model_input_observed"]
    host: str

    format = "atmem-code-exposure-v1"

    def __post_init__(self) -> None:
        _id("request_id", self.request_id)
        _sha256("content_sha256", self.content_sha256)
        if self.assurance not in _ASSURANCE or self.host not in _HOSTS:
            raise ValueError("unsupported exposure assurance or host")

    def to_dict(self) -> dict[str, str]:
        return {"format": self.format, "request_id": self.request_id,
                "content_sha256": self.content_sha256, "assurance": self.assurance,
                "host": self.host}


@dataclass(frozen=True, slots=True)
class CodeDeletionReceipt:
    operation_id: str
    project_id: str
    deleted_count: int
    derived_verified: bool

    format = "atmem-code-deletion-v1"

    def __post_init__(self) -> None:
        _id("operation_id", self.operation_id)
        _id("project_id", self.project_id)
        if type(self.deleted_count) is not int or self.deleted_count < 0:
            raise ValueError("deleted_count must be nonnegative")
        if type(self.derived_verified) is not bool:
            raise ValueError("derived_verified must be boolean")

    def to_dict(self) -> dict[str, Any]:
        return {"format": self.format, "operation_id": self.operation_id,
                "project_id": self.project_id, "deleted_count": self.deleted_count,
                "derived_verified": self.derived_verified}


@dataclass(frozen=True, slots=True)
class CodeError:
    request_id: str
    code: Literal["UNAUTHORIZED", "SCOPE_MISMATCH", "INVALID_INPUT", "RETRY_CONFLICT",
                  "QUEUE_FULL", "DISABLED", "STORAGE_UNPROTECTED"]
    retryable: bool

    format = "atmem-code-error-v1"

    def __post_init__(self) -> None:
        _id("request_id", self.request_id)
        if self.code not in {"UNAUTHORIZED", "SCOPE_MISMATCH", "INVALID_INPUT",
                             "RETRY_CONFLICT", "QUEUE_FULL", "DISABLED", "STORAGE_UNPROTECTED"}:
            raise ValueError("unsupported code error")
        if type(self.retryable) is not bool:
            raise ValueError("retryable must be boolean")

    def to_dict(self) -> dict[str, Any]:
        return {"format": self.format, "request_id": self.request_id,
                "code": self.code, "retryable": self.retryable}

    @classmethod
    def from_dict(cls, value: Any) -> "CodeError":
        row = _closed(value, {"request_id", "code", "retryable"}, cls.format)
        return cls(row["request_id"], row["code"], row["retryable"])
