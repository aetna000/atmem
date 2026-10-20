"""Archive exact Click evidence and publish redacted derivatives, never a solver.

SWE evaluator/reference material stays out of this public export. Its metric
projection may be included explicitly after the pilot is complete.
"""
import argparse
import base64
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

from atmem.core.canonical import canonical_json
from atmem.evidence.crypto import generate_recipient_keypair, generate_signing_keypair
from benchmarks.code_replay.archive import seal, open_archive
from benchmarks.code_replay.discovery_swebench import evidence
from tools.publish_pruner_evidence import Redactor, env_values, SECRET_PATTERNS
from tools.report_discovery_campaign import project

REPO = Path(__file__).resolve().parents[1]
REPO_ID = 'atmem/code-discovery-benchmark-evidence-20261020'
RAM = Path('/Volumes/AtMemReplayRAM-20261017-Localization')
ROOTS = [RAM / name for name in (
    'discovery-044-qualification-20261020', 'discovery-044-qualification-20261020-r2',
    'discovery-044-qualification-20261020-r3', 'discovery-044-click-screen-20261020',
    'discovery-044-click-requested-20261020')]


def write_json(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def publication_files(destination):
    return [p for p in sorted(destination.rglob('*')) if p.is_file() and not any(
        part.startswith('._') or part == '.DS_Store' for part in p.relative_to(destination).parts)]


def stage(destination, swe_metrics=None):
    if not Path('/Volumes/MEM').is_mount() or not destination.is_relative_to(Path('/Volumes/MEM')):
        raise ValueError('explicit benchmark-only MEM publication destination required')
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    values = env_values()
    secrets = [v for k,v in values.items() if any(x in k.upper() for x in ('KEY', 'TOKEN', 'PASSWORD', 'SECRET'))]
    redactor = Redactor(secrets)
    private = Path('/Users/javadtaghia/Library/Application Support/AtMem Benchmarks/discovery-044-publication-keys-20261020')
    private.mkdir(mode=0o700, exist_ok=False)
    public, secret = generate_recipient_keypair()
    signing_public, signing_secret = generate_signing_keypair()
    keyfile = private / 'recovery.json'
    write_json(keyfile, {'recipient_secret': base64.b64encode(secret).decode(),
        'signing_public': base64.b64encode(signing_public).decode()})
    keyfile.chmod(0o600)
    archives, traces, trials = [], [], []
    (destination / 'archives').mkdir()
    for root in ROOTS:
        vault, principal = evidence(root)
        runs = ['campaign', *sorted(p.name for p in root.iterdir() if p.is_dir() and re.fullmatch(
            '[a-f0-9]{7}-(claude|codex|copilot)-(native|cognee|atmem)', p.name))]
        for run in runs:
            retained = vault.inspect(principal, run)
            if not retained:
                continue
            raw = canonical_json(retained).encode()
            bundle = seal(raw, run_id=run, recipient_public_key=public,
                signing_public_key=signing_public, signing_secret_key=signing_secret)
            name = 'archives/' + root.name + '--' + run + '.encrypted.json'
            write_json(destination / name, bundle)
            if open_archive(bundle, run_id=run, recipient_secret_key=secret, trusted_signing_public_key=signing_public) != raw:
                raise RuntimeError('archive byte roundtrip failed')
            archives.append({'path': name, 'run_id': run, 'events_sha256': sha256(raw).hexdigest(), 'events': len(retained)})
            for event in retained:
                envelope = event['envelope']; payload = envelope['payload']
                if envelope['event_type'] == 'discovery.attempt':
                    payload = {k + '_text' if k in {'stdout', 'stderr'} else k:
                        base64.b64decode(v, validate=True).decode(errors='replace') if k in {'stdout', 'stderr'} else v
                        for k,v in payload.items()}
                if envelope['event_type'] == 'discovery.patch' and isinstance(payload.get('source_bytes_base64'), dict):
                    payload = {**payload, 'patch_source_text': {name: base64.b64decode(value, validate=True).decode()
                        if value is not None else None for name,value in payload['source_bytes_base64'].items()}}
                    payload.pop('source_bytes_base64')
                traces.append({'protocol': root.name, 'run_id': run, 'event_type': envelope['event_type'],
                    'payload_json': json.dumps(redactor.value(payload), ensure_ascii=False)})
        if 'click-' in root.name:
            result = project(vault, principal)
            for row in result['rows']:
                trials.append({'protocol': root.name, 'task': row['task'], 'host': row['host'], 'backend': row['backend'],
                    'task_passed': row['functional_pass'], 'input_tokens_including_cache': row['usage']['input_tokens'],
                    'output_tokens': row['usage']['output_tokens'], 'cached_input_tokens': row['usage']['cached_input_tokens'],
                    'agent_seconds': row['solver_ms']/1000, 'index_seconds': row['index_ms']/1000,
                    'setup_seconds_including_index': row['setup_ms']/1000,
                    'discovery_attempts': row['discovery_attempts'], 'nonempty_discovery_responses': row['nonempty_discovery_responses'],
                    'discovery_errors': row['discovery_errors'], 'usage_complete': row['usage']['complete']})
    if swe_metrics:
        metrics = json.loads(swe_metrics.read_text())
        # Strict metric allowlist, never the SWE evaluator task/gold/trace bytes.
        allowed = {'run', 'host', 'backend', 'instance_id', 'usage', 'solver_ms', 'exit_code', 'stop',
            'index_ms', 'setup_ms', 'tool_calls', 'discovery_calls', 'discovery_errors', 'discovery_ms', 'response_bytes',
            'source_read_coverage', 'treatment_used', 'functional_pass', 'grade_valid', 'resolution', 'grader_seconds',
            'patch_violations', 'discovery_attempts', 'ready_discovery_responses', 'nonempty_discovery_responses', 'usage_scope'}
        write_json(destination / 'swe-pilot-metrics.json', {'rows': [
            {k:v for k,v in row.items() if k in allowed} for row in metrics['rows']],
            'classification': 'one_qualification_task_not_full_verified_score'})
        for row in metrics['rows']:
            trials.append({'protocol': 'swe-verified-qualification-requested-consultation',
                'task': row['instance_id'], 'host': row['host'], 'backend': row['backend'],
                'task_passed': row['functional_pass'], 'input_tokens_including_cache': row['usage']['input_tokens'],
                'output_tokens': row['usage']['output_tokens'], 'cached_input_tokens': row['usage']['cached_input_tokens'],
                'agent_seconds': row['solver_ms']/1000, 'index_seconds': row['index_ms']/1000,
                'setup_seconds_including_index': row['setup_ms']/1000,
                'discovery_attempts': row['discovery_attempts'], 'nonempty_discovery_responses': row['nonempty_discovery_responses'],
                'discovery_errors': row['discovery_errors'], 'usage_complete': row['usage']['complete']})
    for filename, rows in (('trials.jsonl', trials), ('traces.jsonl', traces)):
        with (destination / filename).open('x') as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False) + '\n')
    for source, name in ((REPO / 'LICENSE', 'LICENSE-ATMEM'), (REPO / 'third_party/cognee/LICENSE', 'LICENSE-COGNEE')):
        shutil.copyfile(source, destination / name)
    from benchmarks.code_replay.discovery_click import WHEEL, WHEEL_SHA
    if sha256(WHEEL.read_bytes()).hexdigest() != WHEEL_SHA:
        raise ValueError('frozen source-preview wheel changed')
    (destination / 'artifacts').mkdir()
    shutil.copyfile(WHEEL, destination / 'artifacts/atmem-2.3.8-py3-none-any.whl')
    click_license = subprocess.check_output(['git', '-C', '/Volumes/MEM/AtMem-Code-Replay-20261017/upstream/click',
        'show', '8c1a0a7abbc1c36f70d1f65f3604acc46c5ce6ab:LICENSE.txt'])
    (destination / 'LICENSE-CLICK').write_bytes(click_license)
    shutil.copyfile(REPO / 'docs/evidence/discovery-044-dataset-card.md', destination / 'README.md')
    write_json(destination / 'archive-verification.json', {'runs': archives, 'redactions': dict(redactor.counts),
        'private_keys': 'owner-local only, not uploaded', 'original_archives': 'signed/encrypted byte-identical event exports',
        'derivatives': 'decoded privacy-redacted text; original signatures do not apply'})
    # Independent process: the original evidence service cannot even initialize.
    verify = ('import json,base64,sys;from pathlib import Path;from hashlib import sha256;'
        'from atmem.evidence.service import EvidenceService;'
        'EvidenceService.__init__=lambda *a,**k:(_ for _ in ()).throw(PermissionError("original vault denied"));'
        'from benchmarks.code_replay.archive import open_archive;'
        'root=Path(sys.argv[1]);keys=json.loads(Path(sys.argv[2]).read_text());'
        'rows=json.loads((root/"archive-verification.json").read_text())["runs"];'
        'result=[sha256(open_archive(json.loads((root/r["path"]).read_text()),run_id=r["run_id"],'
        'recipient_secret_key=base64.b64decode(keys["recipient_secret"]),'
        'trusted_signing_public_key=base64.b64decode(keys["signing_public"]))).hexdigest()==r["events_sha256"] for r in rows];'
        'assert all(result);print(json.dumps({"verified_runs":len(result),"original_vault_access":"denied"}))')
    checked = subprocess.run([sys.executable, '-c', verify, str(destination), str(keyfile)], capture_output=True, text=True, timeout=180)
    if checked.returncode:
        raise RuntimeError('independent archive verification failed: ' + checked.stderr[-1000:])
    write_json(destination / 'standalone-recovery.json', json.loads(checked.stdout))
    return finalize(destination)


def finalize(destination):
    if (destination / 'manifest.json').exists():
        raise ValueError('manifest already finalized')
    values = env_values()
    secrets = [v for k,v in values.items() if any(x in k.upper() for x in ('KEY', 'TOKEN', 'PASSWORD', 'SECRET'))]
    verification = json.loads((destination / 'archive-verification.json').read_text())
    keyfile = Path('/Users/javadtaghia/Library/Application Support/AtMem Benchmarks/discovery-044-publication-keys-20261020/recovery.json')
    keys = json.loads(keyfile.read_text())
    expected = {'README.md', 'LICENSE-ATMEM', 'LICENSE-COGNEE', 'LICENSE-CLICK', 'trials.jsonl', 'traces.jsonl',
        'archive-verification.json', 'standalone-recovery.json', 'swe-pilot-metrics.json', 'artifacts/atmem-2.3.8-py3-none-any.whl'}
    for row in verification['runs']:
        expected.add(row['path'])
        raw = open_archive(json.loads((destination / row['path']).read_text()), run_id=row['run_id'],
            recipient_secret_key=base64.b64decode(keys['recipient_secret']),
            trusted_signing_public_key=base64.b64decode(keys['signing_public']))
        if sha256(raw).hexdigest() != row['events_sha256']:
            raise ValueError('archive changed after standalone verification')
    if {p.relative_to(destination).as_posix() for p in publication_files(destination)} - expected:
        raise ValueError('unregistered public artifact')
    inventory = []
    for path in publication_files(destination):
        relative = path.relative_to(destination).as_posix()
        if path.is_symlink() or path.name == 'recovery.json' or any(s in relative for s in ('.env', '.secret', 'ssh_key')):
            raise ValueError('forbidden public artifact')
        if not relative.startswith('archives/'):
            if path.suffix == '.whl':
                with zipfile.ZipFile(path) as archive:
                    text = '\n'.join(archive.read(name).decode(errors='replace') for name in archive.namelist() if not name.endswith('/'))
            else:
                text = path.read_text()
            if any(secret in text for secret in secrets if len(secret) >= 12) or any(p.search(text) for p in SECRET_PATTERNS):
                raise ValueError('credential scan failed')
        inventory.append({'path': relative, 'bytes': path.stat().st_size, 'sha256': sha256(path.read_bytes()).hexdigest()})
    write_json(destination / 'manifest.json', {'repo_id': REPO_ID, 'files': inventory})
    return {'status': 'staged', 'task_attempts': len((destination/'trials.jsonl').read_text().splitlines()),
        'files': len(inventory)+1, 'bytes': sum(r['bytes'] for r in inventory),
        'recovery': json.loads((destination/'standalone-recovery.json').read_text())}


def publish(destination):
    from huggingface_hub import HfApi, hf_hub_download
    manifest = json.loads((destination / 'manifest.json').read_text())
    if manifest['repo_id'] != REPO_ID:
        raise ValueError('unexpected dataset identity')
    inventory = {r['path']: r for r in manifest['files']}
    if {p.relative_to(destination).as_posix() for p in publication_files(destination)} != set(inventory) | {'manifest.json'}:
        raise ValueError('staging membership changed')
    for name,row in inventory.items():
        if sha256((destination/name).read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('staging digest changed')
    token = env_values()['HF_TOKEN']
    api = HfApi(token=token)
    if api.repo_exists(REPO_ID, repo_type='dataset'):
        info = api.repo_info(REPO_ID, repo_type='dataset')
        if not info.private or set(api.list_repo_files(REPO_ID, repo_type='dataset')) - {'.gitattributes'}:
            raise ValueError('refuse overwrite of nonempty/public dataset')
    else:
        api.create_repo(REPO_ID, repo_type='dataset', private=True)
    commit = api.upload_folder(repo_id=REPO_ID, repo_type='dataset', folder_path=destination,
        ignore_patterns=['._*', '**/._*', '.DS_Store', '**/.DS_Store'],
        commit_message='Archive both discovery conditions, every Click attempt and real qualification failures')
    uploaded = set(api.list_repo_files(REPO_ID, repo_type='dataset', revision=commit.oid))
    if uploaded != set(inventory) | {'manifest.json', '.gitattributes'}:
        raise RuntimeError('remote file membership differs from verified publication inventory')
    for name in sorted(set(inventory) | {'manifest.json'}):
        downloaded = Path(hf_hub_download(REPO_ID, name, repo_type='dataset', revision=commit.oid, token=token))
        if sha256(downloaded.read_bytes()).digest() != sha256((destination/name).read_bytes()).digest():
            raise RuntimeError('immutable downloaded digest differs')
    api.update_repo_settings(REPO_ID, repo_type='dataset', private=False)
    if api.repo_info(REPO_ID, repo_type='dataset').private:
        raise RuntimeError('public visibility unverified')
    return {'status': 'published_verified', 'repo_id': REPO_ID, 'revision': commit.oid, 'files': len(inventory)+1}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('stage', 'finalize', 'publish'))
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--swe-metrics', type=Path)
    args = parser.parse_args()
    action = stage(args.destination, args.swe_metrics) if args.mode == 'stage' else finalize(args.destination) if args.mode == 'finalize' else publish(args.destination)
    print(json.dumps(action))


if __name__ == '__main__':
    main()
