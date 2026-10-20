"""Live/public metric projection; never imputes missing model usage as zero.

The raw task/evaluator/model evidence remains in the protected benchmark vault.
This projection separates product availability from model correctness and uses
only identical, complete paired cells for token/latency comparisons.
"""
import argparse
import json
import os
from pathlib import Path
import statistics
import time
import math

ARMS = ('no_memory', 'atmem_structure')


def percentile95(values):
    """Empirical nearest-rank p95; no extrapolation from a small sample."""
    return sorted(values)[math.ceil(.95 * len(values)) - 1] if values else None


def summarize(manifest, result):
    arm_order = manifest.get('arms', list(ARMS))
    if (not isinstance(arm_order, list) or not 2 <= len(arm_order) <= 3
            or len(set(arm_order)) != len(arm_order)
            or any(arm not in {*ARMS, 'cognee_structure'} for arm in arm_order)):
        raise ValueError('explicit supported unique comparison arms required')
    rows = result.get('rows', [])
    cells = {(r['instance_id'], r['arm']): r for r in rows}
    if len(cells) != len(rows):
        raise ValueError('duplicate task/arm cells')
    selected = [r['instance_id'] for r in manifest['selected']]
    if any(task not in selected or arm not in arm_order for task, arm in cells):
        raise ValueError('cell outside frozen cohort')
    runnable = [task for task in selected if all(
        (r := cells.get((task, arm), {})).get('grade_valid') is True
        and isinstance(r.get('usage'), dict) and r['usage'].get('complete') is True
        and r.get('solver_s') is not None for arm in arm_order)]
    paired_terminal = [task for task in selected if all(
        type(cells.get((task, arm), {}).get('task_pass')) is bool for arm in arm_order)]
    arms = {}
    for arm in arm_order:
        current = [r for r in rows if r['arm'] == arm]
        inferred = [r for r in current if isinstance(r.get('usage'), dict)]
        pair = [cells[(task, arm)] for task in runnable]
        arms[arm] = {'terminal_cells': len(current), 'selected_tasks': len(selected),
            'fully_resolved': sum(r.get('task_pass') is True for r in current),
            'official_full_resolutions': sum(r.get('grade_valid') is True and r.get('patch_policy') is True
                and r.get('resolution') == 'RESOLVED_FULL' for r in current),
            'graded_cells': sum(r.get('grade_valid') is True for r in current),
            'product_preparation_failures': sum(r.get('status') == 'product_preparation_failed' for r in current),
            'environment_unavailable': sum(r.get('status') == 'environment_not_qualified' for r in current),
            'inference_attempts_with_receipts': len(inferred),
            'complete_usage_receipts': sum(r['usage'].get('complete') is True for r in inferred),
            'paired_operational_resolutions': sum(cells[(task, arm)].get('task_pass') is True for task in paired_terminal),
            'paired_complete_input_tokens': sum(r['usage']['total_input_tokens'] for r in pair) if pair else None,
            'paired_complete_output_tokens': sum(r['usage']['output_tokens'] for r in pair) if pair else None,
            'paired_solver_seconds': sum(r['solver_s'] for r in pair) if pair else None,
            'paired_median_solver_seconds': statistics.median(r['solver_s'] for r in pair) if pair else None,
            'paired_p95_solver_seconds': percentile95([r['solver_s'] for r in pair]),
            'paired_median_cold_seconds': statistics.median(r['solver_s'] + r['setup_s'] for r in pair)
                if pair and all(isinstance(r.get('setup_s'), (float, int)) for r in pair) else None,
            'paired_p95_cold_seconds': percentile95([r['solver_s'] + r['setup_s'] for r in pair])
                if pair and all(isinstance(r.get('setup_s'), (float, int)) for r in pair) else None,
            'paired_index_seconds': sum(r.get('index_s', 0) for r in pair) if pair else None,
            'automatic_context_cells': sum((r.get('automatic_context_bytes') or 0) > 0 for r in current),
            'observed_atmem_tool_calls': sum(r.get('graph_calls', 0) or 0 for r in current),
            'observed_provider_tool_calls': sum(r.get('graph_calls', 0) or 0 for r in current)}
    return {'status': result.get('status', 'pending'), 'selected_tasks': len(selected),
        'paired_terminal_tasks': len(paired_terminal), 'paired_runnable_tasks': len(runnable),
        'arms': arms, 'controller_error': result.get('error'),
        'interpretation': 'Preparation failures measure product availability, not model accuracy. '
            'Token/time totals compare only identical pairs with valid grades and complete usage. '
            'This is a cold-start structural pilot, not an experience-memory or full-suite score.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--watch-pid', type=int)
    parser.add_argument('--output', type=Path, help='Additional public metric projection, not raw transcripts')
    args = parser.parse_args()
    manifest = json.loads((args.root / 'manifest.json').read_text())
    while True:
        path = args.root / 'results.json'
        if path.exists():
            try:
                result = json.loads(path.read_text())
            except json.JSONDecodeError:
                time.sleep(1)
                continue
            report = summarize(manifest, result)
            if args.watch_pid and result['status'] == 'running':
                try:
                    os.kill(args.watch_pid, 0)
                except ProcessLookupError:
                    report['status'] = 'controller_not_running'
            (args.root / 'comparison.json').write_text(json.dumps(report, indent=2))
            if args.output:
                args.output.write_text(json.dumps(report, indent=2))
            if report['status'] != 'running' or not args.watch_pid:
                print(json.dumps(report, indent=2), flush=True)
                return
        elif not args.watch_pid:
            raise ValueError('no result projection exists yet')
        time.sleep(20)


if __name__ == '__main__':
    main()
