"""Reconcile existing campaign cost records read-only, retaining uncertain bounds."""
from __future__ import annotations

import argparse
from decimal import Decimal
import json
from pathlib import Path
import sqlite3

from .protocol import CampaignLedger, digest


def reconcile(root: Path) -> dict:
    unique = {}
    sources = []
    for path in sorted(root.glob('*/budget.db')):
        if not (path.parent.name.startswith(('campaign-atmem-', 'campaign-v3-', 'sol-judge-'))
                or path.parent.name == 'atbot-semantic-diagnostic'):
            continue
        connection = sqlite3.connect(path.as_uri()+'?mode=ro', uri=True)
        try:
            rows = connection.execute('SELECT call_id,phase,state,actual,reserved FROM calls ORDER BY call_id').fetchall()
        finally:
            connection.close()
        sources.append({'path': str(path), 'rows': len(rows), 'row_digest': digest(rows)})
        for row in rows:
            if row[0] in unique and unique[row[0]] != row:
                raise ValueError('conflicting historical call identities; reconciliation required')
            unique[row[0]] = row
    if not unique:
        raise ValueError('no historical campaign ledger found')
    actual = sum(row[3] or 0 for row in unique.values())
    unresolved = [row for row in unique.values() if row[2] == 'reserved']
    bound = sum(row[4] for row in unresolved)
    return {'format': 'atmem-retrieval-campaign-carryover-v1', 'sources': sources,
            'unique_call_ids': len(unique), 'paid_actual_micro_usd': actual,
            'unresolved_paid_calls': len(unresolved), 'unresolved_paid_bound_micro_usd': bound,
            'total_cash_exposure_micro_usd': actual+bound,
            'subscription_failures_with_unknown_tokens': sum(row[2] == 'subscription_failure_usage_unknown' for row in unique.values()),
            'subscription_monthly_fee_allocated': False,
            'note': 'Historical 3.200023 USD total is cash exposure including unresolved bounds, not solely settled spend.'}


def book_carryover(ledger: CampaignLedger, report: dict) -> None:
    actual = report['paid_actual_micro_usd']
    prior = ledger.db.execute("SELECT state,amount FROM entries WHERE id='historical-settled'").fetchone()
    if prior is None:
        usd = str(Decimal(actual)/1_000_000)
        ledger.reserve('historical-settled', usd)
        ledger.settle('historical-settled', usd)
    elif prior != ('spent', actual):
        raise ValueError('historical settled charges changed; reconcile before dispatch')
    bound = report['unresolved_paid_bound_micro_usd']
    if bound:
        ledger.reserve('historical-uncertain', str(Decimal(bound)/1_000_000))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--ledger', type=Path)
    args = parser.parse_args()
    report = reconcile(args.root.resolve())
    if args.ledger:
        ledger = CampaignLedger(args.ledger)
        try:
            book_carryover(ledger, report)
            # Phase allocation bounds, not permission or a price quote. Existing
            # per-request transport ledgers must remain within their allocation.
            ledger.reserve('final-600-and-comparator', '200')
            ledger.reserve('confidence-and-judging', '40')
            report['new_campaign_ledger'] = ledger.snapshot()
        finally:
            ledger.close()
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
