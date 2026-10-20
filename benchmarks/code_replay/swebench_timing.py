"""Account for pre-model automatic context instead of calling solve-only warm.

Read-only projection of retained phase timestamps. Does not rewrite original
results, substitute missing timings, or claim normal-host hook qualification.
"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import statistics

from benchmarks.code_replay.swebench_pilot import vault
from benchmarks.code_replay.swebench_report import percentile95


def context_stage(events, arm, *, automatic_expected=False):
    relevant = [e['envelope'] for e in events if e['envelope'].get('payload', {}).get('arm') == arm]
    starts = [i for i, e in enumerate(relevant) if e['event_type'] == 'trial.started']
    if len(starts) != 1:
        return None
    before = relevant[:starts[0]]
    prepared = [e for e in before if e['event_type'] == 'trial.context_prepared']
    if not prepared:
        return None if automatic_expected else 0.0
    controls = [e for e in before if e['event_type'] == 'trial.transport_control']
    if len(prepared) != 1 or len(controls) != 1:
        return None
    elapsed = (datetime.fromisoformat(prepared[0]['event_time'])
               - datetime.fromisoformat(controls[0]['event_time'])).total_seconds()
    return elapsed if elapsed >= 0 else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    result = json.loads((args.root / 'results.json').read_text())
    manifest = json.loads((args.root / 'manifest.json').read_text())
    if result['status'] not in {'completed', 'stopped'}:
        raise ValueError('terminal results required')
    os.environ['ATMEM_HOME'] = str(args.root / 'home')
    service, principal = vault(args.root)
    events = {}
    rows = []
    for row in result['rows']:
        identity = row['instance_id']
        if identity not in events:
            events[identity] = service.inspect(principal, identity)
        stage = context_stage(events[identity], row['arm'], automatic_expected=(
            row['arm'] == 'atmem_structure' and row.get('context_delivery') == 'automatic'))
        solver = row.get('solver_s')
        rows.append({'instance_id': identity, 'arm': row['arm'],
            'initial_context_stage_seconds': stage,
            'solver_seconds': solver,
            'indexed_workspace_context_plus_solver_seconds': stage + solver
                if stage is not None and solver is not None else None,
            'measured_setup_plus_solver_seconds': row['setup_s'] + solver
                if solver is not None and row.get('setup_s') is not None else None,
            'automatic_source_content_bytes': row.get('automatic_context_bytes', 0)})
    summary = {}
    arms = manifest['arms']
    original_cells = {(row['instance_id'], row['arm']): row for row in result['rows']}
    timed_cells = {(row['instance_id'], row['arm']): row for row in rows}
    paired = [item['instance_id'] for item in manifest['selected'] if all(
        (cell := original_cells.get((item['instance_id'], arm), {})).get('grade_valid') is True
        and (cell.get('usage') or {}).get('complete') is True
        and timed_cells.get((item['instance_id'], arm), {}).get('indexed_workspace_context_plus_solver_seconds') is not None
        for arm in arms)]
    for arm in sorted({row['arm'] for row in rows}):
        selected = [row for row in rows if row['arm'] == arm and row['instance_id'] in paired]
        indexed = [row['indexed_workspace_context_plus_solver_seconds'] for row in selected
                   if row['indexed_workspace_context_plus_solver_seconds'] is not None]
        summary[arm] = {'measured_cells': len(indexed),
            'median_indexed_workspace_context_plus_solver_seconds': statistics.median(indexed) if indexed else None,
            'p95_indexed_workspace_context_plus_solver_seconds': percentile95(indexed)}
    projection = {'status': result['status'], 'rows': rows, 'arms': summary, 'complete_paired_tasks': paired,
        'definition': 'Context stage spans retained transport-control to context-prepared timestamps, '
            'including pack process startup/query/validation and capture overhead. Indexed-workspace '
            'subtotal excludes graph indexing, workspace staging and preliminary transport controls. '
            'Cold setup-plus-solver remains separately measured; this is not normal-host latency qualification.'}
    (args.root / 'timing-analysis.json').write_text(json.dumps(projection, indent=2))
    print(json.dumps(projection, indent=2), flush=True)


if __name__ == '__main__':
    main()
