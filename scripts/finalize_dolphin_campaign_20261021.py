"""Finish only a complete 600-task campaign; no model calls or leaderboard upload.

May watch an existing controller PID. An incomplete run fails explicitly, never
packages a subset or retries an uncertain interaction.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid
import zipfile

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / 'scripts'))
sys.path.insert(0, '/Volumes/AtMemDolphin/upstream')


def archive_final(root, env_file):
    from huggingface_hub import CommitOperationAdd, HfApi, hf_hub_url
    import requests
    from benchmarks.dolphinbench.gateway import save_new

    values = {}
    for line in env_file.read_text().splitlines():
        match = re.match(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$', line)
        if match:
            value = match[2]
            if len(value) > 1 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            values[match[1]] = value
    secrets = [v.encode() for k, v in values.items() if len(v) >= 16 and (re.search('KEY|TOKEN|PASSWORD|SECRET', k) or k == 'OPEN_ROUTER')]
    token, repo = values['HF_TOKEN'], 'atmem/dolphinbench-evidence-20261020'
    api = HfApi(token=token)
    assert api.repo_info(repo, repo_type='dataset').private
    files = {name: root / name for name in ('submission.zip', 'submission-actual-provider-settings.zip',
        'actual-provider-settings-receipt.json', 'private-result.json', 'run.json', 'final-summary.json')}
    files.update({'protocol.md': REPO / 'docs/benchmarks/dolphinbench-v3-campaign-20261021.md',
        'transport-regression-gates.xml': Path('/Volumes/AtMemDolphin/evidence/v3-product-api-transport-gates.xml'),
        'installed-product-gates.xml': Path('/Volumes/AtMemDolphin/evidence/v3-installed-native-final-gates.xml')})
    manifest = {'format': 'dolphin-complete-package-evidence-v1', 'tasks': 600, 'private': True,
        'code_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
        'files': {}}
    for name, path in files.items():
        payload = path.read_bytes()
        assert not any(secret in payload for secret in secrets), 'Secret screen failed'
        if path.suffix == '.zip':
            with zipfile.ZipFile(path) as zipped:
                for member in zipped.namelist():
                    assert not any(secret in zipped.read(member) for secret in secrets), 'ZIP secret screen failed'
        manifest['files'][name] = {'sha256': hashlib.sha256(payload).hexdigest(), 'size_bytes': len(payload)}
    with tempfile.TemporaryDirectory(dir='/Volumes/AtMemDolphin/tmp', prefix='final-evidence-') as temporary:
        directory = Path(temporary)
        manifest_path = directory / 'manifest.json'
        manifest_path.write_text(json.dumps(manifest, indent=2))
        bundle = directory / 'complete-evidence.tar.gz'
        with tarfile.open(bundle, 'w:gz') as archive:
            for name, path in files.items():
                archive.add(path, arcname=name, recursive=False)
            archive.add(manifest_path, arcname='manifest.json', recursive=False)
        digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
        remote = f'campaigns/{root.name}/final/{uuid.uuid4().hex}.tar.gz'
        commit = api.create_commit(repo_id=repo, repo_type='dataset',
            commit_message='Complete 600-task submission packages, replay proof and result',
            operations=[CommitOperationAdd(path_in_repo=remote, path_or_fileobj=str(bundle))])
        actual, count = hashlib.sha256(), 0
        with requests.get(hf_hub_url(repo, remote, repo_type='dataset', revision=commit.oid),
            headers={'Authorization': 'Bearer ' + token}, stream=True, timeout=120) as response:
            response.raise_for_status()
            for block in response.iter_content(1024 * 1024):
                actual.update(block)
                count += len(block)
        assert actual.hexdigest() == digest and count == bundle.stat().st_size
        receipt = {'private': True, 'repository': repo, 'commit': commit.oid,
                   'path': remote, 'sha256': digest, 'size_bytes': count, 'download_verified': True}
        save_new(root / 'final-cloud-receipt.json', receipt)
        print(json.dumps(receipt), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--watch-pid', type=int)
    parser.add_argument('--env-file', type=Path, required=True)
    args = parser.parse_args()
    root = Path('/Volumes/AtMemDolphin/campaign-atmem-v3-product-api-full-20261021')
    if args.watch_pid:
        while True:
            try:
                os.kill(args.watch_pid, 0)
            except ProcessLookupError:
                break
            time.sleep(30)
    from report_dolphin_campaign_20261021 import report
    from benchmarks.dolphinbench.gateway import save_new
    result = report(root)
    assert result['complete'], 'Incomplete campaign; retained evidence must be reconciled, never resampled'
    assert json.loads((root / 'private-result.json').read_text())['tasks'] == 600
    from package_dolphin_actual_settings_20261021 import main as package
    assert not (root / 'submission-actual-provider-settings.zip').exists(), 'Already finalized; inspect receipts'
    package()  # Actual wire settings only; unmodified upstream validation/replay.
    save_new(root / 'final-summary.json', result)
    archive_final(root, args.env_file)
    print(json.dumps({'complete': True, 'tasks': 600, 'passed': result['total_passed'],
                      'package_replay': 'verified', 'cloud_backup': 'download-verified'}), flush=True)


if __name__ == '__main__':
    main()
