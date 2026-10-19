"""Retain complete benchmark-owned upstream preparation logs in encrypted evidence."""
import argparse
import base64
from hashlib import sha256
import json
import os
from pathlib import Path
import re

from benchmarks.code_replay.swebench_pilot import vault, remote, REMOTE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    result = json.loads((args.root / 'results.json').read_text())
    if result['status'] not in {'completed', 'stopped'}:
        raise ValueError('capture preparation logs only after the campaign is terminal')
    manifest = json.loads((args.root / 'manifest.json').read_text())
    os.environ['ATMEM_HOME'] = str(args.root / 'home')
    service, principal = vault(args.root)
    captured = 0
    for row in manifest['selected']:
        identity = row['instance_id']
        events = service.inspect(principal, identity)
        if any(e['envelope']['event_type'] == 'provider.preparation_log_manifest' for e in events):
            continue
        stages = [e['envelope']['payload']['stage'] for e in events
                  if e['envelope']['event_type'] == 'trial.source_staged'
                  and e['envelope']['payload']['arm'] == 'cognee_structure']
        if not stages:
            continue
        stage = stages[-1]
        name = Path(stage['source']).name
        if re.fullmatch('atmem-swe-lite-[a-f0-9]{32}', name) is None:
            raise ValueError('exact benchmark stage required')
        response = remote('''import json,base64,hashlib
from pathlib import Path
root=Path('/home/user/atmem-swebench-20261019/cognee-states')/job['payload']['name']
files=list((root/'logs').glob('*.log'))
if (root/'index-stderr.log').exists():files.append(root/'index-stderr.log')
if any(p.is_symlink() or p.stat().st_size>8000000 for p in files):raise ValueError('unexpected log member')
if sum(p.stat().st_size for p in files)>32000000:raise ValueError('preparation log budget exceeded')
print(json.dumps([{'path':str(p.relative_to(root)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
 'payload_base64':base64.b64encode(p.read_bytes()).decode()} for p in sorted(files)]))
''', {'name': name}, timeout=45)
        if response.returncode:
            raise RuntimeError('upstream preparation log capture failed')
        receipts = []
        for item in json.loads(response.stdout):
            raw = base64.b64decode(item['payload_base64'], validate=True)
            if sha256(raw).hexdigest() != item['sha256']:
                raise ValueError('preparation log integrity mismatch')
            chunks = []
            for start in range(0, len(raw), 6_000_000):
                chunks.append(service.capture(run_id=identity, kind='provider.preparation_log_chunk', principal=principal,
                    payload={'provider': 'actual_upstream_cognee', 'path': item['path'], 'offset': start,
                        'payload_base64': base64.b64encode(raw[start:start + 6_000_000]).decode()}))
            receipts.append({'path': item['path'], 'bytes': len(raw), 'sha256': item['sha256'], 'chunks': chunks})
        service.capture(run_id=identity, kind='provider.preparation_log_manifest', principal=principal,
            payload={'provider': 'actual_upstream_cognee', 'stage': name, 'logs': receipts,
                     'truncated': False, 'public_source_benchmark_only': True})
        captured += len(receipts)
    print(json.dumps({'logs_retained_encrypted': captured}), flush=True)


if __name__ == '__main__':
    main()
