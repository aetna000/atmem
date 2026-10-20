"""Project actual CLI, usage, tool and patch-policy metadata without model text."""
import argparse
import base64
import json
import os
from pathlib import Path
from benchmarks.code_replay.swebench_pilot import vault, usage


def project(manifest, result, inspect):
    if result.get('status') not in {'completed', 'stopped'}:
        raise ValueError('terminal campaign required')
    rows = []
    for case in manifest['selected']:
        identity = case['instance_id']
        events = [event['envelope'] for event in inspect(identity)]
        for index, event in enumerate(events):
            if event['event_type'] != 'trial.captured':
                continue
            captured = event['payload']
            arm = captured['arm']
            starts = [(i, e['payload']) for i, e in enumerate(events[:index])
                      if e['event_type'] == 'trial.started' and e['payload']['arm'] == arm]
            if len(starts) != 1:
                raise ValueError('exactly one started model cell required')
            start, configured = starts[0]
            stream = [json.loads(line) for line in base64.b64decode(captured['stdout_base64'], validate=True).splitlines()
                      if line.startswith(b'{')]
            measured = usage(stream)
            if measured != captured['usage']:
                raise ValueError('retained stream and captured usage differ')
            terminal = [row for row in result['rows'] if row['instance_id'] == identity and row['arm'] == arm]
            if len(terminal) != 1 or terminal[0]['usage'] != measured:
                raise ValueError('terminal usage is absent, duplicated or changed')
            init = [row for row in stream if row.get('type') == 'system' and row.get('subtype') == 'init']
            calls = [e['payload']['request']['params']['name'] for e in events[start + 1:index]
                     if e['event_type'] == 'tool.exchange' and e['payload']['arm'] == arm
                     and e['payload']['request']['method'] == 'tools/call']
            if len(calls) != terminal[0].get('tool_calls'):
                raise ValueError('retained model tool count differs')
            provider_responses = []
            text_bytes = {'workspace_command': 0, 'provider': 0}
            for earlier in events[start + 1:index]:
                payload = earlier['payload']
                if earlier['event_type'] != 'tool.exchange' or payload.get('arm') != arm:
                    continue
                request = payload['request']
                if request.get('method') != 'tools/call':
                    continue
                answer = payload['response']
                content = answer.get('result', {}).get('content', [])
                channel = 'workspace_command' if request['params'].get('name') == 'workspace_command' else 'provider'
                text_bytes[channel] += sum(len(part.get('text', '').encode('utf-8')) for part in content
                                           if part.get('type') == 'text')
                if channel == 'workspace_command':
                    continue
                parsed = json.loads(content[0]['text']) if content else None
                provider_responses.append({'name': request['params']['name'], 'elapsed_seconds': payload['elapsed_s'],
                    'rpc_error': answer.get('error'), 'tool_error': answer.get('result', {}).get('isError', False),
                    'reported_status': parsed.get('status') if isinstance(parsed, dict) else None,
                    'response_json_type': type(parsed).__name__})
            changed = captured['patch']['changed_paths']
            dependencies = [path for path in changed if Path(path).name in
                {'pyproject.toml', 'setup.py', 'setup.cfg', 'package.json', 'Pipfile', 'Pipfile.lock', 'environment.yml'}
                or Path(path).name.startswith('requirements')]
            tests = [path for path in changed if any(part in {'test', 'tests', 'testing'} for part in Path(path).parts)
                     or Path(path).name.startswith('test_') or Path(path).name == 'conftest.py']
            preparation = []
            for earlier in events[:start]:
                payload = earlier['payload']
                if earlier['event_type'] != 'tool.exchange' or payload.get('arm') != arm:
                    continue
                request = payload['request']
                if request.get('method') != 'tools/call' or request['params'].get('name') not in {'code_search', 'code_query'}:
                    continue
                if request['params'].get('arguments', {}).get('operation') != 'architecture':
                    continue
                answer = payload['response'].get('result', {})
                content = answer.get('content', [])
                parsed = json.loads(content[0]['text']) if content else {}
                preparation.append({'operation': 'architecture', 'requested_max_nodes':
                    request['params']['arguments'].get('arguments', {}).get('max_nodes'),
                    'elapsed_seconds': payload['elapsed_s'], 'response_json_type': type(parsed).__name__,
                    'reported_status': parsed.get('status') if isinstance(parsed, dict) else None,
                    'is_error': answer.get('isError', False)})
            rows.append({'instance_id': identity, 'arm': arm,
                'cli_versions': sorted({row.get('claude_code_version', 'unreported') for row in init}),
                'reported_models': sorted({row.get('model', 'unreported') for row in init}),
                'usage_models': sorted((measured.get('models') or {}).keys()),
                'complete_usage': measured.get('complete') is True,
                'usage_exactly_reconstructed': True, 'tool_counts_exactly_reconstructed': True,
                'model_visible_tools': [tool['name'] for tool in configured['tool_inventory']],
                'retained_tool_text_utf8_bytes': text_bytes,
                'tool_inventory_serialized_utf8_bytes': len(json.dumps(configured['tool_inventory'],
                    ensure_ascii=False, separators=(',', ':')).encode()),
                'model_graph_queries': sum(name != 'workspace_command' for name in calls),
                'model_provider_responses': provider_responses,
                'changed_paths': changed, 'dependency_changes': dependencies, 'test_changes': tests,
                'pre_model_architecture_controls': preparation,
                'recorded_patch_policy': terminal[0].get('patch_policy')})
    return {'status': result['status'], 'actual_model_streams': len(rows), 'rows': rows,
            'interpretation': 'Metadata audit of retained streams, not a new model run or independent task reproduction. '
                'Text bytes are retained decoded MCP text, excluding transport wrappers; inventory bytes use compact JSON. '
                'Neither byte measure is billed tokens, a causal decomposition, or proof of model acknowledgement.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    os.environ['ATMEM_HOME'] = str(args.root / 'home')
    service, principal = vault(args.root)
    report = project(json.loads((args.root / 'manifest.json').read_text()),
                     json.loads((args.root / 'results.json').read_text()), lambda identity: service.inspect(principal, identity))
    (args.root / 'receipt-audit.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
