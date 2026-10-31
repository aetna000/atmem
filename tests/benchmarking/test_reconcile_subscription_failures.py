import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('reconcile', Path(__file__).parents[2] / 'scripts/reconcile_subscription_failures.py')
reconcile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reconcile)

RECEIPT = {'provider': 'OpenAI-Subscription', 'response_delivered': False, 'http_status': 502, 'usage': None,
           'incremental_api_charge_usd': 0, 'billing_basis': 'subscription, not paid API; generation outcome unknown'}


def run(tmp_path, rows, unresolved=1):
    db = sqlite3.connect(tmp_path / 'budget.db')
    db.execute('CREATE TABLE calls (call_id TEXT, phase TEXT, state TEXT, actual INTEGER, usage_json TEXT)')
    db.executemany('INSERT INTO calls VALUES (?,?,?,?,?)', rows)
    db.commit(); db.close()
    (tmp_path / 'pilot-accounting.json').write_text(json.dumps({'complete': False, 'unresolved_calls': unresolved,
                                                                'actual_usd': 0.09, 'uncertain_usd': 0}))
    return reconcile.reconcile(tmp_path, 'owner approved')


def test_zero_charge_subscription_failure_is_reconciled_and_original_preserved(tmp_path):
    result = run(tmp_path, [('a', 'tests', 'completed', 0, '{}'),
                            ('b', 'tests', reconcile.STATE, 0, json.dumps({'failure_receipt': RECEIPT}))])
    assert result['complete'] is True and result['actual_usd'] == 0.09
    assert result['reconciliation']['calls'][0]['subscription_token_usage'] == 'unknown'
    assert json.loads((tmp_path / 'pilot-accounting.unreconciled.json').read_text())['complete'] is False


@pytest.mark.parametrize('row', [
    ('b', 'judge', reconcile.STATE, 0, json.dumps({'failure_receipt': RECEIPT})),
    ('b', 'tests', 'reserved', 0, '{}'),
    ('b', 'tests', reconcile.STATE, 0, json.dumps({'failure_receipt': {**RECEIPT, 'incremental_api_charge_usd': 0.2}})),
    ('b', 'tests', reconcile.STATE, 0, json.dumps({'failure_receipt': {**RECEIPT, 'response_delivered': True}})),
])
def test_anything_else_is_refused_without_writing(tmp_path, row):
    with pytest.raises(SystemExit):
        run(tmp_path, [row])
    assert not (tmp_path / 'pilot-accounting.unreconciled.json').exists()
