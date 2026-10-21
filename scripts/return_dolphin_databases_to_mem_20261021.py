"""After complete cloud-verified grading, replace temporary DB links with copies.

Keep both the SSD working copies and the pre-staging external backups. Refuse
live database handles, pending journals, unexpected targets or incomplete runs.
"""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parents[1]
sys.path.append(str(REPO))


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def counts(path):
    from atmem.core.storage import HouseholdPolicy, connect
    with closing(connect(path, policy=HouseholdPolicy.load(path))) as connection:
        connection.execute('PRAGMA query_only=ON')
        assert connection.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
        return {table: connection.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0]
            for table in ('context_source_episodes', 'context_evidence_units',
                          'context_source_ranges', 'context_view_generations')}


def main():
    from atmem.locking import ProcessFileLock
    from benchmarks.dolphinbench.gateway import save_new
    run = Path('/Volumes/AtMemDolphin/campaign-atmem-v3-matched-luna-high-20261021')
    baseline = Path('/Volumes/AtMemDolphin/campaign-atmem-v3-full-r2-20261021')
    scratch = Path('/private/tmp/atmem-dolphin-sqlite-20261021-ecky77ui')
    assert json.loads((run / 'private-result.json').read_text())['tasks'] == 600
    assert json.loads((run / 'final-cloud-receipt.json').read_text())['download_verified'] is True
    assert len(list((run / 'grades').glob('*/*.json'))) == 600
    for pid in (22386, 73119):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            pass
        else:
            raise RuntimeError('Controller still exists; offline transfer refused')
    destination = run / 'repairs/ssd-return-to-mem-20261021.json'
    assert not destination.exists()
    records = []
    for persona in ('morgan', 'alex', 'riley'):
        directory = baseline / 'memory' / persona
        lock = ProcessFileLock(directory / 'control/.hermes-memory-write.lock')
        lock.acquire()
        try:
            logical = directory / 'memory.db'
            working = scratch / persona / 'memory.db'
            assert logical.is_symlink() and logical.resolve() == working
            assert sha(directory / 'memory.db.encryption.json') == sha(working.with_name('memory.db.encryption.json'))
            for path in (logical, working, directory / 'memory.db.vectors.db', working.with_name('memory.db.vectors.db')):
                handles = subprocess.run(['lsof', '-n', '-P', str(path)], capture_output=True, text=True, timeout=20)
                assert not handles.stdout.strip(), 'Live database handle remains'
            before = counts(logical)
            copies = []
            for name in ('memory.db', 'memory.db.vectors.db'):
                target, source = directory / name, scratch / persona / name
                assert target.is_symlink() and target.resolve() == source and source.is_file()
                for suffix in ('-wal', '-journal'):
                    journal = Path(str(source) + suffix)
                    assert not journal.exists() or journal.stat().st_size == 0, 'Pending journal'
                expected = sha(source)
                with tempfile.TemporaryDirectory(prefix='verified-return-', dir=directory) as staging:
                    staged = Path(staging) / name
                    shutil.copy2(source, staged)
                    staged.chmod(0o600)
                    with staged.open('rb') as stream:
                        os.fsync(stream.fileno())
                    assert sha(staged) == expected
                    os.replace(staged, target)  # Replace the link, never its SSD target.
                assert not target.is_symlink() and sha(target) == expected
                copies.append({'logical_path': str(target), 'retained_ssd_source': str(source),
                    'sha256': expected, 'size_bytes': source.stat().st_size})
            assert counts(logical) == before
            records.append({'persona': persona, 'files': copies, 'counts_before_and_after': before,
                'encrypted_quick_check': 'ok', 'pre_staging_external_backups_retained': True})
        finally:
            lock.close()
    save_new(destination, {'format': 'offline-verified-memory-return-v1', 'records': records,
        'source_files_deleted': False, 'canonical_data_changed': False,
        'only_temporary_database_symlinks_replaced': True})
    print(json.dumps({'returned_to_mem': True, 'personas': 3, 'receipt': str(destination)}))


if __name__ == '__main__':
    main()
