"""Freeze validation-only profile selection; never inspect confirmation scores."""
import argparse
from hashlib import sha256
import json
from pathlib import Path


def score(manifest, result):
    if result.get('status') != 'completed' or manifest.get('cohort') != 'validation':
        raise ValueError('completed validation required; confirmation cannot select a profile')
    identities = [row['instance_id'] for row in manifest['selected']]
    if len(identities) != 5 or len(set(identities)) != 5:
        raise ValueError('all five fixed validation identities required')
    rows = [row for row in result['rows'] if row['arm'] == 'atmem_structure']
    if len(rows) != 5 or {row['instance_id'] for row in rows} != set(identities):
        raise ValueError('exactly one terminal AtMem cell per selected task required')
    complete = all((row.get('usage') or {}).get('complete') is True for row in rows)
    timed = all(isinstance(row.get('setup_s'), (int, float))
                and isinstance(row.get('solver_s'), (int, float)) for row in rows)
    return {'operational_full_passes': sum(row.get('task_pass') is True for row in rows),
            'complete_input_tokens': sum(row['usage']['total_input_tokens'] for row in rows) if complete else None,
            'measured_setup_plus_solver_seconds': sum(row['setup_s'] + row['solver_s'] for row in rows) if timed else None}


def rank(value):
    return (-value['operational_full_passes'],
            value['complete_input_tokens'] if value['complete_input_tokens'] is not None else float('inf'),
            value['measured_setup_plus_solver_seconds']
            if value['measured_setup_plus_solver_seconds'] is not None else float('inf'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    candidates = []
    identities = None
    for root in args.root:
        manifest_raw, results_raw = (root / 'manifest.json').read_bytes(), (root / 'results.json').read_bytes()
        manifest, results = json.loads(manifest_raw), json.loads(results_raw)
        current = [row['instance_id'] for row in manifest['selected']]
        if identities is not None and current != identities:
            raise ValueError('validation cohorts differ')
        identities = current
        candidates.append({'campaign': str(root), 'manifest_sha256': sha256(manifest_raw).hexdigest(),
            'results_sha256': sha256(results_raw).hexdigest(), 'score': score(manifest, results),
            'context_delivery': manifest['context_delivery'],
            'model_graph_tools': manifest.get('model_graph_tools', True),
            'product_runtime': manifest['product_runtime']})
    chosen = min(candidates, key=lambda item: rank(item['score']))
    receipt = {'format': 'atmem-validation-profile-selection-v1',
        'rule': 'maximize full passes; minimize complete input; minimize measured setup plus solver; ties retain first declared candidate',
        'confirmation_scores_consulted': False, 'candidates': candidates, 'selected': chosen,
        'interpretation': 'Validation selection is not confirmation of benefit or a superiority claim.'}
    with args.output.open('x') as stream:
        json.dump(receipt, stream, indent=2)
    print(json.dumps(receipt, indent=2), flush=True)


if __name__ == '__main__':
    main()
