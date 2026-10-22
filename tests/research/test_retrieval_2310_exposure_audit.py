"""Transport-attribution fixtures, not benchmark efficacy or training data."""
import json

import pytest

from research.retrieval_2310.exposure_audit import exposed_sources,linked_episode_coverage,UNTRUSTED_PROLOGUE


def payload(source='source-b'):
    return {'format':'atmem-evidence-discovery-v1','evidence':[
        {'unit_id':'unit-b','source_range':{'source_id':source}}]}


def conversation(name='mcp__atmem_discovery__memory_search',arguments='{}'):
    return [{'role':'assistant','tool_calls':[{'id':'call-1','function':{
        'name':name,'arguments':arguments}}]}, {'role':'tool','tool_call_id':'call-1',
        'content':json.dumps({'content':[{'type':'text','text':json.dumps(payload())}], 'isError':False})}]


def expose(messages):
    return exposed_sources(messages,ruling={'context':'exact context','candidate_ids':['unit-a']},
        unit_sources={'unit-a':('source-a',)})


def test_actual_initial_bytes_and_matched_discovery_response_are_separate():
    value=expose([{'role':'developer','content':'prefix exact context suffix'},*conversation()])
    assert value['initial_sources']=={'source-a'}
    assert value['followup_sources']=={'source-b'}
    coverage=linked_episode_coverage(value,{'source-a','source-b'})
    assert coverage['all_linked_episodes_eventually_touched']
    assert not coverage['all_linked_episodes_initially_touched']
    assert not coverage['complete_source_bytes_established']
    assert not coverage['task_success_established']


@pytest.mark.parametrize('role',['user','assistant','tool'])
def test_copied_initial_text_in_an_untrusted_role_does_not_prove_injection(role):
    assert not expose([{'role':role,'content':'exact context'}])['initial_sources']


def test_assistant_terminal_and_unmatched_output_cannot_masquerade_as_discovery():
    assert not expose([{'role':'assistant','content':json.dumps(payload())}])['followup_sources']
    assert not expose(conversation('terminal'))['followup_sources']
    assert not expose(conversation()[1:])['followup_sources']


def test_native_deferred_tool_dispatch_is_recognized_only_without_mixed_calls():
    calls=[{'name':'mcp__atmem_discovery__memory_search','arguments':{'query':'fixture'}}]
    assert expose(conversation('tool_call',json.dumps({'calls':calls})))['followup_sources']=={'source-b'}
    calls.append({'name':'terminal','arguments':{'command':'fixture'}})
    assert not expose(conversation('tool_call',json.dumps({'calls':calls})))['followup_sources']


def test_error_payload_and_unknown_annotations_never_establish_success():
    messages=conversation();messages[1]['content']=json.dumps({'isError':True,'result':payload()})
    value=expose(messages)
    assert not value['followup_sources']
    with pytest.raises(ValueError):linked_episode_coverage(value,set())


def test_real_export_shape_and_native_untrusted_envelope_are_supported():
    name='mcp__atmem_discovery__memory_search'
    messages=conversation()
    messages[0]['tool_calls']=[{'id':'call-1','name':'tool_call',
        'arguments':{'name':name,'arguments':{'query':'fixture'}}}]
    messages[1]['content']=f'<untrusted_tool_result source="{name}">\n'+UNTRUSTED_PROLOGUE+messages[1]['content']+'\n</untrusted_tool_result>'
    assert expose(messages)['followup_sources']=={'source-b'}
    messages[1]['content']=messages[1]['content'].replace('source="'+name+'"',
        'source="mcp__dolphinbench_apps__unrelated"')
    assert not expose(messages)['followup_sources']
