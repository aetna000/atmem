"""Prepare the one owned GPU and recover its real-source qualification."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time

from tools.vast_pruner_rental import instances

ROOT = Path(os.environ.get('ATMEM_PRUNER_GPU_ROOT', '/Users/javadtaghia/Library/Application Support/AtMem Benchmarks/swe-pruner-gpu-20261020-fallback'))
REPO = Path(__file__).parents[1]


def main():
    rental = json.loads((ROOT / 'rental.json').read_text())
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        found = [x for x in instances() if x['id'] == rental['instance_id']]
        if len(found) != 1 or found[0].get('label') != rental['label']:
            raise RuntimeError('owned instance absent or label changed')
        endpoint = found[0]
        boot = {'stage': 'boot', 'epoch': time.time(), 'status': endpoint.get('actual_status'),
                'message': str(endpoint.get('status_msg', ''))[-160:]}
        with (ROOT / 'boot.jsonl').open('a') as log:
            log.write(json.dumps(boot) + '\n')
        print(json.dumps(boot), flush=True)
        command = ['ssh', '-T', '-i', str(ROOT / 'ssh_key'), '-o', 'IdentitiesOnly=yes',
                   '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=accept-new', '-o',
                   'UserKnownHostsFile=' + str(ROOT / 'known_hosts'), '-o', 'ConnectTimeout=8',
                   '-p', str(endpoint['ssh_port']), 'root@' + endpoint['ssh_host']]
        probe = subprocess.run([*command, '/venv/main/bin/python -c "import torch,sys;print(sys.version);print(torch.__version__,torch.cuda.is_available())"'],
                               capture_output=True, text=True, timeout=15)
        if probe.returncode == 0:
            print(json.dumps({'stage': 'ssh_ready', 'runtime': probe.stdout}), flush=True)
            break
        time.sleep(10)
    else:
        raise TimeoutError('second host failed bounded boot window; no solver dispatch')
    (ROOT / 'endpoint.json').write_text(json.dumps({k: endpoint[k] for k in ('ssh_host', 'ssh_port')}, indent=2))
    server = (REPO / 'benchmarks/code_replay/swe_pruner_gpu_server.py').read_text()
    cases = json.loads((ROOT.parent / 'swe-pruner-feasibility-20261019/cpu-cases.json').read_text())
    job = {'server': server, 'cases': cases}
    program = '''import sys,json,subprocess,os
from pathlib import Path
job=json.load(sys.stdin);root=Path('/workspace/atmem-swe-pruner');root.mkdir(parents=True,exist_ok=False)
(root/'server.py').write_text(job['server']);(root/'cases.json').write_text(json.dumps(job['cases'],indent=2))
import torch
if not torch.__version__.startswith('2.8.') or not torch.cuda.is_available():raise RuntimeError('pinned CUDA PyTorch 2.8 required')
abi='TRUE' if torch._C._GLIBCXX_USE_CXX11_ABI else 'FALSE'
wheel='https://github.com/Dao-AILab/flash-attention/releases/download/v2.8.3.post2/flash_attn-2.8.3.post2%2Bcu12torch2.8cxx11abi'+abi+'-cp312-cp312-linux_x86_64.whl'
with (root/'install.log').open('x') as log:
 subprocess.run([sys.executable,'-m','pip','install','--no-cache-dir','swe-pruner==0.1.1','transformers==4.57.1','einops==0.8.1'],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
 subprocess.run([sys.executable,'-m','pip','install','--no-cache-dir','--no-deps',wheel],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
print(json.dumps({'stage':'packages_ready'}),flush=True)
with (root/'qualification.log').open('x') as log:
 subprocess.run([sys.executable,'-u',str(root/'server.py'),'--qualify'],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
print(json.dumps({'stage':'qualification_ready','qualification':json.loads((root/'qualification.json').read_text())}),flush=True)
'''
    with (ROOT / 'prepare-ready.log').open('x') as log:
        process = subprocess.Popen([*command, '/venv/main/bin/python -u -c ' + shlex.quote(program)],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log, text=True)
        process.stdin.write(json.dumps(job));process.stdin.close()
        qualification = None
        for line in process.stdout:
            log.write(line);log.flush()
            event = json.loads(line)
            if event.get('stage') == 'qualification_ready':
                qualification = event['qualification']
                (ROOT / 'qualification.json').write_text(json.dumps(qualification, indent=2))
                print(json.dumps({'stage': event['stage'], 'runtime': qualification['runtime'],
                    'cases': [{k: case[k] for k in ('id','seconds','origin_token_cnt','left_token_cnt')} for case in qualification['cases']]}), flush=True)
            else:
                print(line.strip(), flush=True)
        if process.wait(timeout=15) or qualification is None:
            raise RuntimeError('GPU preparation failed; retain remote logs and do not dispatch solvers')


if __name__ == '__main__':
    main()
