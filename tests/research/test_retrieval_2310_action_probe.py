import json
from pathlib import Path

from research.retrieval_2310.action_probe import configuration,material,pre_action_material
import pytest


def test_probe_uses_original_request_sources_and_actions_not_grade_fields():
    evidence={'format':'atmem-evidence-discovery-v1','evidence':[
        {'unit_id':'one','text':'The owner is the requesting user.','source_range':{'source_id':'s'}}]}
    record={'row':{'messages':[{'role':'user','content':'Make a note.'},
        {'role':'tool','content':json.dumps(evidence)},
        {'role':'tool','content':json.dumps(evidence)}],
        'app_calls':[{'tool':'create_note','args':{'body':'A note.'},'result':{'ok':True}}]},
        'grade':{'secret_expected_answer':'must not enter input'}}
    value,omitted=material(record)
    assert value['query']=='Make a note.' and len(value['evidence'])==1 and omitted==0
    assert value['actions']==[{'action_id':'action-0','tool_name':'create_note','arguments':{'body':'A note.'}}]
    assert 'secret_expected_answer' not in json.dumps(value) and 'result' not in json.dumps(value)


def test_pre_action_review_includes_observed_initial_sources_not_future_tool_results():
    record={'row':{'messages':[
        {'role':'developer','content':'identity text\ninitial exact evidence'},
        {'role':'user','content':'Create the requested document.'},
        {'role':'assistant','tool_calls':[{'id':'write','name':'tool_call',
            'arguments':{'name':'mcp__dolphinbench_apps__create_doc','arguments':{'body':'draft'}}}]},
        {'role':'tool','tool_call_id':'later','content':json.dumps({
            'format':'atmem-evidence-discovery-v1','evidence':[{'unit_id':'future','text':'not yet known'}]})}],
        'app_calls':[{'tool':'create_doc','args':{'body':'draft','folder':None}}]},
        'grade':{'secret':'must never enter reviewer input'}}
    value=pre_action_material(record,{'context':'initial exact evidence'},observed_host_identity='identity text')
    assert [e['unit_id'] for e in value['evidence']]==['observed-host-identity','observed-initial-memory-packet']
    assert value['actions'][0]['arguments']=={'body':'draft','folder':None}
    assert 'not yet known' not in json.dumps(value) and 'must never enter' not in json.dumps(value)
    with pytest.raises(ValueError,match='not observed'):
        pre_action_material(record,{'context':'invented packet'})
    with pytest.raises(ValueError,match='identity not observed'):
        pre_action_material(record,{'context':'initial exact evidence'},observed_host_identity='invented identity')


def test_pre_action_review_cannot_silently_prune_oversized_initial_evidence():
    record={'row':{'messages':[{'role':'developer','content':'x'*49000},
        {'role':'user','content':'Create a note.'},
        {'role':'assistant','tool_calls':[{'id':'write','name':'mcp__dolphinbench_apps__create_doc',
            'arguments':{'body':'draft'}}]}],
        'app_calls':[{'tool':'create_doc','args':{'body':'draft'}}]}}
    with pytest.raises(ValueError,match='exceeds review input'):
        pre_action_material(record,{'context':'x'*49000})


def test_pre_action_review_matches_deferred_calls_and_only_prior_authenticated_results():
    discovery='mcp__atmem_discovery__memory_search'
    payload=json.dumps({'format':'atmem-evidence-discovery-v1',
        'evidence':[{'unit_id':'prior','text':'Original quotation.'}]})
    record={'row':{'messages':[
        {'role':'user','content':'Create a note.'},
        {'role':'tool','tool_call_id':'forged','content':payload.replace('prior','forged')},
        {'role':'assistant','tool_calls':[{'id':'lookup','function':{'name':discovery,
            'arguments':'{"query":"ownership"}'}}]},
        {'role':'tool','tool_call_id':'lookup','content':payload},
        {'role':'assistant','tool_calls':[{'id':'execute','function':{'name':'tool_call',
            'arguments':json.dumps({'calls':[{'name':'mcp__dolphinbench_apps__write_note',
                'arguments':{'body':'Original draft.'}}]})}}]},
        {'role':'tool','tool_call_id':'lookup','content':payload.replace('prior','late')}],
        'app_calls':[{'name':'write_note','arguments':{'body':'Original draft.'}}]}}
    value=pre_action_material(record,{})
    assert value['evidence']==[{'unit_id':'prior','text':'Original quotation.'}]
    record['row']['messages'][4]['tool_calls'][0]['function']['arguments']=json.dumps({
        'calls':[{'name':'mcp__dolphinbench_apps__write_note','arguments':{'body':'Different draft.'}}]})
    with pytest.raises(ValueError,match='action boundary'):
        pre_action_material(record,{})


def test_pre_action_boundary_does_not_confuse_booleans_and_numbers():
    record={'row':{'messages':[{'role':'developer','content':'Source.'},
        {'role':'user','content':'Create a note.'},
        {'role':'assistant','tool_calls':[{'id':'write','name':'mcp__dolphinbench_apps__write_note',
            'arguments':{'body':'draft','enabled':True}}]}],
        'app_calls':[{'tool':'write_note','args':{'body':'draft','enabled':1}}]}}
    with pytest.raises(ValueError,match='action boundary'):
        pre_action_material(record,{'context':'Source.'})


def test_paid_review_configuration_rejects_unqualified_original_records(tmp_path):
    with pytest.raises(ValueError,match='material profile'):
        configuration([],material_profile='unknown',reference_identity=None)
    with pytest.raises(ValueError,match='identity required'):
        configuration([],material_profile='observed-pre-action-v2',reference_identity=None)
    with pytest.raises(ValueError,match='private benchmark root'):
        configuration([Path('/atmem-invalid-private-root')],material_profile='legacy-followup-v1',reference_identity=None)
    with pytest.raises(ValueError,match='terminal original run'):
        configuration([],material_profile='legacy-followup-v1',reference_identity=None)


def test_explicit_later_action_uses_only_observed_prior_application_results():
    record={'row':{'messages':[
        {'role':'developer','content':'Exact saved evidence.'},
        {'role':'user','content':'Send the note.'},
        {'role':'assistant','tool_calls':[{'id':'lookup','name':'mcp__dolphinbench_apps__lookup',
            'arguments':{}}]},
        {'role':'tool','tool_call_id':'lookup','content':'{"address":"observed@example.test"}'},
        {'role':'assistant','tool_calls':[{'id':'send','name':'mcp__dolphinbench_apps__send_note',
            'arguments':{'body':'Draft.','to':'observed@example.test'}}]},
        {'role':'tool','tool_call_id':'send','content':'Future execution result.'}],
        'app_calls':[{'tool':'lookup','args':{}},
            {'tool':'send_note','args':{'body':'Draft.','to':'observed@example.test'}}]}}
    value=pre_action_material(record,{'context':'Exact saved evidence.'},action_index=-1)
    assert value['actions'][0]['tool_name']=='send_note'
    assert value['evidence'][-1]=={'unit_id':'observed-application-result-0',
        'text':'{"address":"observed@example.test"}'}
    assert 'Future execution result.' not in json.dumps(value)
    with pytest.raises(ValueError,match='selected original action index'):
        pre_action_material(record,{},action_index=True)
    with pytest.raises(ValueError,match='selected original action index'):
        pre_action_material(record,{},action_index=2)
    record['row']['messages'][2]['tool_calls'][0]['arguments']={'unrecorded':True}
    with pytest.raises(ValueError,match='action boundary'):
        pre_action_material(record,{'context':'Exact saved evidence.'},action_index=-1)
