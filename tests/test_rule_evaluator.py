"""Adversarial final argument and owner approval bindings; no model calls."""
from dataclasses import replace

import pytest

from atmem.contracts.feedback import MCPInvocation, RulePredicate
from atmem.rules.compiler import compile_rule
from atmem.rules.evaluator import evaluate
from test_feedback_contracts import SAMPLES
from test_guarded_mcp import dispatcher_fixture, SCHEMA


RULE=next(v for v in SAMPLES if v.format=='atmem-feedback-rule-candidate-v1')


def test_approval_predicate_cannot_be_satisfied_by_a_model_argument_alone():
    rule=replace(RULE,predicates=(RulePredicate('approval_required',('target',)),))
    schema={'type':'object','properties':{'target':{'type':'string'}},'additionalProperties':False}
    compiled=compile_rule(rule,schema)
    call=MCPInvocation(rule.tool,rule.schema_version,{'target':'staging'},'call',approval_id='caller-invented')
    assert evaluate((compiled,),call).reason=='approval_required'
    assert evaluate((compiled,),call,approval_valid=True).allowed
    assert not evaluate((compiled,),call,native_allowed=False,approval_valid=True).allowed
    assert not evaluate((compiled,),replace(call,arguments={}),approval_valid=True).allowed


@pytest.mark.parametrize('change',['expiry','handler_generation','arguments'])
def test_owner_approval_cannot_survive_changed_final_binding(tmp_path,change):
    f,dispatcher,path=dispatcher_fixture(tmp_path)
    try:
        invoke=lambda args:path.write_text(args['body'])
        guard=lambda args:True
        dispatcher.register(f.owner['token'],f.scope,tool='fixture.write',schema_version='v1',schema=SCHEMA,
                            invoke=invoke,native_guard=guard,requires_approval=True)
        call=MCPInvocation('fixture.write','v1',{'body':'approved'},'exact-call')
        approval=dispatcher.approve(f.owner['token'],f.scope,principal_id=f.user['principal_id'],
                                    invocation=call,expires_at=1_700_000_060)
        if change=='expiry':f.feedback.clock=lambda:1_700_000_061
        elif change=='handler_generation':
            dispatcher.register(f.owner['token'],f.scope,tool='fixture.write',schema_version='v1',schema=SCHEMA,
                                invoke=invoke,native_guard=guard,requires_approval=True)
        else:call=replace(call,arguments={'body':'not approved'})
        result=dispatcher.execute(f.session,replace(call,approval_id=approval))
        assert result['status']=='blocked' and result['reason']=='approval_required'
        assert not path.exists()
    finally:
        f.feedback.memory.close()
