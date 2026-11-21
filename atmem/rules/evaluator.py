"""Non-executable deterministic predicates. Authorization is the caller's duty.

This function is not a model tool and cannot establish enforcement outside the
AtMem-owned dispatcher. Approval verification/consumption belongs to dispatch.
"""
from atmem.contracts.feedback import MCPInvocation
from atmem.rules.models import CompiledRule, RuleDecision


_MISSING = object()


def argument_at(arguments, path):
    value = arguments
    for name in path:
        if type(value) is not dict or name not in value:
            return _MISSING
        value = value[name]
    return value


def evaluate(rules: tuple[CompiledRule, ...], invocation: MCPInvocation, *, native_allowed=True, approval_valid=False) -> RuleDecision:
    if type(rules) is not tuple or len(rules) > 1000 or any(type(rule) is not CompiledRule for rule in rules):
        raise ValueError("bounded compiled rules required")
    if type(native_allowed) is not bool or type(approval_valid) is not bool:
        raise ValueError("explicit dispatcher decisions required")
    applicable = [r for r in rules if r.tool == invocation.tool]
    ids = tuple(r.rule_id for r in applicable)
    if not native_allowed:
        return RuleDecision(False, "native_denied", ids)
    if any(r.schema_version != invocation.schema_version for r in applicable):
        return RuleDecision(False, "schema_drift", ids)
    equality = {}
    for rule in applicable:
        for predicate in rule.predicates:
            if predicate.operator == "equals":
                previous = equality.get(predicate.path, _MISSING)
                value = (type(predicate.value), predicate.value)
                if previous is not _MISSING and previous != value:
                    return RuleDecision(False, "rule_conflict", ids)
                equality[predicate.path] = value
    needs_approval = False
    for rule in applicable:
        for predicate in rule.predicates:
            value = argument_at(invocation.arguments, predicate.path)
            if value is _MISSING:
                return RuleDecision(False, "required_argument_missing", ids)
            if predicate.operator == "equals" and (type(value) is not type(predicate.value) or value != predicate.value):
                return RuleDecision(False, "wrong_argument_value", ids)
            if predicate.operator == "approval_required":
                needs_approval = True
                if invocation.approval_id is None or not approval_valid:
                    return RuleDecision(False, "approval_required", ids, True)
    return RuleDecision(True, "allowed", ids, needs_approval)
