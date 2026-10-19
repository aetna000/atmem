"""Aggregate both frozen repeats without mixing task denominators or missing usage."""
import argparse
import json
import os
from pathlib import Path
import statistics
from benchmarks.code_replay.swebench_pilot import vault, validate_frozen_manifest
from benchmarks.code_replay.swebench_report import summarize, percentile95

ARMS = ('no_memory', 'atmem_structure', 'cognee_structure')


def combine(manifests, results):
    if len(manifests) != 2 or len(results) != 2:
        raise ValueError('both predeclared repetitions required')
    first = manifests[0]
    identities = [row['instance_id'] for row in first['selected']]
    if len(identities) != 5 or len(set(identities)) != 5:
        raise ValueError('five distinct task clusters required')
    cells = []
    for index, (manifest, result) in enumerate(zip(manifests, results), 1):
        if manifest.get('cohort') != 'confirmation' or manifest.get('repetition') != index or result['status'] != 'completed':
            raise ValueError('complete, ordered confirmation repeats required')
        if ({k: v for k, v in manifest.items() if k not in {'selected', 'repetition'}}
                != {k: v for k, v in first.items() if k not in {'selected', 'repetition'}}):
            raise ValueError('frozen provider or experiment identity differs')
        for before, after in zip(first['selected'], manifest['selected']):
            expected = before if index == 1 else {**before, 'arm_order': list(reversed(before['arm_order']))}
            if after != expected:
                raise ValueError('tasks or reversed second-repeat orders differ')
        if len(manifest['selected']) != 5 or set(manifest['arms']) != set(ARMS):
            raise ValueError('all scheduled provider cells required')
        summarize(manifest, result)  # Existing duplicate/foreign-cell validation.
        current = {(row['instance_id'], row['arm']): row for row in result['rows']}
        if set(current) != {(identity, arm) for identity in identities for arm in ARMS}:
            raise ValueError('missing terminal cell; do not call this complete')
        cells.append(current)
    availability = {arm: {'scheduled_attempts': 10,
        'operational_full_passes': sum(row.get('task_pass') is True for c in cells for (identity, a), row in c.items() if a == arm),
        'preparation_failures': sum(row.get('status') == 'product_preparation_failed' for c in cells for (identity, a), row in c.items() if a == arm),
        'environment_unavailable': sum(row.get('status') == 'environment_not_qualified' for c in cells for (identity, a), row in c.items() if a == arm),
        'complete_usage_receipts': sum((row.get('usage') or {}).get('complete') is True for c in cells for (identity, a), row in c.items() if a == arm)} for arm in ARMS}
    comparisons = {}
    for label, arms in [('three_way', ARMS), ('native_vs_atmem', ARMS[:2])]:
        common = [identity for identity in identities if all(
            (row := current[(identity, arm)]).get('grade_valid') is True
            and (row.get('usage') or {}).get('complete') is True
            and isinstance(row.get('solver_s'), (int, float))
            and isinstance(row.get('setup_s'), (int, float))
            for current in cells for arm in arms)]
        measured = {}
        for arm in arms:
            rows = [current[(identity, arm)] for current in cells for identity in common]
            measured[arm] = {'paired_attempts': len(rows),
                'full_passes': sum(row.get('task_pass') is True for row in rows),
                'input_tokens': sum(row['usage']['total_input_tokens'] for row in rows) if rows else None,
                'output_tokens': sum(row['usage']['output_tokens'] for row in rows) if rows else None,
                'median_solver_seconds': statistics.median(row['solver_s'] for row in rows) if rows else None,
                'p95_solver_seconds': percentile95([row['solver_s'] for row in rows]),
                'median_measured_setup_plus_solver_seconds': statistics.median(row['setup_s'] + row['solver_s'] for row in rows) if rows else None,
                'total_index_seconds': sum(row.get('index_s', 0) for row in rows) if rows else None,
                'provider_tool_requests': sum(row.get('graph_calls', 0) for row in rows)}
        comparisons[label] = {'identical_task_ids_in_both_repeats': common, 'task_clusters': len(common), 'arms': measured}
    return {'scheduled_task_clusters': 5, 'repetitions': 2, 'availability': availability, 'comparisons': comparisons,
        'per_repetition': [summarize(m, r) for m, r in zip(manifests, results)],
        'interpretation': 'Two attempts per task are clustered, not ten independent tasks. '
            'Token/time comparisons use identical complete task sets in BOTH repetitions. '
            'Unavailable or incomplete receipts are not zero. No population superiority or knowledge-use attribution.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifests, results = [], []
    for root in args.root:
        manifest = json.loads((root / 'manifest.json').read_text())
        result = json.loads((root / 'results.json').read_text())
        os.environ['ATMEM_HOME'] = str(root / 'home')
        service, principal = vault(root)
        events = service.inspect(principal, 'pilot')
        validate_frozen_manifest(events, manifest)
        completed = [e['envelope']['payload'] for e in events if e['envelope']['event_type'] == 'execution.completed']
        if completed != [result]:
            raise ValueError('result projection differs from protected completed receipt')
        if json.loads((root / 'archive-verification.json').read_text())['status'] != 'verified':
            raise ValueError('verify independent archive recovery before final aggregation')
        manifests.append(manifest); results.append(result)
    report = combine(manifests, results)
    report['projection_matches_protected_completed_receipts'] = True
    report['independent_archive_recovery_verified'] = True
    args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
