"""Export and publish the completed October 20 evidence; never run a solver.

Stage is local-only. Publish creates a private HF dataset, verifies downloaded
bytes against the staged inventory, then makes this one evidence dataset public.
No private archive key, owner environment, SSH configuration or runtime database
is included. Original encrypted bundles remain byte-identical; readable exports
are privacy-redacted derivatives, not original signed evidence.
"""
from __future__ import annotations

import argparse
import base64
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
import shlex
import shutil
from urllib.request import urlopen

REPO = Path(__file__).resolve().parents[1]
LOCAL = Path('/Users/javadtaghia/Library/Application Support/AtMem Benchmarks')
MEM = Path('/Volumes/MEM/AtMem-SWEbench-Threeway-20261019')
REPO_ID = 'atmem/code-pruner-click-evidence-20261020'
RUNS = ('click-pruner-fourway-20261020', 'click-pruner-controlled-20261020')
ENV = Path('/Users/javadtaghia/gitlab/aetnamem/.env.atmem-c709e')
GPU_NAMES = {'qualification.json', 'last-runtime.json', 'inference-audit.jsonl',
             'install.log', 'qualification.log', 'server.py', 'cases.json'}
SECRET_PATTERNS = (
    re.compile(r'\b(?:hf_|gh[pousr]_|github_pat_|sk-ant-)[A-Za-z0-9_-]{16,}'),
    re.compile(r'-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----[\s\S]*?-----END (?:[A-Z0-9 ]+ )?PRIVATE KEY-----'),
    re.compile(r'(?i)\bBearer\s+[A-Za-z0-9_.~+/=-]{16,}'),
)


def env_values():
    values = {}
    for line in ENV.read_text().splitlines():
        for item in shlex.split(line, comments=True):
            if '=' in item:
                key, value = item.split('=', 1)
                values[key] = value
    return values


class Redactor:
    def __init__(self, secrets=()):
        self.secrets = sorted({s for s in secrets if len(s) >= 12}, key=len, reverse=True)
        self.counts = Counter()

    def text(self, text):
        for secret in self.secrets:
            self.counts['known_credential'] += text.count(secret)
            text = text.replace(secret, '[REDACTED_CREDENTIAL]')
        for pattern in SECRET_PATTERNS:
            text, count = pattern.subn('[REDACTED_CREDENTIAL]', text)
            self.counts['credential_pattern'] += count
        for pattern, replacement, category in (
            (r'/Users/javadtaghia', '/Users/benchmark', 'local_home'),
            (r'\b(?:\d{1,3}\.){3}\d{1,3}\b', '[REDACTED_IP]', 'ip_address'),
        ):
            # Do not redact numeric version pins such as torch 2.8.0+cu128.
            text, count = re.subn(pattern, replacement, text)
            self.counts[category] += count
        return text

    def value(self, value):
        if isinstance(value, dict):
            result = {}
            for key, item in value.items():
                if key == 'patch_source_bytes' and isinstance(item, dict):
                    result['patch_source_text'] = {path: self.text(base64.b64decode(encoded,
                        validate=True).decode()) if encoded is not None else None
                        for path, encoded in item.items()}
                elif key.endswith('_base64') and isinstance(item, str):
                    raw = base64.b64decode(item, validate=True)
                    result[key[:-7] + '_text'] = self.text(raw.decode('utf-8', errors='replace'))
                else:
                    result[key] = self.value(item)
            return result
        if isinstance(value, list):
            return [self.value(item) for item in value]
        return self.text(value) if isinstance(value, str) else value


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def stage(destination):
    from benchmarks.code_replay.archive import open_archive
    destination.mkdir(parents=True, exist_ok=False)
    credentials = env_values()
    secrets = [v for k, v in credentials.items()
               if any(word in k.upper() for word in ('TOKEN', 'KEY', 'SECRET', 'PASSWORD', 'VAST'))]
    redactor = Redactor(secrets)
    trials, all_events, archive_inventory = [], [], []
    for run in RUNS:
        root = LOCAL / run
        source = MEM / (run + '-gpu-complete') / (run + '.encrypted.json')
        keys = root / 'archive-keys-gpu-complete'
        raw = open_archive(json.loads(source.read_bytes()), run_id=run,
            recipient_secret_key=(keys / 'recipient.secret').read_bytes(),
            trusted_signing_public_key=(keys / 'signing.public').read_bytes())
        events = json.loads(raw)
        started = [e['envelope']['payload']['arm'] for e in events
                   if e['envelope']['event_type'] == 'trial.started']
        expected = ['native', 'cognee', 'atmem', 'atmem_pruner'] if 'fourway' in run else ['atmem', 'atmem_pruner']
        if started != expected:
            raise ValueError('all predeclared attempts must be retained')
        gpu = {}
        for event in events:
            envelope = event['envelope']
            kind, payload = envelope['event_type'], envelope['payload']
            if kind == 'pruner.gpu_artifact':
                gpu.setdefault(payload['name'], {})[payload['chunk']] = payload
            elif kind == 'harness.source_snapshot':
                # These are executable research artifacts, not user credentials.
                for name, encoded in payload['files_base64'].items():
                    if Path(name).name != name or not name.endswith('.py'):
                        raise ValueError('unsafe archived source path')
                    target = destination / 'harness' / run / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(redactor.text(base64.b64decode(encoded, validate=True).decode()))
            else:
                all_events.append({'protocol': run, 'event_type': kind,
                    'payload_json': json.dumps(redactor.value(payload), ensure_ascii=False)})
        if set(gpu) != GPU_NAMES:
            raise ValueError('complete GPU artifact inventory required')
        for name, parts in gpu.items():
            first = parts[0]
            if set(parts) != set(range(first['total_chunks'])):
                raise ValueError('missing GPU artifact chunk')
            text = ''.join(parts[i]['text'] for i in sorted(parts))
            if sha256(text.encode()).hexdigest() != first['sha256']:
                raise ValueError('GPU artifact digest mismatch')
            path = destination / 'gpu' / name
            path.parent.mkdir(exist_ok=True)
            sanitized = redactor.text(text)
            if path.exists() and path.read_text() != sanitized:
                raise ValueError('GPU artifacts differ between complete archives')
            path.write_text(sanitized)
        attempts = {e['envelope']['payload']['arm']: e['envelope']['payload'] for e in events
                    if e['envelope']['event_type'] == 'agent.attempt'}
        graded = [e['envelope']['payload'] for e in events if e['envelope']['event_type'] == 'trial.completed']
        if len(graded) != len(expected) or set(attempts) != set(expected):
            raise ValueError('missing attempt or grade')
        for grade in graded:
            row = grade['result']; arm = row['arm']; attempt = attempts[arm]
            evidence = redactor.value({'attempt': attempt, 'grade': grade})
            trial_path = destination / 'trials' / run / (arm + '.json')
            write_json(trial_path, evidence)
            trials.append({'protocol': run, 'arm': arm, 'task': row['task'],
                'task_passed': row['functional_pass'], 'tests_passed': row['grade_counts']['passed'],
                'tests_failed': row['grade_counts'].get('failed', 0),
                'input_tokens_including_cache': row['usage']['total_input_tokens'],
                'output_tokens': row['usage']['output_tokens'], 'agent_seconds': row['solver_ms'] / 1000,
                'graph_calls': row['graph_calls'], 'source_read_calls': row['source_read_calls'],
                'evidence_path': trial_path.relative_to(destination).as_posix()})
        target = destination / 'archives' / source.name
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(source, target)
        archive_inventory.append({'protocol': run, 'encrypted_archive_sha256': sha256(source.read_bytes()).hexdigest(),
                                  'decrypted_events_sha256': sha256(raw).hexdigest(), 'events': len(events)})
    (destination / 'data').mkdir()
    for name, rows in (('trials', trials), ('events', all_events)):
        (destination / 'data' / (name + '.jsonl')).write_text(''.join(
            json.dumps(row, ensure_ascii=False) + '\n' for row in rows))
    for path in REPO.glob('RandD/2026-10-20-swe-pruner*'):
        target = destination / 'reports' / path.name
        target.parent.mkdir(exist_ok=True)
        target.write_text(redactor.text(path.read_text()))
    for path in REPO.glob('specs/043-click-historical-replay/pruner-*-20261020.md'):
        target = destination / 'protocols' / path.name
        target.parent.mkdir(exist_ok=True)
        target.write_text(redactor.text(path.read_text()))
    shutil.copyfile(REPO / 'LICENSE', destination / 'LICENSE-ATMEM')
    shutil.copyfile(REPO / 'third_party/cognee/LICENSE', destination / 'LICENSE-COGNEE')
    shutil.copyfile(REPO / 'third_party/cognee/NOTICE.md', destination / 'NOTICE-COGNEE.md')
    with urlopen('https://raw.githubusercontent.com/pallets/click/8c1a0a7abbc1c36f70d1f65f3604acc46c5ce6ab/LICENSE.txt', timeout=30) as response:
        license_text = response.read(100_000).decode()
    if 'Redistribution' not in license_text or 'COPYRIGHT' not in license_text:
        raise ValueError('unexpected pinned Click license')
    (destination / 'LICENSE-CLICK').write_text(license_text)
    shutil.copyfile(REPO / 'docs/evidence/swe-pruner-20261020-dataset-card.md', destination / 'README.md')
    write_json(destination / 'verification.json', {'format': 'atmem-pruner-publication-verification-v1',
        'trials': len(trials), 'archives': archive_inventory, 'redactions': dict(redactor.counts),
        'original_archive_keys': 'retained locally, never uploaded',
        'readable_exports': 'decoded and privacy-redacted derivatives; original signatures do not apply'})
    inventory = []
    for path in sorted(destination.rglob('*')):
        if not path.is_file():
            continue
        relative = path.relative_to(destination).as_posix()
        if path.is_symlink() or any(word in relative for word in ('recipient.secret', 'signing.secret', 'ssh_key', '.env')):
            raise ValueError('forbidden publication file')
        if not relative.startswith('archives/'):
            text = path.read_text()
            if any(secret in text for secret in secrets if len(secret) >= 12) or any(p.search(text) for p in SECRET_PATTERNS):
                raise ValueError('credential scan failed: ' + relative)
        inventory.append({'path': relative, 'bytes': path.stat().st_size, 'sha256': sha256(path.read_bytes()).hexdigest()})
    write_json(destination / 'manifest.json', {'repo_id': REPO_ID, 'files': inventory})
    return {'status': 'staged', 'files': len(inventory) + 1,
            'bytes': sum(row['bytes'] for row in inventory), 'trials': len(trials)}


def publish(destination):
    from huggingface_hub import HfApi, hf_hub_download
    manifest = json.loads((destination / 'manifest.json').read_text())
    if manifest['repo_id'] != REPO_ID:
        raise ValueError('unexpected publication identity')
    inventory = {row['path']: row for row in manifest['files']}
    if {p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file()} != set(inventory) | {'manifest.json'}:
        raise ValueError('staged inventory changed')
    for name, row in inventory.items():
        path = destination / name
        if path.is_symlink() or sha256(path.read_bytes()).hexdigest() != row['sha256'] or path.stat().st_size != row['bytes']:
            raise ValueError('staged digest changed')
    token = env_values()['HF_TOKEN']
    api = HfApi(token=token)
    # Resume an empty private repository after metadata validation failure only.
    if api.repo_exists(REPO_ID, repo_type='dataset'):
        info = api.repo_info(REPO_ID, repo_type='dataset')
        files = set(api.list_repo_files(REPO_ID, repo_type='dataset'))
        if not info.private or files - {'.gitattributes'}:
            raise ValueError('nonempty or public evidence dataset already exists; do not overwrite')
    else:
        api.create_repo(REPO_ID, repo_type='dataset', private=True)
    commit = api.upload_folder(repo_id=REPO_ID, repo_type='dataset', folder_path=destination,
        commit_message='Archive all six Click trials, readable traces and original encrypted GPU evidence')
    for name in sorted(set(inventory) | {'manifest.json'}):
        remote = Path(hf_hub_download(REPO_ID, name, repo_type='dataset', revision=commit.oid, token=token))
        if sha256(remote.read_bytes()).digest() != sha256((destination / name).read_bytes()).digest():
            raise ValueError('remote digest mismatch: ' + name)
    api.update_repo_settings(REPO_ID, repo_type='dataset', private=False)
    public = HfApi(token=False).repo_info(REPO_ID, repo_type='dataset', revision=commit.oid)
    if public.private:
        raise ValueError('dataset is not public')
    return {'repo_id': REPO_ID, 'revision': commit.oid, 'url': 'https://huggingface.co/datasets/' + REPO_ID,
        'verified_files': len(inventory) + 1, 'public': True,
        'manifest_sha256': sha256((destination / 'manifest.json').read_bytes()).hexdigest()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['stage', 'publish'])
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.destination) if args.operation == 'stage' else publish(args.destination)))
