"""Owner-authorized reconciliation of $0 subscription transport failures in a pilot ledger.

A subscription (not paid API) reader call that failed in transport is recorded as
``subscription_failure_usage_unknown``: its failure receipt states a $0 incremental
API charge and no delivered response, but its subscription token usage is unknown.
The frozen accounting treats such a call as unresolved, which blocks the pilot report
even though every USD amount is known.

This tool never edits the ledger or frozen code. It preserves the original
``pilot-accounting.json`` byte for byte as ``pilot-accounting.unreconciled.json``
and writes a reconciled accounting that lists each reconciled call, its receipt and
the owner authorization, with token usage still reported as unknown. Any other
unresolved state, a non-zero or missing charge, a delivered response or a paid-API
basis is refused.

    python scripts/reconcile_subscription_failures.py --output RUN_DIR \
        --authorization "owner approved 2026-10-31: ..."
"""
import argparse
import json
from pathlib import Path
import shutil
import sqlite3
import time

STATE = 'subscription_failure_usage_unknown'


def reconcile(output, authorization):
    output = Path(output)
    accounting_path = output / 'pilot-accounting.json'
    original_path = output / 'pilot-accounting.unreconciled.json'
    accounting = json.loads(accounting_path.read_text())
    if accounting.get('complete') is True:
        raise SystemExit('Accounting is already complete; nothing to reconcile.')
    with sqlite3.connect(f'file:{output / "budget.db"}?mode=ro', uri=True) as connection:
        rows = connection.execute("SELECT call_id, phase, state, actual, usage_json FROM calls "
                                  "WHERE state NOT IN ('completed','unsent')").fetchall()
    reconciled = []
    for call_id, phase, state, actual, usage_json in rows:
        receipt = (json.loads(usage_json or '{}') or {}).get('failure_receipt') or {}
        if (state != STATE or phase != 'tests' or actual not in (0, None)
                or receipt.get('incremental_api_charge_usd') != 0 or receipt.get('response_delivered') is not False
                or receipt.get('provider') != 'OpenAI-Subscription'
                or 'subscription' not in str(receipt.get('billing_basis', ''))):
            raise SystemExit(f'Refusing to reconcile {call_id}: state={state}, phase={phase}, receipt={receipt}')
        reconciled.append({'call_id': call_id, 'phase': phase, 'state': state, 'failure_receipt': receipt,
                           'incremental_api_charge_usd': 0, 'subscription_token_usage': 'unknown'})
    if not reconciled or len(reconciled) != accounting.get('unresolved_calls'):
        raise SystemExit('Ledger unresolved calls do not match the accounting record; nothing written.')
    if original_path.exists():
        raise SystemExit('A preserved unreconciled accounting already exists; refusing to overwrite it.')
    shutil.copyfile(accounting_path, original_path)
    accounting.update(complete=True, unresolved_calls=0, reconciliation={
        'format': 'atmem-subscription-failure-reconciliation-v1', 'authorization': authorization,
        'reconciled_at': time.time(), 'calls': reconciled,
        'basis': 'subscription transport failure with a $0 incremental API charge receipt and no delivered '
                 'response; USD totals unchanged; subscription token usage remains unknown',
        'original_accounting': str(original_path)})
    accounting_path.write_text(json.dumps(accounting, indent=1, sort_keys=True))
    return accounting


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--authorization', required=True)
    args = parser.parse_args()
    result = reconcile(args.output, args.authorization)
    print(json.dumps({'complete': result['complete'], 'actual_usd': result['actual_usd'],
                      'reconciled_calls': len(result['reconciliation']['calls'])}))


if __name__ == '__main__':
    main()
