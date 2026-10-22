"""Run-specific, reversible SSD staging under the product write barrier.

Never runs inference, changes memory algorithms, disables synchronization, or
deletes an original database. Run with the installed controller and its isolated
ATMEM_HOME, only after the original controller has exited.
"""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time

from atmem.core.storage import HouseholdPolicy, connect
from atmem.locking import ProcessFileLock
from atmem.memory import Memory

ROOT = Path('/Volumes/AtMemDolphin/campaign-atmem-v3-full-r2-20261021')
PID = 38093


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def counts(path):
    with closing(connect(path, policy=HouseholdPolicy.load(path))) as connection:
        connection.execute('PRAGMA query_only=ON')
        assert connection.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
        return {table: connection.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0]
                for table in ('context_source_episodes', 'context_evidence_units',
                              'context_source_ranges', 'context_view_generations')}


def main():
    assert shutil.disk_usage('/private/tmp').free > 2 * 1024**3
    assert not any((ROOT / 'tests').glob('*/*.json')), 'Storage staging is ingestion-only'
    try:
        os.kill(PID, 0)
    except ProcessLookupError:
        pass
    else:
        raise RuntimeError('Offline staging requires the original controller to have exited')
    scratch = Path(tempfile.mkdtemp(prefix='atmem-dolphin-sqlite-20261021-', dir='/private/tmp'))
    repair = ROOT / 'repairs' / 'ssd-working-databases-20261021.json'
    assert not repair.exists()
    records = []
    for persona in ('alex', 'riley', 'morgan'):
        directory = ROOT / 'memory' / persona
        lock = ProcessFileLock(directory / 'control' / '.hermes-memory-write.lock')
        deadline = time.monotonic() + 180
        while True:
            try:
                lock.acquire()
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise RuntimeError('No safe write-barrier gap: ' + persona)
                time.sleep(0.001)
        stopped = False
        replaced = []
        try:
            handles = subprocess.run(['lsof', '-n', '-P', str(directory / 'memory.db')],
                capture_output=True, text=True, timeout=15).stdout.splitlines()
            if handles:
                raise RuntimeError('A live database handle remains; no file was moved: ' + persona)
            source = directory / 'memory.db'
            before = counts(source)
            # Closing the final connection must have checkpointed the WAL.
            for suffix in ('-wal', '-journal'):
                pending = Path(str(source) + suffix)
                if pending.exists() and pending.stat().st_size:
                    raise RuntimeError('Uncheckpointed journal; refusing raw copy: ' + persona)
            target = scratch / persona
            target.mkdir(mode=0o700)
            files = [source, Path(str(source) + '.encryption.json')]
            vector = Path(str(source) + '.vectors.db')
            if vector.exists():
                files.append(vector)
            copies = []
            for original in files:
                assert original.is_file() and not original.is_symlink()
                destination = target / original.name
                shutil.copy2(original, destination)
                destination.chmod(0o600)
                expected = sha(original)
                assert sha(destination) == expected
                copies.append({'name': original.name, 'size_bytes': original.stat().st_size,
                               'sha256': expected})
            assert counts(target / 'memory.db') == before
            # Only DB payloads become links; the product authority/write lock,
            # binding credentials and service configuration stay in place.
            for original in (source, vector) if vector.exists() else (source,):
                backup = original.with_name(original.name + '.before-ssd-20261021')
                assert not backup.exists()
                original.rename(backup)
                replaced.append((original, backup))
                original.symlink_to(target / original.name)
            # Exercise the actual product constructor through the unchanged
            # logical path before allowing its next ordinary observation.
            with closing(Memory(source, retain_query_text=False, auto_vectors=False)) as memory:
                actual = {table: memory.store._conn.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0]
                          for table in before}
                assert actual == before
                assert memory.policy.state == 'encrypted'
            records.append({'persona': persona, 'logical_database': str(source),
                'working_directory': str(target), 'copied_files': copies,
                'counts_before_and_after': before, 'originals_retained_on_mem': True,
                'normal_product_open_verified': True, 'completed_at_unix': time.time()})
            print(json.dumps(records[-1]), flush=True)
        except BaseException:
            for original, backup in reversed(replaced):
                if original.is_symlink():
                    original.unlink()
                if backup.exists() and not original.exists():
                    backup.rename(original)
            raise
        finally:
            # A waiter retries acquisition before testing its timeout. Release
            # the write barrier *before* continuing the controller.
            lock.close()
            if stopped:
                os.kill(PID, signal.SIGCONT)
    result = {'format': 'atmem-physical-storage-operation-v1', 'controller_pid': PID,
        'working_root': str(scratch), 'database_operations': records,
        'algorithms_or_model_settings_changed': False,
        'commit_synchronization_changed': False, 'encryption_changed': False,
        'originals_deleted': False, 'archive_locations_unchanged': True,
        'all_scored_tasks_after_storage_operation': True}
    with repair.open('x') as output:
        json.dump(result, output, indent=2)
    print(json.dumps({'ssd_staging_complete': True, 'receipt': str(repair)}), flush=True)


if __name__ == '__main__':
    main()
