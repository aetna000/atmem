"""Read-only progress/results from saved executions, grades and actual costs."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3
import statistics


def report(root):
    rows = []
    latency_exceptions = []
    for persona in ('morgan', 'alex', 'riley'):
        tests = [json.loads(p.read_text()) for p in sorted((root / 'tests' / persona).glob('*.json'))]
        for test in tests:
            for attempt in test.get('attempts', []):
                if attempt.get('duration_basis'):
                    latency_exceptions.append({'persona': persona, 'test_id': test['row']['test_id'],
                        'basis': attempt['duration_basis']})
        grades = [json.loads(p.read_text()) for p in sorted((root / 'grades' / persona).glob('*.json'))]
        times = sorted(t['row']['duration_ms'] / 1000 for t in tests)
        usage = [m['usage'] for t in tests for m in t['row']['messages'] if 'usage' in m]
        auxiliary = []
        terminal_failures, unknown_usage_attempts = 0, 0
        preparation = Counter()
        for test in tests:
            native = root / 'native/tests' / persona / test['row']['test_id']
            ruling = native / 'pre-action-ruling.json'
            if ruling.exists():
                preparation[json.loads(ruling.read_text())['reason']] += 1
            exported = native / 'export.json'
            if exported.exists():
                data = json.loads(exported.read_text())
                auxiliary.extend(a['usage'] for a in data.get('auxiliary_calls', []))
                failure = data.get('native_terminal_failure')
                unknown_usage_attempts += len(data.get('failed_transport_attempts', []))
                if failure:
                    terminal_failures += 1
                    if 'failed_transport_attempts' not in data:
                        unknown_usage_attempts += len(failure['failed_attempts'])
        usage += auxiliary
        rows.append({'persona': persona, 'executed': len(tests), 'graded': len(grades),
            'passed': sum(bool(g['checks']) and all(c['passed'] for c in g['checks']) for g in grades),
            'native_transport_terminal_failures': terminal_failures,
            'failed_attempts_with_unknown_token_usage': unknown_usage_attempts,
            'token_totals_are_lower_bounds': bool(unknown_usage_attempts),
            'blocked_before_model': sum(any(a.get('gate_blocked') for a in t.get('attempts', [])) for t in tests),
            'product_preparation_rulings': dict(preparation),
            'model_responses': len([u for u in usage if u.get('prompt_tokens', u.get('input_tokens', 0))]),
            'input_tokens': sum(u.get('prompt_tokens', u.get('input_tokens', 0)) for u in usage),
            'output_tokens': sum(u.get('completion_tokens', u.get('output_tokens', 0)) for u in usage),
            'auxiliary_calls_included_in_token_totals': len(auxiliary),
            'median_task_seconds': statistics.median(times) if times else None,
            'p95_task_seconds': times[max(0, (len(times) * 95 + 99) // 100 - 1)] if times else None})
    book = sqlite3.connect(f'{(root / "budget.db").as_uri()}?mode=ro', uri=True)
    try:
        costs = [{'phase': phase, 'state': state, 'calls': count, 'actual_usd': (actual or 0) / 1e6,
                  'reserved_bound_usd': (reserved or 0) / 1e6}
                 for phase, state, count, actual, reserved in book.execute(
                     'SELECT phase,state,COUNT(*),SUM(actual),SUM(reserved) FROM calls GROUP BY phase,state')]
    finally:
        book.close()
    index = json.loads((root / 'archive-index.json').read_text()) if (root / 'archive-index.json').exists() else {}
    return {'run': str(root), 'expected_tasks': 600, 'personas': rows,
        'total_graded': sum(r['graded'] for r in rows), 'total_passed': sum(r['passed'] for r in rows),
        'complete': all(r['executed'] == r['graded'] for r in rows) and sum(r['graded'] for r in rows) == 600,
        'actual_api_costs_and_uncertain_bounds': costs,
        'latency_includes_memory_preparation_and_execution_excludes_grading_and_cloud_backup': not latency_exceptions,
        'latency_exceptions': latency_exceptions,
        'subscription_fees_not_allocated': True,
        'matched_mem0_run': False,
        'latest_verified_cloud_batch': index.get('verified_batches', [None])[-1]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path,
        default=Path('/Volumes/AtMemDolphin/campaign-atmem-v3-matched-luna-high-20261021'))
    parser.add_argument('--require-complete', action='store_true')
    args = parser.parse_args()
    result = report(args.root.resolve())
    if args.require_complete and not result['complete']:
        parser.error('All 600 saved executions and grades are required')
    print(json.dumps(result, indent=2))
