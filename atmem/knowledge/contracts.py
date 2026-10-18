"""Versioned source and experience contracts, never independent authority."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import PurePosixPath
import re
from typing import Any

from atmem.code.contracts import CodeScope, _closed, _id, _sha256
from atmem.core.canonical import canonical_json
from atmem.extract.validation import screen_content


def source_path(value: Any) -> str:
    if (not isinstance(value, str) or not value or len(value.encode()) > 1024
            or "\\" in value or any(ord(char) < 0x20 or ord(char) == 0x7f for char in value)
            or ":" in value):
        raise ValueError("invalid source path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or str(path) != value or value == ".":
        raise ValueError("source path must be normalized and repository-relative")
    if not screen_content(value, trusted=True).admissible:
        raise ValueError("source path is not admissible")
    return value


def text(value: Any, name: str, maximum: int = 4000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.encode()) > maximum:
        raise ValueError(f"invalid {name}")
    if not screen_content(value, trusted=True).admissible:
        raise ValueError(f"inadmissible {name}")
    return value


def stable_digest(value: Any) -> str:
    return sha256(canonical_json(value).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class SourceAnchor:
    path: str
    content_sha256: str
    start_line: int
    end_line: int
    format = "atmem-source-anchor-v1"

    def __post_init__(self):
        source_path(self.path)
        _sha256("content_sha256", self.content_sha256)
        if type(self.start_line) is not int or type(self.end_line) is not int or not 1 <= self.start_line <= self.end_line <= 10_000_000:
            raise ValueError("invalid source range")

    def to_dict(self):
        return {"format": self.format, "path": self.path, "content_sha256": self.content_sha256,
                "start_line": self.start_line, "end_line": self.end_line}

    @classmethod
    def from_dict(cls, value):
        r = _closed(value, {"path", "content_sha256", "start_line", "end_line"}, cls.format)
        return cls(r["path"], r["content_sha256"], r["start_line"], r["end_line"])


@dataclass(frozen=True, slots=True)
class SourceSnapshot:
    scope: CodeScope
    worktree_id: str
    revision: str
    files: tuple[tuple[str, str], ...]
    configuration_sha256: str
    format = "atmem-source-snapshot-v1"

    def __post_init__(self):
        if not isinstance(self.scope, CodeScope):
            raise ValueError("CodeScope required")
        _id("worktree_id", self.worktree_id)
        if not isinstance(self.revision, str) or not re.fullmatch(r"[0-9a-f]{40,64}", self.revision):
            _id("revision", self.revision)
        _sha256("configuration_sha256", self.configuration_sha256)
        if not isinstance(self.files, tuple) or not 1 <= len(self.files) <= 5000:
            raise ValueError("bounded nonempty file manifest required")
        paths = []
        for item in self.files:
            if not isinstance(item, tuple) or len(item) != 2:
                raise ValueError("invalid file manifest entry")
            path, digest = item
            paths.append(source_path(path))
            _sha256("file_sha256", digest)
        if paths != sorted(set(paths)):
            raise ValueError("file manifest must be sorted and unique")

    def to_dict(self):
        return {"format": self.format, "scope": self.scope.to_dict(), "worktree_id": self.worktree_id,
                "revision": self.revision, "files": [list(item) for item in self.files],
                "configuration_sha256": self.configuration_sha256}

    @property
    def snapshot_id(self):
        return stable_digest(self.to_dict())

    @classmethod
    def from_dict(cls, value):
        r = _closed(value, {"scope", "worktree_id", "revision", "files", "configuration_sha256"}, cls.format)
        if type(r["files"]) is not list or any(type(v) is not list or len(v) != 2 for v in r["files"]):
            raise ValueError("invalid file manifest")
        return cls(CodeScope.from_dict(r["scope"]), r["worktree_id"], r["revision"],
                   tuple(tuple(v) for v in r["files"]), r["configuration_sha256"])


@dataclass(frozen=True, slots=True)
class ExecutionReceipt:
    receipt_id: str
    scope: CodeScope
    producer_id: str
    attempt_id: str
    snapshot_id: str
    environment_sha256: str
    command: tuple[str, ...]
    exit_code: int | None
    result_sha256: str
    evidence_id: str
    format = "atmem-code-execution-receipt-v1"

    def __post_init__(self):
        for name in ("receipt_id", "producer_id", "attempt_id", "evidence_id"):
            _id(name, getattr(self, name))
        if not isinstance(self.scope, CodeScope):
            raise ValueError("CodeScope required")
        for name in ("snapshot_id", "environment_sha256", "result_sha256"):
            _sha256(name, getattr(self, name))
        if not isinstance(self.command, tuple) or not 1 <= len(self.command) <= 128:
            raise ValueError("bounded command argv required")
        for argument in self.command:
            text(argument, "command argument", 2048)
        if self.exit_code is not None and (type(self.exit_code) is not int or not -255 <= self.exit_code <= 255):
            raise ValueError("invalid exit code")

    def to_dict(self):
        return {"format": self.format, "scope": self.scope.to_dict(), "receipt_id": self.receipt_id,
                "producer_id": self.producer_id, "attempt_id": self.attempt_id, "snapshot_id": self.snapshot_id,
                "environment_sha256": self.environment_sha256, "command": list(self.command),
                "exit_code": self.exit_code, "result_sha256": self.result_sha256, "evidence_id": self.evidence_id}

    @property
    def digest(self):
        return stable_digest(self.to_dict())

    @classmethod
    def from_dict(cls, value):
        r = _closed(value, {"scope", "receipt_id", "producer_id", "attempt_id", "snapshot_id",
                           "environment_sha256", "command", "exit_code", "result_sha256", "evidence_id"}, cls.format)
        if type(r["command"]) is not list:
            raise ValueError("command argv must be a list")
        return cls(r["receipt_id"], CodeScope.from_dict(r["scope"]), r["producer_id"], r["attempt_id"],
                   r["snapshot_id"], r["environment_sha256"], tuple(r["command"]), r["exit_code"],
                   r["result_sha256"], r["evidence_id"])


@dataclass(frozen=True, slots=True)
class ExperienceProposal:
    proposal_id: str
    scope: CodeScope
    snapshot_id: str
    intent: str
    observation: str
    outcome: str
    anchors: tuple[SourceAnchor, ...]
    receipt_ids: tuple[str, ...]
    format = "atmem-code-experience-proposal-v1"

    def __post_init__(self):
        _id("proposal_id", self.proposal_id)
        if not isinstance(self.scope, CodeScope):
            raise ValueError("CodeScope required")
        _sha256("snapshot_id", self.snapshot_id)
        text(self.intent, "intent", 2000)
        text(self.observation, "observation", 2000)
        if self.outcome not in ("asserted", "observed_pass", "observed_failure", "unknown"):
            raise ValueError("invalid outcome assurance")
        if not isinstance(self.anchors, tuple) or not 1 <= len(self.anchors) <= 64 or any(not isinstance(v, SourceAnchor) for v in self.anchors):
            raise ValueError("bounded source anchors required")
        if not isinstance(self.receipt_ids, tuple) or len(self.receipt_ids) > 64:
            raise ValueError("invalid receipt identities")
        for item in self.receipt_ids:
            _id("receipt_id", item)
        if len(set(self.receipt_ids)) != len(self.receipt_ids):
            raise ValueError("duplicate receipt identities")
        if self.outcome.startswith("observed_") and not self.receipt_ids:
            raise ValueError("observed outcome requires execution receipts")

    def to_dict(self):
        return {"format": self.format, "proposal_id": self.proposal_id, "scope": self.scope.to_dict(),
                "snapshot_id": self.snapshot_id, "intent": self.intent, "observation": self.observation,
                "outcome": self.outcome, "anchors": [a.to_dict() for a in self.anchors], "receipt_ids": list(self.receipt_ids)}

    @classmethod
    def from_dict(cls, value):
        r = _closed(value, {"proposal_id", "scope", "snapshot_id", "intent", "observation", "outcome", "anchors", "receipt_ids"}, cls.format)
        if type(r["anchors"]) is not list or type(r["receipt_ids"]) is not list:
            raise ValueError("anchors and receipts must be lists")
        return cls(r["proposal_id"], CodeScope.from_dict(r["scope"]), r["snapshot_id"], r["intent"], r["observation"],
                   r["outcome"], tuple(SourceAnchor.from_dict(a) for a in r["anchors"]), tuple(r["receipt_ids"]))


FACT_KINDS = frozenset({"repository", "module", "symbol", "route", "storage", "dependency",
                        "service", "test_ref", "file_ref", "insight", "intent", "extraction", "association", "lint"})


@dataclass(frozen=True, slots=True)
class StructuralObject:
    object_id: str
    scope: CodeScope
    snapshot_id: str
    kind: str
    name: str
    anchors: tuple[SourceAnchor, ...]
    assurance: str
    format = "atmem-structural-object-v1"

    def __post_init__(self):
        _id("object_id", self.object_id)
        if not isinstance(self.scope, CodeScope):
            raise ValueError("CodeScope required")
        _sha256("snapshot_id", self.snapshot_id)
        if not isinstance(self.kind, str) or self.kind not in FACT_KINDS:
            raise ValueError("unknown structural kind")
        text(self.name, "structural name", 2000)
        if not isinstance(self.anchors, tuple) or len(self.anchors) > 64 or any(not isinstance(a, SourceAnchor) for a in self.anchors):
            raise ValueError("invalid anchors")
        if self.assurance not in ("syntax", "resolver", "declared", "heuristic", "unresolved"):
            raise ValueError("unknown structural assurance")

    def to_dict(self):
        return {"format": self.format, "object_id": self.object_id, "scope": self.scope.to_dict(),
                "snapshot_id": self.snapshot_id, "kind": self.kind, "name": self.name,
                "anchors": [a.to_dict() for a in self.anchors], "assurance": self.assurance}

    @classmethod
    def from_dict(cls, value):
        r = _closed(value, {"object_id", "scope", "snapshot_id", "kind", "name", "anchors", "assurance"}, cls.format)
        if type(r["anchors"]) is not list:
            raise ValueError("anchors must be a list")
        return cls(r["object_id"], CodeScope.from_dict(r["scope"]), r["snapshot_id"], r["kind"], r["name"],
                   tuple(SourceAnchor.from_dict(a) for a in r["anchors"]), r["assurance"])


@dataclass(frozen=True, slots=True)
class StructuralRelation:
    source_id: str
    target_id: str | None
    kind: str
    target_name: str
    assurance: str
    format = "atmem-structural-relation-v1"

    def __post_init__(self):
        _id("source_id", self.source_id)
        if self.target_id is not None:
            _id("target_id", self.target_id)
        _id("relation_kind", self.kind)
        text(self.target_name, "target name", 2000)
        if self.assurance not in ("syntax", "resolver", "declared", "heuristic", "unresolved"):
            raise ValueError("unknown relation assurance")
        if self.target_id is None and self.assurance != "unresolved":
            raise ValueError("missing target must remain unresolved")

    def to_dict(self):
        return {"format": self.format, "source_id": self.source_id, "target_id": self.target_id,
                "kind": self.kind, "target_name": self.target_name, "assurance": self.assurance}

    @classmethod
    def from_dict(cls, value):
        r = _closed(value, {"source_id", "target_id", "kind", "target_name", "assurance"}, cls.format)
        return cls(r["source_id"], r["target_id"], r["kind"], r["target_name"], r["assurance"])


@dataclass(frozen=True, slots=True)
class ApplicabilityReceipt:
    proposal_id: str
    evaluated_snapshot_id: str
    status: str
    reason_codes: tuple[str, ...]
    format = "atmem-code-applicability-v1"

    def __post_init__(self):
        _id("proposal_id", self.proposal_id)
        _sha256("evaluated_snapshot_id", self.evaluated_snapshot_id)
        if self.status not in ("applicable", "withheld", "review"):
            raise ValueError("invalid applicability status")
        if not isinstance(self.reason_codes, tuple) or not 1 <= len(self.reason_codes) <= 32:
            raise ValueError("bounded reason codes required")
        for reason in self.reason_codes:
            _id("reason_code", reason)

    def to_dict(self):
        return {"format": self.format, "proposal_id": self.proposal_id,
                "evaluated_snapshot_id": self.evaluated_snapshot_id, "status": self.status,
                "reason_codes": list(self.reason_codes)}

    @classmethod
    def from_dict(cls, value):
        r = _closed(value, {"proposal_id", "evaluated_snapshot_id", "status", "reason_codes"}, cls.format)
        if type(r["reason_codes"]) is not list:
            raise ValueError("reason_codes must be a list")
        return cls(r["proposal_id"], r["evaluated_snapshot_id"], r["status"], tuple(r["reason_codes"]))


@dataclass(frozen=True, slots=True)
class CapabilityReceipt:
    build_sha256: str
    configuration_sha256: str
    scope: CodeScope
    capabilities: tuple[tuple[str, str], ...]
    evidence_sha256: str
    format = "atmem-knowledge-capability-v1"

    def __post_init__(self):
        for field in ("build_sha256", "configuration_sha256", "evidence_sha256"):
            _sha256(field, getattr(self, field))
        if not isinstance(self.scope, CodeScope):
            raise ValueError("CodeScope required")
        if not isinstance(self.capabilities, tuple) or not 1 <= len(self.capabilities) <= 128:
            raise ValueError("bounded capability cells required")
        names = []
        for item in self.capabilities:
            if not isinstance(item, tuple) or len(item) != 2:
                raise ValueError("invalid capability cell")
            name, status = item
            _id("capability", name)
            if status not in ("verified", "partial", "unsupported", "unverified"):
                raise ValueError("invalid capability status")
            names.append(name)
        if names != sorted(set(names)):
            raise ValueError("capability cells must be sorted and unique")

    def to_dict(self):
        return {"format": self.format, "build_sha256": self.build_sha256,
                "configuration_sha256": self.configuration_sha256, "scope": self.scope.to_dict(),
                "capabilities": [list(c) for c in self.capabilities], "evidence_sha256": self.evidence_sha256}

    @classmethod
    def from_dict(cls, value):
        r = _closed(value, {"build_sha256", "configuration_sha256", "scope", "capabilities", "evidence_sha256"}, cls.format)
        if type(r["capabilities"]) is not list or any(type(c) is not list or len(c) != 2 for c in r["capabilities"]):
            raise ValueError("invalid capability cells")
        return cls(r["build_sha256"], r["configuration_sha256"], CodeScope.from_dict(r["scope"]),
                   tuple(tuple(c) for c in r["capabilities"]), r["evidence_sha256"])
