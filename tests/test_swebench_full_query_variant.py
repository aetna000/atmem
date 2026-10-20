from copy import deepcopy
from hashlib import sha256
import json
import pytest
from benchmarks.code_replay.swebench_full_query_variant import validate_qualification


def example():
    runtime = {'wheel_sha256': 'pinned'}
    tasks = {str(i): {'problem_statement': 'x' * 1200 + ' late_reference()'} for i in range(5)}
    manifest = {'format': 'atmem-full-query-context-qualification-v1', 'product_runtime': runtime,
                'model_runs': 0, 'selected': [{'instance_id': key} for key in tasks]}
    events = {'pilot': [{'envelope': {'event_type': 'diagnostic.full_query_planned', 'payload': {'manifest': manifest}}}]}
    rows = []
    for identity, task in tasks.items():
        query = task['problem_statement']
        prefix = query[:1000]
        pack = {'format': 'atmem-code-source-pack-v1', 'status': 'current', 'snapshot_id': 'source',
                'content': 'source body', 'content_sha256': sha256(b'source body').hexdigest()}
        reply = {'result': {'content': [{'type': 'text', 'text': json.dumps(pack)}], 'isError': False}}
        request = {'runtime': runtime, 'query_bytes': [1000, len(query)], 'requests': [{'method': 'initialize'},
            *[{'jsonrpc': '2.0', 'id': i, 'method': 'tools/call', 'params': {
                'name': 'code_context', 'arguments': {'query': text, 'budget': 4096}}}
              for i, text in ((2, prefix), (3, query))]]}
        raw = {'responses': [{}, deepcopy(reply), deepcopy(reply)], 'snapshot_id': 'source',
               'installed_package_files': 347, 'context_bytes': [11, 11],
               'context_sha256': [pack['content_sha256']] * 2}
        events[identity] = [{'envelope': {'event_type': kind, 'payload': payload}} for kind, payload in (
            ('diagnostic.full_query_request', request), ('diagnostic.full_query_response', raw))]
        rows.append({'instance_id': identity, 'status': 'passed', 'query_bytes': request['query_bytes'],
                     **{key: raw[key] for key in ('snapshot_id', 'installed_package_files', 'context_bytes', 'context_sha256')}})
    return runtime, tasks, manifest, {'status': 'completed', 'rows': rows}, events


def test_qualification_is_bound_to_complete_protected_requests_and_responses():
    runtime, tasks, manifest, result, events = example()
    assert validate_qualification(manifest, result, events.__getitem__, runtime, tasks) == result['rows']


@pytest.mark.parametrize('failure', ['truncated', 'projection', 'runtime', 'stopped', 'missing_response'])
def test_full_query_cannot_launch_from_lossy_stale_or_changed_qualification(failure):
    runtime, tasks, manifest, result, events = example()
    if failure == 'truncated':
        events['0'][0]['envelope']['payload']['requests'][2]['params']['arguments']['query'] = 'x' * 1000
    elif failure == 'projection':
        result['rows'] = deepcopy(result['rows'])
        result['rows'][0]['context_sha256'][1] = 'changed'
    elif failure == 'runtime':
        runtime = {'wheel_sha256': 'replacement'}
    elif failure == 'stopped':
        result['status'] = 'stopped'
    else:
        events['0'].pop()
    with pytest.raises(ValueError):
        validate_qualification(manifest, result, events.__getitem__, runtime, tasks)
