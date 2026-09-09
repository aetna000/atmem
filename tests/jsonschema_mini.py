"""A small JSON Schema checker for the subset AtMem's schemas actually use.

AtMem ships schemas as public contracts but takes no runtime schema
dependency, so tests need a way to prove a document really satisfies the
published file rather than merely looking plausible. This validator covers
exactly the keywords used by `atmem/schemas/v1/*.json` and raises on any
keyword it does not understand, so a schema that grows a new construct fails
loudly here instead of being silently under-checked.

It is a test helper, not a general-purpose implementation.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

SCHEMA_ROOT = Path(__file__).resolve().parents[1] / "atmem" / "schemas" / "v1"

_SUPPORTED = {
    "$schema", "$id", "$ref", "$defs", "title", "description", "type", "const",
    "enum", "required", "properties", "additionalProperties", "items",
    "minItems", "maxItems", "uniqueItems", "minLength", "maxLength", "minimum",
    "maximum", "exclusiveMinimum", "pattern", "oneOf", "anyOf", "allOf", "if",
    "then", "else", "not", "propertyNames", "format",
}

_TYPES: dict[str, Any] = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
    "number": (int, float),
    "integer": int,
    "null": type(None),
}


class SchemaError(AssertionError):
    """A document did not satisfy its published schema."""


def load(name: str) -> dict[str, Any]:
    return json.loads((SCHEMA_ROOT / name).read_text())


def validate(document: Any, schema: dict[str, Any], *, root: dict[str, Any] | None = None,
             path: str = "$") -> None:
    """Raise SchemaError unless `document` satisfies `schema`."""
    root = root if root is not None else schema
    unsupported = set(schema) - _SUPPORTED
    if unsupported:
        raise SchemaError(
            f"{path}: schema uses keywords this checker does not implement: "
            f"{sorted(unsupported)}"
        )

    if "$ref" in schema:
        validate(document, _resolve(str(schema["$ref"]), root), root=root, path=path)
        return

    if "type" in schema:
        _check_type(document, schema["type"], path)
    if "const" in schema and document != schema["const"]:
        raise SchemaError(f"{path}: expected const {schema['const']!r}, got {document!r}")
    if "enum" in schema and document not in schema["enum"]:
        raise SchemaError(f"{path}: {document!r} is not one of {schema['enum']}")

    if isinstance(document, str):
        _check_string(document, schema, path)
    if isinstance(document, (int, float)) and not isinstance(document, bool):
        _check_number(document, schema, path)
    if isinstance(document, list):
        _check_array(document, schema, root, path)
    if isinstance(document, dict):
        _check_object(document, schema, root, path)

    for keyword in ("oneOf", "anyOf"):
        if keyword not in schema:
            continue
        matches = 0
        for index, branch in enumerate(schema[keyword]):
            try:
                validate(document, branch, root=root, path=f"{path}[{keyword}:{index}]")
                matches += 1
            except SchemaError:
                continue
        if keyword == "oneOf" and matches != 1:
            raise SchemaError(f"{path}: matched {matches} oneOf branches, expected 1")
        if keyword == "anyOf" and matches == 0:
            raise SchemaError(f"{path}: matched no anyOf branch")

    for branch in schema.get("allOf", ()):
        validate(document, branch, root=root, path=path)

    if "if" in schema:
        try:
            validate(document, schema["if"], root=root, path=f"{path}[if]")
        except SchemaError:
            if "else" in schema:
                validate(document, schema["else"], root=root, path=path)
        else:
            if "then" in schema:
                validate(document, schema["then"], root=root, path=path)

    if "not" in schema:
        try:
            validate(document, schema["not"], root=root, path=path)
        except SchemaError:
            pass
        else:
            raise SchemaError(f"{path}: document matched a forbidden schema")


def as_json_document(value: Any) -> Any:
    """Round-trip through JSON, the way a document actually crosses a boundary.

    AtMem contracts hold tuples and string enums in memory. What a consumer
    receives is JSON, so schemas are checked against the serialized form.
    """
    return json.loads(json.dumps(value, default=str))


def is_valid(document: Any, schema: dict[str, Any]) -> bool:
    try:
        validate(document, schema)
    except SchemaError:
        return False
    return True


def _check_type(document: Any, expected: Any, path: str) -> None:
    names = expected if isinstance(expected, list) else [expected]
    for name in names:
        python_type = _TYPES[name]
        if name == "integer" and isinstance(document, bool):
            continue
        if name in {"number", "integer"} and isinstance(document, bool):
            continue
        if isinstance(document, python_type):
            return
    raise SchemaError(f"{path}: {type(document).__name__} is not of type {expected}")


def _check_string(document: str, schema: dict[str, Any], path: str) -> None:
    if "minLength" in schema and len(document) < schema["minLength"]:
        raise SchemaError(f"{path}: shorter than minLength {schema['minLength']}")
    if "maxLength" in schema and len(document) > schema["maxLength"]:
        raise SchemaError(f"{path}: longer than maxLength {schema['maxLength']}")
    if "pattern" in schema and not re.search(schema["pattern"], document):
        raise SchemaError(f"{path}: {document!r} does not match {schema['pattern']!r}")


def _check_number(document: Any, schema: dict[str, Any], path: str) -> None:
    if "minimum" in schema and document < schema["minimum"]:
        raise SchemaError(f"{path}: below minimum {schema['minimum']}")
    if "maximum" in schema and document > schema["maximum"]:
        raise SchemaError(f"{path}: above maximum {schema['maximum']}")
    if "exclusiveMinimum" in schema and document <= schema["exclusiveMinimum"]:
        raise SchemaError(f"{path}: not above exclusiveMinimum {schema['exclusiveMinimum']}")


def _check_array(document: list, schema: dict[str, Any], root: dict[str, Any], path: str) -> None:
    if "minItems" in schema and len(document) < schema["minItems"]:
        raise SchemaError(f"{path}: fewer than minItems {schema['minItems']}")
    if "maxItems" in schema and len(document) > schema["maxItems"]:
        raise SchemaError(f"{path}: more than maxItems {schema['maxItems']}")
    if schema.get("uniqueItems"):
        seen = [json.dumps(item, sort_keys=True) for item in document]
        if len(set(seen)) != len(seen):
            raise SchemaError(f"{path}: items are not unique")
    if "items" in schema:
        for index, item in enumerate(document):
            validate(item, schema["items"], root=root, path=f"{path}[{index}]")


def _check_object(document: dict, schema: dict[str, Any], root: dict[str, Any], path: str) -> None:
    for name in schema.get("required", ()):
        if name not in document:
            raise SchemaError(f"{path}: missing required property {name!r}")
    properties = schema.get("properties", {})
    for name, value in document.items():
        if name in properties:
            validate(value, properties[name], root=root, path=f"{path}.{name}")
        elif schema.get("additionalProperties") is False:
            raise SchemaError(f"{path}: additional property {name!r} is not allowed")
        elif isinstance(schema.get("additionalProperties"), dict):
            validate(
                value, schema["additionalProperties"], root=root, path=f"{path}.{name}"
            )
    if "propertyNames" in schema:
        for name in document:
            validate(name, schema["propertyNames"], root=root, path=f"{path}.{name}")


def _pointer(node: Any, pointer: str) -> Any:
    for part in pointer.split("/"):
        if part:
            node = node[part]
    return node


def _resolve(reference: str, root: dict[str, Any]) -> dict[str, Any]:
    if reference.startswith("#/"):
        return _pointer(root, reference[2:])
    if ".json#/" in reference:
        # A pointer into another published schema, so a shared definition such
        # as a task operation lives in exactly one file. Duplicating it per
        # schema is what lets two copies drift apart unnoticed.
        filename, pointer = reference.split("#/", 1)
        return _pointer(load(filename), pointer)
    if reference.endswith(".json"):
        return load(reference)
    raise SchemaError(f"unsupported $ref: {reference!r}")
