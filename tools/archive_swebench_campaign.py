"""Export a terminal campaign to MEM and independently verify retained streams.

Only encrypted bundles go to MEM. Recipient keys stay in a restricted directory
beside the original benchmark. A fresh verifier cannot open the original vault.
"""
import argparse
import base64
from hashlib import sha256
import json
import os
import re
from pathlib import Path
import subprocess
import sys

from atmem.core.canonical import canonical_json
from atmem.evidence.crypto import generate_recipient_keypair, generate_signing_keypair
from benchmarks.code_replay.swebench_pilot import vault


VERIFY = '''import json,sys,base64,hashlib
from pathlib import Path
from atmem.evidence.service import EvidenceService
def denied(*args,**kwargs):raise PermissionError('original vault unavailable in archive verifier')
EvidenceService.__init__=denied
from benchmarks.code_replay.archive import open_archive
from atmem.core.canonical import canonical_json
manifest=json.loads(Path(sys.argv[1]).read_text());keys=json.loads(Path(sys.argv[2]).read_text())
results=[]
for row in manifest['runs']:
 bundle=json.loads(Path(row['archive_path']).read_text())
 raw=open_archive(bundle,run_id=row['run_id'],recipient_secret_key=base64.b64decode(keys['recipient_secret']),
  trusted_signing_public_key=base64.b64decode(keys['signing_public']))
 assert hashlib.sha256(raw).hexdigest()==row['events_sha256']
 events=json.loads(raw);streams=0;grades=0;started=[];captured=[]
 for event in events:
  e=event['envelope'];p=e['payload']
  if e['event_type']=='trial.started':started.append(p['arm'])
  if e['event_type']=='trial.captured':
   captured.append(p['arm']);stdout=base64.b64decode(p['stdout_base64'],validate=True)
   stream=[json.loads(line) for line in stdout.splitlines() if line.startswith(b'{')]
   assert stream;streams+=1
  if e['event_type']=='trial.graded':grades+=1
 assert len(started)==len(set(started)) and set(captured)==set(started)
 results.append({'run_id':row['run_id'],'events':len(events),'model_streams':streams,'grades':grades,'sha256':row['events_sha256']})
print(json.dumps({'status':'verified','original_vault_access':'denied','runs':results}))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--archive-name', help='Explicit separate terminal snapshot; never replaces the final campaign archive')
    args = parser.parse_args()
    if args.archive_name and re.fullmatch(r'[A-Za-z0-9_-]{1,180}', args.archive_name) is None:
        raise ValueError('simple explicit archive name required')
    result = json.loads((args.root / 'results.json').read_text())
    if result['status'] not in {'completed', 'stopped'}:
        raise ValueError('only terminal campaigns may be archived')
    manifest = json.loads((args.root / 'manifest.json').read_text())
    destination = Path('/Volumes/MEM/AtMem-SWEbench-Threeway-20261019') / (args.archive_name or args.root.name)
    if not Path('/Volumes/MEM').is_mount():
        raise ValueError('benchmark archive volume unavailable')
    destination.mkdir(parents=True, mode=0o700, exist_ok=False)
    key_dir = args.root / ('archive-keys-' + args.archive_name if args.archive_name else 'archive-keys')
    key_dir.mkdir(mode=0o700, exist_ok=False)
    public, secret = generate_recipient_keypair()
    signing_public, signing_secret = generate_signing_keypair()
    key_file = key_dir / 'recipient.json'
    key_file.write_text(json.dumps({'recipient_secret': base64.b64encode(secret).decode(),
        'signing_public': base64.b64encode(signing_public).decode()}))
    key_file.chmod(0o600)
    os.environ['ATMEM_HOME'] = str(args.root / 'home')
    service, principal = vault(args.root)
    rows = []
    for identity in ['pilot', *(r['instance_id'] for r in manifest['selected'])]:
        events = service.inspect(principal, identity)
        if not events:
            continue
        digest = sha256(canonical_json(events).encode()).hexdigest()
        bundle = service.encrypted_archive(principal, identity, recipient_public_key=public,
            signing_public_key=signing_public, signing_secret_key=signing_secret)
        path = destination / (identity + '.json')
        path.write_text(json.dumps(bundle))
        rows.append({'run_id': identity, 'events_sha256': digest, 'archive_path': str(path)})
    archive_manifest = destination / 'manifest.json'
    archive_manifest.write_text(json.dumps({'campaign': args.root.name, 'status': result['status'], 'runs': rows}, indent=2))
    checked = subprocess.run([sys.executable, '-c', VERIFY, str(archive_manifest), str(key_file)],
                             capture_output=True, text=True, timeout=180)
    if checked.returncode:
        raise RuntimeError('independent archive verification failed: ' + checked.stderr[-1500:])
    verification = json.loads(checked.stdout)
    verification_name = ('archive-verification-' + args.archive_name + '.json') if args.archive_name else 'archive-verification.json'
    (args.root / verification_name).write_text(json.dumps(verification, indent=2))
    (destination / 'verification.json').write_text(json.dumps(verification, indent=2))
    print(json.dumps({'status': verification['status'], 'archive': str(destination),
        'runs': len(rows), 'model_streams': sum(r['model_streams'] for r in verification['runs'])}), flush=True)


if __name__ == '__main__':
    main()
