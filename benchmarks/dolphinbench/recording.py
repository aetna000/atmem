"""Durable per-call budget reservations; uncertain requests remain charged at their bound.

Not a memory implementation. Callers must reserve *every* agent, memory and judge
request before network I/O. Unused reservations may only be released when the
caller can prove no paid request was sent. A crashed/unknown request stays reserved.
"""
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import hashlib
import json
from pathlib import Path
import sqlite3
import time


def micros(value):
    if isinstance(value, bool):
        raise ValueError('cost must be a nonnegative finite USD amount')
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0:
            raise ValueError('cost must be a nonnegative finite USD amount')
        return int((amount * 1_000_000).to_integral_value(rounding=ROUND_CEILING))
    except InvalidOperation:
        raise ValueError('invalid USD amount') from None


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False, separators=(',', ':')).encode()).hexdigest()


class BudgetLedger:
    def __init__(self, path, *, cap_usd, identity):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.connection = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        self.connection.execute('PRAGMA journal_mode=WAL')
        self.connection.execute('PRAGMA synchronous=FULL')
        self.connection.executescript('''
            CREATE TABLE IF NOT EXISTS campaign (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1), cap INTEGER NOT NULL,
                identity TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS calls (
                call_id TEXT PRIMARY KEY, phase TEXT NOT NULL, request_sha256 TEXT NOT NULL,
                reserved INTEGER NOT NULL, actual INTEGER, state TEXT NOT NULL,
                usage_json TEXT, response_sha256 TEXT, created REAL NOT NULL);
        ''')
        with self.transaction():
            row = self.connection.execute('SELECT cap,identity FROM campaign').fetchone()
            expected = (micros(cap_usd), fingerprint(identity))
            if row is None:
                self.connection.execute('INSERT INTO campaign VALUES (1,?,?)', expected)
            elif row != expected:
                raise ValueError('Campaign cap or identity changed; do not resume this ledger')

    @contextmanager
    def transaction(self):
        self.connection.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.connection.execute('COMMIT')
        except BaseException:
            self.connection.execute('ROLLBACK')
            raise

    def reserve(self, call_id, *, phase, request, maximum_usd):
        if phase not in {'ingestion', 'tests', 'judge', 'qualification'}:
            raise ValueError('invalid cost phase')
        bound = micros(maximum_usd)
        if bound <= 0 or not isinstance(call_id, str) or not call_id:
            raise ValueError('A unique call ID and positive request cost bound are required')
        with self.transaction():
            if self.connection.execute("SELECT 1 FROM calls WHERE state='overrun' LIMIT 1").fetchone():
                raise PermissionError('Provider overrun requires reconciliation before any new call')
            if self.connection.execute('SELECT 1 FROM calls WHERE call_id=?', (call_id,)).fetchone():
                raise ValueError('Call already recorded or uncertain; refusing replay')
            cap = self.connection.execute('SELECT cap FROM campaign').fetchone()[0]
            exposure = self.connection.execute(
                "SELECT COALESCE(SUM(CASE WHEN state IN ('completed','overrun') THEN actual "
                "WHEN state='reserved' THEN reserved ELSE 0 END),0) FROM calls"
            ).fetchone()[0]
            if exposure + bound > cap:
                raise PermissionError('Budget exhausted including in-flight reservations')
            self.connection.execute('INSERT INTO calls VALUES (?,?,?,?,NULL,?,NULL,NULL,?)',
                                    (call_id, phase, fingerprint(request), bound, 'reserved', time.time()))

    def complete(self, call_id, *, actual_usd, usage, response):
        for name in ('prompt_tokens', 'completion_tokens'):
            if type(usage.get(name)) is not int or usage[name] < 0:
                raise ValueError('API-reported usage required; unknown is not zero')
        actual = micros(actual_usd)
        with self.transaction():
            row = self.connection.execute('SELECT reserved,state FROM calls WHERE call_id=?', (call_id,)).fetchone()
            if row is None or row[1] != 'reserved':
                raise ValueError('Call must have exactly one outstanding reservation')
            # Retain a provider overrun honestly; the next reservation will stop.
            self.connection.execute('UPDATE calls SET actual=?,state=?,usage_json=?,response_sha256=? WHERE call_id=?',
                (actual, 'overrun' if actual > row[0] else 'completed', json.dumps(usage, allow_nan=False), fingerprint(response), call_id))
        if actual > row[0]:
            raise RuntimeError('Provider cost exceeded reservation; retained actual cost, stop and reconcile')

    def cancel_unsent(self, call_id, *, proven_unsent=False):
        if proven_unsent is not True:
            raise PermissionError('Cannot release uncertain paid work')
        with self.transaction():
            cursor = self.connection.execute("UPDATE calls SET state='unsent' WHERE call_id=? AND state='reserved'", (call_id,))
            if cursor.rowcount != 1:
                raise ValueError('No outstanding reservation')

    def totals(self):
        result = {}
        for phase, state, reserved, actual in self.connection.execute('SELECT phase,state,reserved,actual FROM calls'):
            row = result.setdefault(phase, {'actual_usd': 0, 'reserved_usd': 0, 'calls': 0})
            row['calls'] += 1
            if state in {'completed', 'overrun'}:
                row['actual_usd'] += actual
            elif state == 'reserved':
                row['reserved_usd'] += reserved
        for row in result.values():
            row['actual_usd'] /= 1_000_000
            row['reserved_usd'] /= 1_000_000
        return result

    def close(self):
        self.connection.close()
