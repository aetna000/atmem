"""Relocate only cloud-verified portable exports from stopped runs on MEM.

Original paths remain usable symlinks. No database, key, ingestion, case,
repository or unverified file is moved. Copies are hash-verified first.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import uuid

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from benchmarks.dolphinbench.gateway import save_new


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def main():
    moved, total = [], 0
    for name in ('campaign-atmem-v3-product-api-full-20261021',
                 'campaign-atmem-v3-full-r2-20261021'):
        root = Path('/Volumes/AtMemDolphin') / name
        manifest = json.loads((root / 'archive-index.json').read_text())
        assert manifest['verified_batches']
        for source in sorted((root / 'portable-memory').glob('*.jsonl')):
            if source.is_symlink():
                continue
            assert source.is_file()
            relative = str(source.relative_to(root))
            expected = manifest['files'].get(relative)
            if not expected:
                continue  # Never touch an export lacking verified cloud evidence.
            assert digest(source) == expected
            target = Path('/Volumes/MEM/atmem-dolphinbench-20261020/archive') / name / relative
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if not target.exists():
                pending = target.with_name(target.name + '.' + uuid.uuid4().hex + '.pending')
                with pending.open('xb') as output, source.open('rb') as input_file:
                    os.chmod(pending, 0o600)
                    shutil.copyfileobj(input_file, output, 1024 * 1024)
                    output.flush()
                    os.fsync(output.fileno())
                assert digest(pending) == expected
                assert not target.exists()
                os.replace(pending, target)
            assert digest(target) == expected
            assert digest(source) == expected
            size = source.stat().st_size
            link = source.with_name(source.name + '.' + uuid.uuid4().hex + '.link')
            os.symlink(str(target), link)
            os.replace(link, source)  # Replace this export only after a verified copy exists.
            assert source.resolve() == target and digest(source) == expected
            moved.append({'source': str(source), 'archive': str(target), 'sha256': expected, 'size_bytes': size})
            total += size
        receipt = root / 'repairs' / ('verified-portable-relocation-' + uuid.uuid4().hex + '.json')
        save_new(receipt, {'format': 'verified-portable-export-relocation-v1',
            'source_paths_remain_resolvable': True, 'database_or_key_moved': False,
            'cloud_verified_before_move': True, 'files': [m for m in moved if m['source'].startswith(str(root) + '/')]})
    print(json.dumps({'relocated_exports': len(moved), 'bytes': total,
                      'recoverable_on_MEM_and_cloud': True, 'original_paths_resolve': True}), flush=True)


if __name__ == '__main__':
    main()
