"""Private incremental evidence backups; never include profiles or service keys."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tarfile
import tempfile
import uuid


def main():
    from huggingface_hub import HfApi, CommitOperationAdd, hf_hub_url
    import requests
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--env-file', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    root.relative_to(Path('/Volumes/AtMemDolphin'))
    values = {}
    for line in args.env_file.read_text().splitlines():
        match = re.match(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$', line)
        if match:
            value = match[2]
            if len(value) > 1 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            values[match[1]] = value
    token = values['HF_TOKEN']
    secret_bytes = [v.encode() for k, v in values.items() if len(v) >= 16 and (re.search('KEY|TOKEN|PASSWORD|SECRET', k) or k == 'OPEN_ROUTER')]
    repo = 'atmem/dolphinbench-evidence-20261020'
    api = HfApi(token=token)
    if not api.repo_info(repo, repo_type='dataset').private:
        raise ValueError('Recovery repository must remain private')
    state_path = root / 'archive-index.json'
    old = json.loads(state_path.read_text()) if state_path.exists() else {'files': {}, 'verified_batches': []}
    candidates = [root / 'run.json']
    candidates.extend(root.glob('controller-error-*.json'))
    candidates.extend(root / name for name in ('private-result.json', 'live-qualification.json', 'submission.zip'))
    for name in ('ingestion', 'tests', 'grades', 'costs', 'checkpoints', 'native', 'portable-memory', 'repairs', 'subscription-transport'):
        candidates.extend(sorted((root / name).rglob('*.json')))
        if name in {'portable-memory', 'native'}:
            candidates.extend(sorted((root / name).rglob('*.jsonl')))
    selected = {}
    for path in candidates:
        if not path.is_file() or path.is_symlink():
            continue
        path.resolve().relative_to(root)
        data = path.read_bytes()
        if any(secret in data for secret in secret_bytes):
            raise ValueError('Secret screen failed; no archive uploaded')
        name = str(path.relative_to(root))
        digest = hashlib.sha256(data).hexdigest()
        if old['files'].get(name) != digest:
            selected[name] = {'sha256': digest, 'size_bytes': len(data)}
    with tempfile.TemporaryDirectory(dir='/Volumes/AtMemDolphin/tmp', prefix='cloud-batch-') as raw:
        temporary = Path(raw)
        source = sqlite3.connect(f'{(root / "budget.db").as_uri()}?mode=ro', uri=True)
        backup = sqlite3.connect(temporary / 'budget.db')
        try:
            source.backup(backup)
        finally:
            backup.close()
            source.close()
        budget_bytes = (temporary / 'budget.db').read_bytes()
        selected['accounting/budget.db'] = {'sha256': hashlib.sha256(budget_bytes).hexdigest(), 'size_bytes': len(budget_bytes)}
        manifest = {'format': 'atmem-private-benchmark-batch-v1', 'campaign': root.name,
                    'files': selected, 'previous_verified_batches': old['verified_batches'],
                    'memory_backup': 'neutral product export, not bit-exact encrypted database restore'}
        (temporary / 'manifest.json').write_text(json.dumps(manifest, indent=2))
        archive = temporary / 'batch.tar.gz'
        with tarfile.open(archive, 'w:gz') as output:
            for name in selected:
                output.add(temporary / 'budget.db' if name == 'accounting/budget.db' else root / name,
                           arcname=name, recursive=False)
            output.add(temporary / 'manifest.json', arcname='manifest.json')
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        remote = f'campaigns/{root.name}/batches/{uuid.uuid4().hex}.tar.gz'
        result = api.create_commit(repo_id=repo, repo_type='dataset',
            commit_message=f'Checkpoint {root.name}: {len(selected)} evidence files',
            operations=[CommitOperationAdd(path_in_repo=remote, path_or_fileobj=str(archive))])
        check, count = hashlib.sha256(), 0
        with requests.get(hf_hub_url(repo, remote, repo_type='dataset', revision=result.oid),
                          headers={'Authorization': 'Bearer ' + token}, stream=True, timeout=120) as response:
            response.raise_for_status()
            for chunk in response.iter_content(1024 * 1024):
                check.update(chunk)
                count += len(chunk)
        if check.hexdigest() != digest or count != archive.stat().st_size:
            raise ValueError('Independent remote archive verification failed')
        old['files'].update({name: value['sha256'] for name, value in selected.items() if name != 'accounting/budget.db'})
        old['verified_batches'].append({'path': remote, 'commit': result.oid, 'sha256': digest, 'size_bytes': count})
        pending = state_path.with_name('archive-index-' + uuid.uuid4().hex + '.pending')
        fd = os.open(pending, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'w') as output:
            json.dump(old, output)
            output.flush()
            os.fsync(output.fileno())
        os.replace(pending, state_path)
        print(json.dumps({'verified': True, 'repository': repo, 'revision': result.oid,
                          'path': remote, 'sha256': digest, 'size_bytes': count}), flush=True)


if __name__ == '__main__':
    main()
