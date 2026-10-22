"""Grounding-review contract fixtures, not evidence of task-quality improvement."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'packages/atbot/src'))
from atbot.action_review import review_action


def invoke(change=None):
    evidence=[{'unit_id':'source-one','text':'The on-call manager owns exceptions, not routine reviews.'}]
    actions=[{'action_id':'draft-one','tool_name':'write_note',
              'arguments':{'body':'The on-call manager owns every review.'}}]
    value={'findings':[{'kind':'unsupported_statement','action_id':'draft-one','unit_id':'source-one',
        'source_quote':evidence[0]['text'],'draft_quote':actions[0]['arguments']['body']}],'abstained':False}
    if change:change(value)
    class Provider:
        def complete(self,**kwargs):
            assert kwargs['schema']['additionalProperties'] is False
            return SimpleNamespace(structured=value,provider='fixture',model='fixture',
                                   input_tokens=12,output_tokens=3)
    return review_action(Provider(),'Create an ownership note.',evidence,actions)


def test_read_only_reviewer_preserves_source_and_draft_quotes():
    value=invoke()
    assert value['authority_decision'] is None and value['canonical_storage'] is False
    assert value['findings'][0]['draft_quote']=='The on-call manager owns every review.'


@pytest.mark.parametrize('field,value', [('unit_id','foreign'),('action_id','not-present'),
    ('source_quote','invented policy'),('draft_quote','invented assertion')])
def test_reviewer_rejects_invented_references(field,value):
    with pytest.raises(ValueError):invoke(lambda response:response['findings'][0].update({field:value}))


def test_reviewer_cannot_return_action_or_approval():
    with pytest.raises(ValueError):invoke(lambda value:value.update(approved=True))


def test_omission_uses_an_empty_draft_quote_not_generated_replacement():
    value=invoke(lambda response:response['findings'][0].update(kind='missing_qualification',draft_quote=''))
    assert value['findings'][0]['draft_quote']==''


def test_provider_cannot_mutate_the_original_draft_to_validate_a_forged_quote():
    evidence=[{'unit_id':'source','text':'Exceptions need approval.'}]
    actions=[{'action_id':'draft','tool_name':'write_note','arguments':{'body':'Original draft.'}}]
    class Provider:
        def complete(self,**kwargs):
            actions[0]['arguments']['body']='Forged draft.'
            return SimpleNamespace(structured={'abstained':False,'findings':[{
                'kind':'unsupported_statement','action_id':'draft','unit_id':'source',
                'source_quote':'Exceptions need approval.','draft_quote':'Forged draft.'}]},
                provider='fixture',model='fixture',input_tokens=1,output_tokens=1)
    with pytest.raises(ValueError,match='supplied source and draft'):
        review_action(Provider(),'Write a note.',evidence,actions)


def test_validated_findings_do_not_retain_provider_owned_aliases():
    response={'abstained':False,'findings':[{'kind':'missing_qualification',
        'action_id':'draft','unit_id':'source','source_quote':'Approval is required.',
        'draft_quote':''}]}
    class Provider:
        def complete(self,**kwargs):
            return SimpleNamespace(structured=response,provider='fixture',model='fixture',
                input_tokens=1,output_tokens=1)
    value=review_action(Provider(),'Write a note.',
        [{'unit_id':'source','text':'Approval is required.'}],
        [{'action_id':'draft','tool_name':'write_note','arguments':{'body':'Draft.'}}])
    response['findings'][0]['source_quote']='Invented after validation.'
    assert value['findings'][0]['source_quote']=='Approval is required.'
