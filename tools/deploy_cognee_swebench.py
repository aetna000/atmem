"""Install the pinned full upstream wheel in a fresh benchmark-only WSL venv."""
import argparse
import base64
from hashlib import sha256
import json
from pathlib import Path

from benchmarks.code_replay.swebench_pilot import remote


PROGRAM = '''import base64,hashlib,json,os,subprocess,shutil
from pathlib import Path
p=job['payload']; raw=base64.b64decode(p['wheel'],validate=True)
if hashlib.sha256(raw).hexdigest()!=p['sha256']:raise ValueError('wheel digest differs')
root=Path('/home/user/atmem-swebench-20261019/cognee-runtime-20261019')
root.mkdir(mode=0o700,exist_ok=False)
wheel=root/'cognee-1.6.4-py3-none-any.whl';wheel.write_bytes(raw)
if shutil.disk_usage('/mnt/c').free<50*1024**3:raise RuntimeError('insufficient installation headroom')
subprocess.run(['python3','-m','venv',str(root/'venv')],check=True,capture_output=True)
env={'PATH':'/usr/bin:/bin','HOME':str(root),'PYTHONDONTWRITEBYTECODE':'1','PIP_CONFIG_FILE':'/dev/null'}
argv=[str(root/'venv/bin/python'),'-m','pip','--isolated','--disable-pip-version-check',
 'install','--no-cache-dir','--no-compile',str(wheel)]
with (root/'install.log').open('w') as log:
 result=subprocess.run(argv,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=900)
if result.returncode:raise RuntimeError('Cognee install failed; see benchmark-owned install.log')
frozen=subprocess.check_output([str(root/'venv/bin/python'),'-m','pip','freeze'],env=env,text=True)
(root/'dependencies.txt').write_text(frozen)
summary={'python':str(root/'venv/bin/python'),'wheel_path':str(wheel),
 'wheel_sha256':p['sha256'],'upstream_commit':p['commit'],'version':'1.6.4',
 'dependencies_sha256':hashlib.sha256(frozen.encode()).hexdigest(),
 'windows_free_gib':shutil.disk_usage('/mnt/c').free/1024**3}
(root/'runtime.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheel', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('runtime output already exists')
    raw = args.wheel.read_bytes()
    if not 1 <= len(raw) <= 20_000_000:
        raise ValueError('bounded wheel required')
    result = remote(PROGRAM, {'wheel': base64.b64encode(raw).decode(),
        'sha256': sha256(raw).hexdigest(), 'commit': 'f154b32a9e544dac73e7ddf2010327cf9988edcd'}, timeout=960)
    if result.returncode:
        raise RuntimeError(result.stderr[-1500:] + result.stdout[-1000:])
    summary = json.loads(result.stdout)
    args.output.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
