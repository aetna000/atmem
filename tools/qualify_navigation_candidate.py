"""Revalidate the new installed packer on all five existing public snapshots.

Preserves prior summaries, checks exact old neutral-pack hashes, and exercises
the actual installed MCP for every snapshot. No solver or grader is launched.
"""
import json
from pathlib import Path
from benchmarks.code_replay.swebench_pilot import remote


CASES = [
    ('sympy', 'large-repo-fix/sympy-cached', 'atmem-swe-lite-2b2d648c3e2649fd89b983a2fc5c9b5a', 'repository architecture'),
    ('sphinx', 'index-fix-qualification-v2/sphinx', 'atmem-swe-lite-fd5363d4a0694d9e9b3aea6c1c260fdd', 'repository architecture'),
    ('matplotlib', 'index-fix-qualification-v2/matplotlib', 'atmem-swe-lite-0e387bf1c5d34d5a9dac549a742ec2af', 'repository architecture'),
    ('django', 'index-fix-qualification-v2/django', 'atmem-swe-lite-fea57c36fca949f48c2feccb0144c06e', 'repository architecture'),
    ('scikit-learn', 'index-fix-qualification-v2/scikit-learn', 'atmem-swe-lite-20fbb251727a4a1a9d090756892f43e7', 'fit estimator'),
]


def main():
    script = Path('tools/qualify_code_index.py').read_text()
    program = '''import subprocess,json,time
from pathlib import Path
root=Path('/home/user/atmem-swebench-20261019')
output=root/'navigation-qualification-20261019';output.mkdir(exist_ok=False)
results=[]
for name,state,source,query in job['payload']['cases']:
 directory=root/state
 old=sorted(directory.glob('summary*.json'),key=lambda p:p.stat().st_mtime)[-1]
 prior=json.loads(old.read_text())
 command=['/home/user/atmem-swebench-20261019/candidate-navigation-20261019/venv/bin/python','-I','-c',job['payload']['script'],
  '--source',str(root/'sources'/source),'--state-root',str(directory),'--reuse-state',
  '--image-id','sha256:9fed0943365daedd9ee3e2e08de8341c9b04b08c6309b1dc2c08aaaaf2abfdf1','--query',query]
 tick=time.monotonic();p=subprocess.run(command,capture_output=True,text=True,timeout=300)
 if p.returncode:raise RuntimeError('installed navigation qualification process failed: '+p.stderr[-1000:])
 value=json.loads(p.stdout)
 equal=value.get('context',{}).get('sha256')==prior.get('context',{}).get('sha256')
 row={'repository':name,'previous_summary':str(old),'exact_context_equal':equal,'summary':value}
 results.append(row);(output/'results.json').write_text(json.dumps(results,indent=2))
 print(json.dumps({'repository':name,'status':value['status'],'exact_context_equal':equal,'elapsed_s':time.monotonic()-tick}),flush=True)
 if not equal or value['status']!='passed':raise RuntimeError('installed context equivalence/transport gate failed')
'''
    result = remote(program, {'script': script, 'cases': CASES}, timeout=1600)
    print(result.stdout, flush=True)
    if result.returncode:
        raise RuntimeError(result.stderr[-2000:])


if __name__ == '__main__':
    main()
