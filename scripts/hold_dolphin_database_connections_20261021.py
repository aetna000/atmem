"""Keep idle, query-only encrypted connections open; do not weaken WAL durability."""
import json
import os
from pathlib import Path
import signal
import time

from atmem.memory import Memory


def main():
    root = Path('/Volumes/AtMemDolphin/campaign-atmem-v3-full-r2-20261021')
    parent = 38093
    memories = []
    stopping = False

    def stop(*_args):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        for persona in ('alex', 'riley', 'morgan'):
            memory = Memory(root / 'memory' / persona / 'memory.db',
                            retain_query_text=False, auto_vectors=False)
            memories.append(memory)
            connection = memory.store._conn
            assert not connection.in_transaction
            connection.execute('PRAGMA query_only=ON')
            assert connection.execute('PRAGMA query_only').fetchone()[0] == 1
            assert not connection.in_transaction
        receipt = {
            'format': 'atmem-storage-operation-v1',
            'operation': 'hold_idle_query_only_connections',
            'controller_pid': parent, 'helper_pid': os.getpid(),
            'started_at_unix': time.time(),
            'reason': 'Avoid a full WAL checkpoint on every final connection close',
            'data_mutations': False, 'commit_synchronization_changed': False,
            'read_transactions_held': False, 'memory_algorithm_changed': False,
            'operator_only': True, 'all_data_remains_on_external_volume': True,
            'completed_histories_at_start': sum(1 for _ in (root / 'ingestion').glob('*/*.json')),
        }
        destination = root / 'repairs' / 'idle-database-connections-20261021.json'
        destination.parent.mkdir(exist_ok=True, mode=0o700)
        with destination.open('x') as output:
            json.dump(receipt, output, indent=2)
        print(json.dumps(receipt), flush=True)
        while not stopping:
            try:
                os.kill(parent, 0)
            except ProcessLookupError:
                break
            # No query or transaction is issued while the worker is running.
            time.sleep(10)
    finally:
        for memory in memories:
            memory.close()
        print(json.dumps({'connections_closed': len(memories)}), flush=True)


if __name__ == '__main__':
    main()
