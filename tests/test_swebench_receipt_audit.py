import base64
from copy import deepcopy
import json
import pytest
from benchmarks.code_replay.swebench_pilot import usage
from tools.audit_swebench_receipts import project


def example():
    stream = [{'type': 'system', 'subtype': 'init', 'model': 'pinned-model', 'claude_code_version': 'pinned-cli'},
              {'type': 'result', 'subtype': 'success', 'is_error': False,
               'usage': {'input_tokens': 1, 'cache_read_input_tokens': 2, 'cache_creation_input_tokens': 3, 'output_tokens': 4}}]
    measured = usage(stream)
    def event(kind, **payload):
        return {'envelope': {'event_type': kind, 'payload': {'arm': 'atmem_structure', **payload}}}
    events = [event('trial.started', tool_inventory=[{'name': 'workspace_command'}]),
              event('tool.exchange', request={'method': 'tools/call', 'params': {'name': 'workspace_command'}},
                    response={'result': {'content': [{'type': 'text', 'text': 'bounded output'}], 'isError': False}}),
              event('trial.captured', usage=measured,
                    stdout_base64=base64.b64encode('\n'.join(map(json.dumps, stream)).encode()).decode(),
                    patch={'changed_paths': ['src/core.py']})]
    result = {'status': 'completed', 'rows': [{'instance_id': 'task', 'arm': 'atmem_structure',
               'usage': measured, 'tool_calls': 1, 'patch_policy': True}]}
    return events, result


def test_audit_reconstructs_usage_and_tools_without_exposing_model_text():
    events, result = example()
    report = project({'selected': [{'instance_id': 'task'}]}, result, lambda _: events)
    assert report['actual_model_streams'] == 1
    row = report['rows'][0]
    assert row['cli_versions'] == ['pinned-cli'] and row['reported_models'] == ['pinned-model']
    assert row['usage_exactly_reconstructed'] and row['complete_usage']
    assert row['model_graph_queries'] == 0 and not row['dependency_changes']
    assert row['retained_tool_text_utf8_bytes'] == {'workspace_command': 14, 'provider': 0}
    broken = deepcopy(result)
    broken['rows'][0]['tool_calls'] = 0
    with pytest.raises(ValueError, match='tool count differs'):
        project({'selected': [{'instance_id': 'task'}]}, broken, lambda _: events)


def test_dependency_audit_does_not_silently_rewrite_retained_result():
    events, result = example()
    events[-1]['envelope']['payload']['patch']['changed_paths'] = ['setup.py']
    row = project({'selected': [{'instance_id': 'task'}]}, result, lambda _: events)['rows'][0]
    assert row['dependency_changes'] == ['setup.py']
    assert row['recorded_patch_policy'] is True


@pytest.mark.parametrize('reply,expected', [({'status': 'current'}, 'current'), ([{'nodes': []}], None)])
@pytest.mark.parametrize('tool_name', ['code_search', 'code_query'])
def test_preparation_latency_preserves_provider_specific_response_shapes(reply, expected, tool_name):
    events, result = example()
    events.insert(0, {'envelope': {'event_type': 'tool.exchange', 'payload': {'arm': 'atmem_structure',
        'request': {'method': 'tools/call', 'params': {'name': tool_name,
                    'arguments': {'operation': 'architecture', 'arguments': {'max_nodes': 3}}}},
        'response': {'result': {'content': [{'type': 'text', 'text': json.dumps(reply)}], 'isError': False}},
        'elapsed_s': 1.25}}})
    control = project({'selected': [{'instance_id': 'task'}]}, result, lambda _: events)['rows'][0]['pre_model_architecture_controls'][0]
    assert control['elapsed_seconds'] == 1.25 and control['requested_max_nodes'] == 3
    assert control['reported_status'] == expected
    assert control['response_json_type'] == type(reply).__name__
