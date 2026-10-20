"""Recover diagnostic results and actual nonempty navigation delivery from evidence."""
import argparse
from hashlib import sha256
import json
from pathlib import Path


def project(vault, principal):
    campaign = vault.inspect(principal, 'campaign')
    terminal = [e['envelope']['payload'] for e in campaign if e['envelope']['event_type'] == 'discovery.completed']
    if len(terminal) != 1:
        raise ValueError('exactly one completed campaign required; do not silently omit failures')
    rows = terminal[0]['rows']
    if len({row['run'] for row in rows}) != len(rows):
        raise ValueError('duplicate trial identities')
    output = []
    for row in rows:
        retained = vault.inspect(principal, row['run'])
        kinds = [e['envelope']['event_type'] for e in retained]
        if kinds.count('discovery.trial_started') != 1 or kinds.count('discovery.attempt') != 1:
            raise ValueError('missing or duplicate retained solver attempt')
        attempts, errors, nonempty, delivered = 0, 0, 0, 0
        for event in retained:
            if event['envelope']['event_type'] != 'discovery.tool_written':
                continue
            payload = event['envelope']['payload']
            request = payload['request']
            if request['method'] != 'tools/call' or request['params']['name'] != 'repository_discover':
                continue
            attempts += 1
            result = payload['response'].get('result')
            if result is None or result.get('isError'):
                errors += 1
                continue
            answer = json.loads(result['content'][0]['text'])
            if answer.get('status') == 'ready':
                delivered += 1
                nonempty += bool(answer.get('items'))
        output.append({**row, 'discovery_attempts': attempts, 'discovery_errors': errors,
            'ready_discovery_responses': delivered, 'nonempty_discovery_responses': nonempty,
            'treatment_used': nonempty > 0,
            'usage_scope': 'total_model_input_including_cache_not_unique_source_tokens'})
    return {'rows': output, 'planned_cells': terminal[0].get('planned', terminal[0].get('full_target_cells')),
        'executed_cells': len(output), 'classification': terminal[0].get('classification',
            'qualification' if terminal[0].get('qualification_only') else 'click_diagnostic'),
        'rental_spend_usd': terminal[0].get('rental_spend_usd')}


def markdown(value):
    lines = ['| Host | Backend | Task passed | Input incl. cache | Agent s | Index s | Nonempty lookup |',
        '|---|---|---:|---:|---:|---:|---:|']
    for row in value['rows']:
        token = row['usage']['input_tokens']
        lines.append('| ' + ' | '.join([row['host'], row['backend'],
            'yes' if row.get('functional_pass') is True else 'no' if row.get('functional_pass') is False else 'not scored',
            f'{token:,}' if token is not None else 'missing', f'{row["solver_ms"]/1000:.2f}',
            f'{row["index_ms"]/1000:.2f}', str(row['nonempty_discovery_responses'])]) + ' |')
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('choose new report directory')
    from benchmarks.code_replay.discovery_swebench import evidence
    vault, principal = evidence(args.root)
    result = project(vault, principal)
    args.output.mkdir(mode=0o700, parents=True)
    (args.output / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    (args.output / 'table.md').write_text(markdown(result))
    print(json.dumps({'reported': result['executed_cells'], 'output': str(args.output),
        'nonempty_lookup_cells': sum(r['treatment_used'] for r in result['rows']),
        'json_sha256': sha256((args.output / 'results.json').read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
