import json

import pytest

from research.retrieval_2310.trace_audit import audit


def test_trace_audit_distinguishes_execution_from_missing_evidence(tmp_path):
    cases=[(True,False,[]),(False,True,[]),(False,False,[]),
           (False,False,[{'tool':'create_document'}])]
    for i,(passed,blocked,calls) in enumerate(cases):
        for directory in ('tests','grades'):(tmp_path/directory/'fixture').mkdir(parents=True,exist_ok=True)
        (tmp_path/'tests/fixture'/f'{i}.json').write_text(json.dumps({
            'row':{'app_calls':calls},'attempts':[{'gate_blocked':blocked}],
            'settings':{'tools':[{'type':'function','function':{'name':'mcp__atmem__memory_search'}}]}}))
        (tmp_path/'grades/fixture'/f'{i}.json').write_text(json.dumps({'checks':[{'passed':passed}]}))
    result=audit(tmp_path)
    assert result['tasks']==4 and result['passed']==1
    assert result['observable_boundaries']=={'passed':1,'blocked_before_reader':1,
        'no_application_call':1,'application_called_but_failed':1}
    assert all(r['memory_search_tool_exposed'] for r in result['records'])
    assert result['semantic_failure_cause_not_inferred']


def test_trace_audit_rejects_truthy_but_invalid_grade(tmp_path):
    for directory in ('tests','grades'):(tmp_path/directory).mkdir()
    (tmp_path/'tests/case.json').write_text('{}')
    (tmp_path/'grades/case.json').write_text(json.dumps({'checks':[{'passed':'false'}]}))
    with pytest.raises(ValueError,match='grade'):audit(tmp_path)


def test_absent_row_field_uses_retained_empty_trace_not_an_assumption(tmp_path):
    for directory in ('tests/fixture','grades/fixture','apps/fixture/task'):
        (tmp_path/directory).mkdir(parents=True)
    (tmp_path/'tests/fixture/task.json').write_text(json.dumps({'row':{},'attempts':[]}))
    (tmp_path/'grades/fixture/task.json').write_text(json.dumps({'checks':[{'passed':False}]}))
    with pytest.raises(ValueError,match='trace'):audit(tmp_path)
    (tmp_path/'apps/fixture/task/calls.jsonl').write_text('')
    assert audit(tmp_path)['observable_boundaries']=={'no_application_call':1}
