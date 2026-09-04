"""The published semantic-health schema must govern real payloads.

A checked-in schema that nothing validates against can drift from the code it
describes, which is exactly the CLI/dashboard divergence FR-005 exists to
prevent. These tests keep it load-bearing without adding a runtime dependency.
"""

from __future__ import annotations

import json
from pathlib import Path
import re

import pytest

from atmem.semantic.health import (
    SemanticHealthReason,
    SemanticHealthStatus,
    evaluate_semantic_health,
)

SCHEMA_PATH = Path(__file__).parents[1] / "atmem/schemas/v1/semantic-health.json"


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _validate(value, schema: dict, path: str = "$") -> list[str]:
    """Validate the subset of JSON Schema the semantic-health document uses."""

    errors: list[str] = []
    if "oneOf" in schema:
        matches = [
            branch for branch in schema["oneOf"] if not _validate(value, branch, path)
        ]
        if len(matches) != 1:
            errors.append(f"{path}: matched {len(matches)} oneOf branches, expected 1")
        return errors
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: {value!r} != const {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} not in enum")
    types = {
        "object": dict,
        "array": list,
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "null": type(None),
    }
    expected = schema.get("type")
    if expected:
        names = [expected] if isinstance(expected, str) else list(expected)
        kinds = tuple(
            kind
            for name in names
            for kind in (
                types[name] if isinstance(types[name], tuple) else (types[name],)
            )
        )
        if names == ["integer"] and isinstance(value, bool):
            errors.append(f"{path}: bool is not an integer")
        elif not isinstance(value, kinds):
            errors.append(f"{path}: {type(value).__name__} is not {'|'.join(names)}")
            return errors
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: shorter than minLength")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{path}: {value!r} does not match pattern")
    if isinstance(value, int) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: below minimum")
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: fewer than minItems")
        if schema.get("uniqueItems") and len(value) != len(set(map(str, value))):
            errors.append(f"{path}: items are not unique")
        for position, item in enumerate(value):
            if "items" in schema:
                errors.extend(_validate(item, schema["items"], f"{path}[{position}]"))
    if isinstance(value, dict):
        for name in schema.get("required", []):
            if name not in value:
                errors.append(f"{path}: missing required {name!r}")
        for name, subschema in schema.get("properties", {}).items():
            if name in value:
                errors.extend(_validate(value[name], subschema, f"{path}.{name}"))
    return errors


def _epoch(**changes) -> dict:
    identity = {
        "provider": "sentence-transformers",
        "model": "BAAI/bge-small-en-v1.5",
        "version": "1",
        "normalization": "l2",
        "policy_sha256": "e" * 64,
    }
    value = {
        "epoch_id": "vidx_1",
        "subject_id": "user-1",
        "provider": identity["provider"],
        "model": identity["model"],
        "model_version": identity["version"],
        "identity": identity,
        "identity_sha256": "a" * 64,
        "dimensions": 384,
        "status": "active",
        "dirty": 0,
        "entry_count": 3,
        "created_at": "2026-09-05T00:00:00Z",
    }
    value.update(changes)
    return value


def _health(epoch=None, **kwargs):
    active = _epoch() if epoch is None else epoch
    kwargs.setdefault("verification", {"valid": True, "report_sha256": "b" * 64})
    kwargs.setdefault("epochs", [active] if active else [])
    return evaluate_semantic_health(
        "user-1",
        active_epoch=active,
        source_sha256=f"sha256:{'c' * 64}",
        canonical_generation=4,
        **kwargs,
    )


ALL_STATES = {
    SemanticHealthStatus.MISSING: evaluate_semantic_health("user-1", active_epoch=None),
    SemanticHealthStatus.REBUILDING: evaluate_semantic_health(
        "user-1", active_epoch=None, epochs=[{"status": "building"}]
    ),
    SemanticHealthStatus.LEGACY: _health(_epoch(identity_sha256=None)),
    SemanticHealthStatus.WEAK: _health(
        _epoch(
            provider="hashing-diagnostic",
            identity={
                "provider": "hashing-diagnostic",
                "model": "blake2b-token-v1",
                "version": "1",
                "normalization": "l2",
            },
        )
    ),
    SemanticHealthStatus.STALE: _health(_epoch(dirty=1)),
    SemanticHealthStatus.INCOMPATIBLE: _health(_epoch(dimensions=0)),
    SemanticHealthStatus.HEALTHY: _health(),
}


@pytest.mark.parametrize("status", list(SemanticHealthStatus))
def test_every_health_state_validates_against_published_schema(status) -> None:
    health = ALL_STATES[status]
    assert health.status is status
    assert _validate(health.to_dict(), _schema()) == []


def test_schema_enums_match_the_implementation_exactly() -> None:
    schema = _schema()
    assert set(schema["properties"]["status"]["enum"]) == {
        member.value for member in SemanticHealthStatus
    }
    assert set(schema["properties"]["reasons"]["items"]["enum"]) == {
        member.value for member in SemanticHealthReason
    }


def test_validator_rejects_a_payload_outside_the_schema() -> None:
    payload = ALL_STATES[SemanticHealthStatus.HEALTHY].to_dict()
    payload["status"] = "excellent"
    assert _validate(payload, _schema()) != []
