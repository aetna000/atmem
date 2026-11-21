"""Compile three allowlisted predicates against a registered closed tool schema."""
from atmem.contracts.feedback import RuleCandidate
from atmem.feedback.store import FeedbackError, snapshot
from atmem.rules.models import CompiledRule


def compile_rule(candidate: RuleCandidate, schema: dict) -> CompiledRule:
    candidate = RuleCandidate.from_dict(candidate.to_dict())
    schema = snapshot(schema)
    if schema.get("type") != "object" or schema.get("additionalProperties") is not False:
        raise FeedbackError("unsupported_schema")
    for predicate in candidate.predicates:
        current = schema
        for path in predicate.path:
            if (current.get("type") != "object" or current.get("additionalProperties") is not False
                    or path not in current.get("properties", {})):
                raise FeedbackError("rule_unexpressible")
            current = current["properties"][path]
        kind = current.get("type")
        if predicate.operator == "approval_required" and kind != "string":
            raise FeedbackError("rule_unexpressible")
        if predicate.operator == "equals":
            expected_type = {"string": str, "boolean": bool, "integer": int, "number": (int, float), "null": type(None)}.get(kind)
            if expected_type is None or type(predicate.value) not in (expected_type if type(expected_type) is tuple else (expected_type,)):
                raise FeedbackError("rule_unexpressible")
            if "enum" in current and not any(type(v) is type(predicate.value) and v == predicate.value for v in current["enum"]):
                raise FeedbackError("rule_unexpressible")
    return CompiledRule(candidate.rule_id, candidate.content_digest, candidate.tool, candidate.schema_version, candidate.predicates)
