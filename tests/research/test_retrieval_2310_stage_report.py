import pytest

from research.retrieval_2310.stage_report import compare,execution_metrics,summarize,read_stage


def test_missing_execution_remains_in_denominator_and_usage_unknown():
    report=summarize({('scope','001'):{'passed':True,'duration_ms':4,
                     'reader_input_tokens':10,'reader_output_tokens':2}},
                     {('scope','001'),('scope','002')})
    assert report['requested_denominator_success_rate']==.5
    assert report['ungraded_or_not_executed']==1 and not report['complete']
    assert report['reader_input_tokens']=={'known_lower_bound':10,'unknown_tasks':1}
    assert report['latency']['unknown_tasks']==1 and not report['ready_for_600']


def test_missing_message_usage_never_means_zero_tokens():
    metrics=execution_metrics({'row':{'duration_ms':None,'messages':[
        {'role':'assistant','usage':{'prompt_tokens':7,'completion_tokens':3}},
        {'role':'assistant','content':'usage missing'}]}})
    assert metrics['reader_input_tokens'] is None
    assert metrics['reader_output_tokens'] is None
    assert metrics['duration_ms'] is None and not metrics['reader_usage_known']


def test_recorded_zero_usage_is_not_unknown():
    metrics=execution_metrics({'row':{'duration_ms':0,'messages':[
        {'role':'assistant','usage':{'prompt_tokens':0,'completion_tokens':0}}]}})
    assert metrics['reader_usage_known'] and metrics['reader_input_tokens']==0


def test_pre_reader_zero_call_receipt_does_not_look_like_missing_provider_usage():
    execution={'row':{'duration_ms':2,'messages':[
        {'role':'assistant','usage':{'input_tokens':0,'output_tokens':0}}]},
        'attempts':[{'gate_blocked':True,'provider_calls':0,'cost_usd':0}]}
    metrics=execution_metrics(execution)
    assert metrics['reader_usage_known'] and metrics['reader_input_tokens']==0
    assert metrics['reader_usage_basis']=='terminal_zero_call_receipt'
    execution['attempts']=[]
    assert execution_metrics(execution)['reader_input_tokens'] is None


def test_recovered_native_time_is_not_reported_as_complete_task_latency(tmp_path):
    import json
    (tmp_path/'grades/scope').mkdir(parents=True)
    (tmp_path/'tests/scope').mkdir(parents=True)
    (tmp_path/'grades/scope/001.json').write_text(json.dumps({'checks':[{'passed':True}]}))
    (tmp_path/'tests/scope/001.json').write_text(json.dumps({'row':{'duration_ms':12,'messages':[]}}))
    (tmp_path/'recovery-receipt.json').write_text(json.dumps({
        'latency_comparable_to_complete_task_wall_time':False}))
    record=read_stage(tmp_path)[('scope','001')]
    assert record['passed'] and record['duration_ms'] is None


def test_partial_pair_is_not_complete_and_no_unknown_task_is_accepted():
    first={('scope','001'):{'passed':True}}
    second={('scope','001'):{'passed':False},('scope','002'):{'passed':True}}
    report=compare(first,second,set(second))
    assert report['paired_losses']==1 and report['paired_wins']==0
    assert not report['complete_paired_comparison']
    with pytest.raises(ValueError):summarize(second,set(first))


@pytest.mark.parametrize('duration',[-1,float('nan'),True])
def test_invalid_duration_fails(duration):
    with pytest.raises(ValueError):execution_metrics({'row':{'duration_ms':duration,'messages':[]}})
