"""Retain complete private benchmark wheels in existing encrypted MEM evidence.

Not a complete offline Docker/dependency/model reconstruction. No owner install,
publication, source mutation or solver call. Original bytes, not only hashes.
"""
import argparse
import base64
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import zipfile
from benchmarks.code_replay.swebench_pilot import vault


def wheel_metadata(raw):
    if not 1 <= len(raw) <= 10_000_000:
        raise ValueError('bounded wheel required')
    with zipfile.ZipFile(BytesIO(raw)) as archive:
        members = archive.infolist()
        if len(members) > 4096 or sum(member.file_size for member in members) > 32_000_000:
            raise ValueError('wheel expansion budget exceeded')
        if any(PurePosixPath(m.filename).is_absolute() or '..' in PurePosixPath(m.filename).parts for m in members):
            raise ValueError('unsafe wheel member')
        if not any(m.filename.startswith('atmem/') for m in members) or archive.testzip() is not None:
            raise ValueError('complete AtMem wheel required')
    return {'sha256': sha256(raw).hexdigest(), 'bytes': len(raw), 'members': len(members)}


VERIFY = '''import base64,json,sys,hashlib,io,zipfile
from pathlib import Path
from atmem.evidence.service import EvidenceService
def denied(*args,**kwargs):raise PermissionError('original evidence vault unavailable')
EvidenceService.__init__=denied
from benchmarks.code_replay.archive import open_archive
root=Path(sys.argv[1]);dest=Path(sys.argv[2])
keys=json.loads((root/'archive-keys/recipient.json').read_text());manifest=json.loads((dest/'manifest.json').read_text())
pilot=next(row for row in manifest['runs'] if row['run_id']=='pilot')
planned=json.loads(open_archive(json.loads(Path(pilot['archive_path']).read_text()),run_id='pilot',
 recipient_secret_key=base64.b64decode(keys['recipient_secret']),trusted_signing_public_key=base64.b64decode(keys['signing_public'])))
inventory=next(e['envelope']['payload']['inventory'] for e in planned if e['envelope']['event_type']=='artifact.retention_planned')
results=[]
for item in inventory:
 row=next(r for r in manifest['runs'] if r['run_id']==item['run_id'])
 raw=open_archive(json.loads(Path(row['archive_path']).read_text()),run_id=item['run_id'],
  recipient_secret_key=base64.b64decode(keys['recipient_secret']),trusted_signing_public_key=base64.b64decode(keys['signing_public']))
 events=json.loads(raw);artifacts=[e['envelope']['payload'] for e in events if e['envelope']['event_type']=='artifact.product_wheel']
 assert len(artifacts)==1
 data=base64.b64decode(artifacts[0]['content_base64'],validate=True)
 assert len(data)==item['bytes'] and hashlib.sha256(data).hexdigest()==item['sha256']
 with zipfile.ZipFile(io.BytesIO(data)) as wheel:assert wheel.testzip() is None
 results.append({'run_id':item['run_id'],'sha256':item['sha256'],'bytes':len(data),'zip_integrity':'verified'})
print(json.dumps({'status':'verified','original_vault_access':'denied','original_wheel_files_read':False,'wheels':results}))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--wheel', type=Path, action='append', required=True)
    args = parser.parse_args()
    # Validate all inputs before creating protected output; never discover or
    # glob owner files. The caller lists exact benchmark artifacts explicitly.
    artifacts = {}
    for path in args.wheel:
        if path.is_symlink() or not path.is_file() or path.suffix != '.whl':
            raise ValueError('explicit regular wheel file required')
        raw = path.read_bytes()
        meta = wheel_metadata(raw)
        artifacts.setdefault(meta['sha256'], (path, raw, meta))
    args.root.mkdir(parents=True, mode=0o700, exist_ok=False)
    os.environ['ATMEM_HOME'] = str(args.root / 'home')
    service, principal = vault(args.root)
    inventory = [{'run_id': 'wheel-' + digest[:24], 'name': path.name, **meta}
                 for digest, (path, raw, meta) in artifacts.items()]
    manifest = {'format': 'atmem-swebench-product-artifacts-v1',
        'selected': [{'instance_id': row['run_id']} for row in inventory], 'model_runs': 0,
        'claim': 'full product-wheel byte recovery only; not complete offline benchmark reconstruction'}
    (args.root / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    (args.root / 'artifact-inventory.json').write_text(json.dumps(inventory, indent=2))
    service.capture(run_id='pilot', kind='artifact.retention_planned', principal=principal,
        payload={'manifest': manifest, 'inventory': inventory, 'source': Path(__file__).read_text()})
    for row in inventory:
        path, raw, _ = artifacts[row['sha256']]
        service.capture(run_id=row['run_id'], kind='artifact.product_wheel', principal=principal,
            payload={**row, 'content_base64': base64.b64encode(raw).decode()})
    (args.root / 'results.json').write_text(json.dumps({'status': 'completed', 'rows': inventory}, indent=2))
    subprocess.run([sys.executable, '-m', 'tools.archive_swebench_campaign', '--root', str(args.root)], check=True)
    destination = Path('/Volumes/MEM/AtMem-SWEbench-Threeway-20261019') / args.root.name
    checked = subprocess.run([sys.executable, '-c', VERIFY, str(args.root), str(destination)],
                             capture_output=True, text=True, timeout=120)
    if checked.returncode:
        raise RuntimeError('archive-only full wheel recovery failed: ' + checked.stderr[-1000:])
    verification = json.loads(checked.stdout)
    (args.root / 'artifact-verification.json').write_text(json.dumps(verification, indent=2))
    (destination / 'artifact-verification.json').write_text(json.dumps(verification, indent=2))
    print(json.dumps({'status': 'verified', 'complete_wheels': len(inventory),
        'original_wheel_files_read_in_verifier': False, 'model_runs': 0}), flush=True)


if __name__ == '__main__':
    main()
