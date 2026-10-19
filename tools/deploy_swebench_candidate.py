"""Install an explicit private wheel in a new benchmark-owned Windows/WSL runtime.

The baseline is untouched. Dependencies are reused read-only from its isolated
environment; no package index, API key, GPU, owner Python or owner project is used.
"""
import argparse
import base64
from hashlib import sha256
import json
from pathlib import Path
import re

from benchmarks.code_replay.swebench_pilot import remote, validate_product_runtime

PROGRAM = '''import base64,pathlib,json,hashlib,subprocess
payload=job['payload']
raw=base64.b64decode(payload['wheel'],validate=True)
assert hashlib.sha256(raw).hexdigest()==payload['sha256']
root=pathlib.Path('/home/user/atmem-swebench-20261019')/payload['name']
root.mkdir(exist_ok=False)
wheel=root/'atmem-2.3.8-py3-none-any.whl';wheel.write_bytes(raw)
venv=root/'venv'
baseline='/home/user/atmem-swebench-20261019/venv/bin/python'
subprocess.run([baseline,'-m','venv','--without-pip',str(venv)],check=True,capture_output=True,timeout=30)
site=venv/'lib/python3.12/site-packages'
installed=subprocess.run([baseline,'-m','pip','install','--no-deps','--no-compile','--target',str(site),str(wheel)],capture_output=True,timeout=60)
if installed.returncode:raise RuntimeError('isolated candidate install failed')
(site/'atmem_benchmark_dependencies.pth').write_text('/home/user/atmem-swebench-20261019/venv/lib/python3.12/site-packages'+chr(10))
summary={'python':str(venv/'bin/python'),'wheel_path':str(wheel),'wheel_sha256':hashlib.sha256(raw).hexdigest(),'worker_image_id':payload['image_id']}
(root/'runtime.json').write_text(json.dumps(summary))
print(json.dumps(summary))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheel', type=Path, required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--image-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'candidate-[a-z0-9-]+', args.name):
        raise ValueError('new candidate-prefixed benchmark runtime name required')
    if args.output.exists():
        raise ValueError('choose a new runtime manifest output')
    raw = args.wheel.read_bytes()
    if not 1 <= len(raw) <= 10_000_000 or re.fullmatch(r'sha256:[0-9a-f]{64}', args.image_id) is None:
        raise ValueError('bounded wheel and pinned worker required')
    result = remote(PROGRAM, {'wheel': base64.b64encode(raw).decode(), 'sha256': sha256(raw).hexdigest(),
                             'name': args.name, 'image_id': args.image_id}, timeout=120)
    if result.returncode:
        raise RuntimeError('candidate deployment failed: ' + result.stderr[-1000:])
    runtime = validate_product_runtime(json.loads(result.stdout))
    args.output.write_text(json.dumps(runtime, indent=2))
    print(json.dumps(runtime), flush=True)


if __name__ == '__main__':
    main()
