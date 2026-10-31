"""Read-only AtSys acceptance for the routed 600-task run: retained evidence, never worker claims."""
from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from benchmarks.dolphinbench.readiness import admit, identity, pin, read


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('condition', 'receipts', 'output', 'summary'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    result_path = args.output / 'full-result.json'
    if not result_path.is_file() or not args.summary.is_file():
        parser.exit(1, 'Full result or worker summary missing; the run is incomplete.\n')
    condition = admit(args.condition, args.receipts, 'full')
    result, summary = read(result_path), read(args.summary)
    rows = result.get('rows', [])
    accounting = result.get('accounting', {})
    full_transport = condition.get('full_admission_policy') == 'fresh-full-transport-qualified-v1'
    if full_transport:
        from benchmarks.dolphinbench.recording import verify_transient_reservations
        budget_identity = {**read(condition['inputs']['options']['path'])['campaign_identity'],
                           'cap_usd': condition['budget']['caps_usd']['full']}
        proof = verify_transient_reservations(args.output / 'budget.db', args.output / 'judge-calls',
            cap_usd=condition['budget']['caps_usd']['full'], identity=budget_identity)
        accounting_ok = (all(abs(accounting.get(k, -1) - proof[k]) < 1e-9
                             for k in ('actual_usd', 'uncertain_usd'))
                         and accounting.get('unresolved_calls') == proof['unresolved_calls']
                         and accounting.get('complete') is (proof['unresolved_calls'] == 0))
    else:
        accounting_ok = accounting.get('complete') is True and accounting.get('uncertain_usd') == 0
    if (result.get('schema') != 'dolphin-full-report-v1' or result.get('tasks') != 600 or len(rows) != 600
            or len({r.get('id') for r in rows}) != 600 or result.get('condition_sha256') != identity(condition)
            or not accounting_ok
            or not 0 <= accounting.get('actual_usd', -1) <= condition['budget']['caps_usd']['full']
            or result['passed'] != sum(bool(r.get('passed')) for r in rows)):
        parser.exit(1, 'Full result is incomplete, mismatched or has unreconciled accounting.\n')
    expected = {'condition_sha256': identity(condition), 'tasks': 600, 'passed': result['passed'],
                'recoveries': len(result['recoveries']), 'regressions': len(result['regressions']),
                'actual_usd': accounting['actual_usd'], 'uncertain_usd': accounting.get('uncertain_usd', 0),
                'result': pin(result_path)}
    if any(summary.get(k) != v for k, v in expected.items()):
        parser.exit(1, 'Worker summary does not match the independently read full result.\n')
    print(f"Validated: routed full run {result['passed']}/600; paid API settled ${accounting['actual_usd']}, "
          f"uncertain up to ${accounting.get('uncertain_usd', 0)}. Self-tested, not official.")


if __name__ == '__main__':
    main()
