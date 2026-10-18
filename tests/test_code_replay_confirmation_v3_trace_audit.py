import pytest
from benchmarks.code_replay.confirmation_v3_trace_audit import audit_events


def event(identity,output):
    return {'type':'item.completed','item':{'id':identity,'type':'command_execution',
        'command':'read source','aggregated_output':output,'exit_code':0}}


def test_audit_counts_all_outputs_but_deduplicates_repeated_cli_items():
    first=event('one','x'*2000)
    result=audit_events([first,first,event('two','x'*2000)])
    assert result['native_commands']==2
    assert result['native_command_output_bytes']==4000
    assert result['exact_duplicate_output_bytes']==2000
    assert len(result['command_metadata'])==2
    assert 'not per-tool token attribution' in result['assurance']
    with pytest.raises(ValueError):audit_events([first,event('one','different')])
