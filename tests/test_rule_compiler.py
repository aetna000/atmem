from dataclasses import replace

import pytest

from atmem.contracts.feedback import MCPInvocation, RulePredicate
from atmem.feedback.store import FeedbackError
from atmem.rules.compiler import compile_rule
from atmem.rules.evaluator import evaluate
from test_feedback_contracts import SAMPLES


RULE = next(v for v in SAMPLES if v.format == "atmem-feedback-rule-candidate-v1")
SCHEMA = {"type": "object", "properties": {"target": {"type": "string"}, "approval": {"type": "string"},
                                         "flag": {"type": "boolean"}}, "additionalProperties": False}


def test_compiler_is_data_only_and_never_executes_rationale_or_values(tmp_path):
    marker = tmp_path / "unwanted"
    candidate = replace(RULE, rationale=f"execute touch {marker}", predicates=(RulePredicate("equals", ("target",), f"touch {marker}"),))
    compiled = compile_rule(candidate, SCHEMA)
    invocation = MCPInvocation(RULE.tool, RULE.schema_version, {"target": f"touch {marker}"}, "key")
    assert evaluate((compiled,), invocation).allowed
    assert not marker.exists()
    for schema in ({"type": "object"}, {"type": "object", "additionalProperties": True}):
        with pytest.raises(FeedbackError, match="unsupported_schema"):
            compile_rule(RULE, schema)
    for predicate in (RulePredicate("equals", ("target",), True), RulePredicate("present", ("unknown",)),
                      RulePredicate("approval_required", ("flag",))):
        with pytest.raises(FeedbackError, match="rule_unexpressible"):
            compile_rule(replace(RULE, predicates=(predicate,)), SCHEMA)


def test_conflicts_type_equality_and_native_denial_are_preserved():
    a = compile_rule(replace(RULE, predicates=(RulePredicate("equals", ("target",), "staging"),)), SCHEMA)
    b = compile_rule(replace(RULE, rule_id="other", predicates=(RulePredicate("equals", ("target",), "production"),)), SCHEMA)
    invocation = MCPInvocation(RULE.tool, RULE.schema_version, {"target": "staging"}, "key")
    assert evaluate((a,), invocation).allowed
    assert evaluate((a, b), invocation).reason == "rule_conflict"
    assert evaluate((a,), invocation, native_allowed=False).reason == "native_denied"
    assert evaluate((a,), replace(invocation, schema_version="v2")).reason == "schema_drift"
    assert evaluate((a,), replace(invocation, arguments={})).reason == "required_argument_missing"
