"""Archive raw apps/judge transport and latest portable memory after finalization.

Supplement incremental backups without rerunning or rewriting any experiment.
Keep the dataset private; exclude credentials, runtime profiles and storage keys.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile
import uuid

REPO = Path(__file__).resolve().parents[1]
sys.path.append(str(REPO))


def main():
    from huggingface_hub import CommitOperationAdd, HfApi, hf_hub_url
    import requests
    from benchmarks.dolphinbench.gateway import save_new
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, required=True)
    args = parser.parse_args()
    root = Path('/Volumes/AtMemDolphin/campaign-atmem-v3-matched-luna-high-20261021')
    result = json.loads((root / 'private-result.json').read_text())
    assert result['tasks'] == 600 and result['package_validation']['tests'] == 600
    assert json.loads((root / 'final-cloud-receipt.json').read_text())['download_verified']
    assert (root / 'repairs/ssd-return-to-mem-20261021.json').is_file()
    assert len(list((root / 'grades').glob('*/*.json'))) == 600
    values = {}
    for line in args.env_file.read_text().splitlines():
        match = re.match(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$', line)
        if match:
            value = match[2]
            if len(value) > 1 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            values[match[1]] = value
    secrets = [v.encode() for k, v in values.items() if len(v) >= 16
        and (re.search('KEY|TOKEN|PASSWORD|SECRET', k) or k == 'OPEN_ROUTER')]
    token, repo = values['HF_TOKEN'], 'atmem/dolphinbench-evidence-20261020'
    api = HfApi(token=token)
    assert api.repo_info(repo, repo_type='dataset').private
    files = {}
    for name in ('apps', 'judge-calls', 'repairs'):
        for path in sorted((root / name).rglob('*')):
            if path.is_file():
                assert not path.is_symlink()
                path.resolve().relative_to(root)
                files[str(path.relative_to(root))] = path
    for name in ('archive-index.json', 'run.json', 'private-result.json', 'final-summary.json',
                 'final-cloud-receipt.json', 'actual-provider-settings-receipt.json'):
        files[name] = root / name
    files['protocol.md'] = REPO / 'docs/benchmarks/dolphinbench-v3-campaign-20261021.md'
    for persona in ('morgan', 'alex', 'riley'):
        path = max((root / 'portable-memory').glob(persona + '-*.jsonl'),
            key=lambda p: int(p.stem.rsplit('-', 1)[1]))
        receipt = root / 'portable-memory' / (persona + '.json')
        expected = json.loads(receipt.read_text())['sha256']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
        files['portable-memory/' + path.name] = path
        files['portable-memory/' + receipt.name] = receipt
    manifest = {'format': 'complete-raw-benchmark-artifacts-v1', 'tasks': 600,
        'passed': result['passed'], 'private': True, 'new_inference_calls': 0,
        'original_results_changed': False,
        'code_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
        'includes': ['raw per-task apps/configuration/logs', 'raw paid-judge request/response/usage/routing',
                     'latest authorized portable memory exports for all three scopes',
                     'all recording/transfer repair receipts', 'incremental cloud coverage index',
                     'complete package verification receipts and final protocol'],
        'excluded': ['credentials', 'Hermes runtime profiles', 'storage encryption keys'], 'files': {}}
    for name, path in files.items():
        payload = path.read_bytes()
        assert not any(secret in payload for secret in secrets), 'Secret screen failed'
        manifest['files'][name] = {'sha256': hashlib.sha256(payload).hexdigest(), 'size_bytes': len(payload)}
    destination = root / 'complete-artifact-manifest.json'
    save_new(destination, manifest)
    files['manifest.json'] = destination
    prefix = f'campaigns/{root.name}'
    with tempfile.TemporaryDirectory(prefix='complete-artifacts-', dir='/Volumes/AtMemDolphin/tmp') as temporary:
        archive_path = Path(temporary) / 'complete-raw-artifacts.tar.gz'
        with tarfile.open(archive_path, 'w:gz') as archive:
            for name, path in files.items():
                archive.add(path, arcname=name, recursive=False)
        digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        remote = prefix + '/final/raw-artifacts-' + uuid.uuid4().hex + '.tar.gz'
        commit = api.create_commit(repo_id=repo, repo_type='dataset',
            commit_message='Complete raw app/judge evidence, portable memory and verified recovery index',
            operations=[CommitOperationAdd(path_in_repo=remote, path_or_fileobj=str(archive_path)),
                CommitOperationAdd(path_in_repo=prefix + '/final/raw-artifacts-manifest.json', path_or_fileobj=str(destination)),
                CommitOperationAdd(path_in_repo=prefix + '/README.md', path_or_fileobj=str(files['protocol.md']))])
        actual, size = hashlib.sha256(), 0
        with requests.get(hf_hub_url(repo, remote, repo_type='dataset', revision=commit.oid),
                headers={'Authorization': 'Bearer ' + token}, stream=True, timeout=120) as response:
            response.raise_for_status()
            for block in response.iter_content(1024 * 1024):
                actual.update(block)
                size += len(block)
        assert actual.hexdigest() == digest and size == archive_path.stat().st_size
        receipt = {'private': True, 'repository': repo, 'commit': commit.oid, 'path': remote,
            'sha256': digest, 'size_bytes': size, 'download_verified': True,
            'manifest_path': prefix + '/final/raw-artifacts-manifest.json',
            'report_path': prefix + '/README.md', 'files': len(files), 'new_inference_calls': 0}
        save_new(root / 'supplemental-cloud-receipt.json', receipt)
        print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
