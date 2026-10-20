"""Actual installed full-query source contexts on all five public validation tasks.

No model/grader. Prefix and full requests use the same frozen source/generation,
with complete protected request/response retention. No semantic utility claim.
"""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
from benchmarks.code_replay.swebench_pilot import vault, remote, validate_product_runtime


PROBE = '''import json,os,subprocess,zipfile,hashlib
from pathlib import Path
case=job['payload'];runtime=case['runtime']
wheel=Path(runtime['wheel_path']);assert hashlib.sha256(wheel.read_bytes()).hexdigest()==runtime['wheel_sha256']
site=Path(runtime['python']).parent.parent/'lib/python3.12/site-packages'
with zipfile.ZipFile(wheel) as archive:
 names=[n for n in archive.namelist() if n.startswith('atmem/') and not n.endswith('/')]
 assert all((site/n).read_bytes()==archive.read(n) for n in names)
server=case['graph']['server']
env={'PATH':str(Path(runtime['python']).parent)+':/usr/bin:/bin','HOME':case['graph']['home'],
 'ATMEM_HOME':case['graph']['home'],'LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1'}
run=subprocess.run([runtime['python'],*[a for a in server['args'] if a!='--experience']],
 input='\\n'.join(map(json.dumps,case['requests']))+'\\n',capture_output=True,text=True,env=env,timeout=400)
if run.returncode:raise RuntimeError('installed full-query MCP control failed: '+run.stderr[-1000:])
answers=[json.loads(line) for line in run.stdout.splitlines()]
assert len(answers)==len(case['requests']) and all('error' not in answer for answer in answers)
packs=[]
for answer in answers[1:]:
 assert not answer['result'].get('isError')
 pack=json.loads(answer['result']['content'][0]['text'])
 assert pack['status']=='current' and pack['format']=='atmem-code-source-pack-v1'
 assert len(pack['content'].encode())<=4096
 assert hashlib.sha256(pack['content'].encode()).hexdigest()==pack['content_sha256']
 packs.append(pack)
assert packs[0]['snapshot_id']==packs[1]['snapshot_id'] and packs[1]['content']
print(json.dumps({'responses':answers,'installed_package_files':len(names),
 'snapshot_id':packs[1]['snapshot_id'],'context_bytes':[len(p['content'].encode()) for p in packs],
 'context_sha256':[p['content_sha256'] for p in packs]}))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    runtime = validate_product_runtime(json.loads(args.runtime.read_text()))
    parent = json.loads((args.source / 'manifest.json').read_text())
    if parent.get('cohort') != 'validation' or len(parent['selected']) != 5:
        raise ValueError('all five original validation tasks required')
    os.environ['ATMEM_HOME'] = str(args.source / 'home')
    original, principal = vault(args.source)
    cases = []
    for item in parent['selected']:
        events = [event['envelope'] for event in original.inspect(principal, item['instance_id'])]
        task = next(event['payload'] for event in events if event['event_type'] == 'upstream.task')
        graph = deepcopy(next(event['payload']['graph'] for event in events
            if event['event_type'] == 'trial.configured' and event['payload']['arm'] == 'atmem_structure'))
        problem = task['problem_statement']
        if len(problem.encode()) > 4000:
            raise ValueError('full qualification query exceeds contract; refuse instead of truncating')
        prefix = problem.encode()[:1000].decode(errors='ignore')
        requests = [{'jsonrpc': '2.0', 'id': 1, 'method': 'initialize'},
            *[{'jsonrpc': '2.0', 'id': i, 'method': 'tools/call', 'params': {
                'name': 'code_context', 'arguments': {'query': query, 'budget': 4096}}}
              for i, query in ((2, prefix), (3, problem))]]
        cases.append({'identity': item['instance_id'], 'graph': graph, 'requests': requests,
            'runtime': runtime, 'query_bytes': [len(prefix.encode()), len(problem.encode())]})
    args.root.mkdir(parents=True, mode=0o700, exist_ok=False)
    os.environ['ATMEM_HOME'] = str(args.root / 'home')
    target, access = vault(args.root)
    manifest = {'format': 'atmem-full-query-context-qualification-v1', 'selected': parent['selected'],
                'product_runtime': runtime, 'model_runs': 0, 'source_campaign': args.source.name}
    (args.root / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    target.capture(run_id='pilot', kind='diagnostic.full_query_planned', principal=access,
        payload={'manifest': manifest, 'source': Path(__file__).read_text()})
    rows = []
    try:
        for case in cases:
            target.capture(run_id=case['identity'], kind='diagnostic.full_query_request', principal=access, payload=case)
            observed = remote(PROBE, case, timeout=430)
            if observed.returncode:
                raise RuntimeError('installed full-query control failed without retries: ' + observed.stderr[-1000:])
            raw = json.loads(observed.stdout)
            target.capture(run_id=case['identity'], kind='diagnostic.full_query_response', principal=access, payload=raw)
            row = {'instance_id': case['identity'], 'status': 'passed', 'query_bytes': case['query_bytes'],
                   **{key: raw[key] for key in ('snapshot_id', 'installed_package_files', 'context_bytes', 'context_sha256')}}
            rows.append(row)
            (args.root / 'results.json').write_text(json.dumps({'status': 'running', 'rows': rows}, indent=2))
            print(json.dumps(row), flush=True)
    except Exception:
        (args.root / 'results.json').write_text(json.dumps({'status': 'stopped', 'rows': rows,
            'error': 'full-query installed qualification failed; no model launch'}, indent=2))
        raise
    (args.root / 'results.json').write_text(json.dumps({'status': 'completed', 'rows': rows}, indent=2))


if __name__ == '__main__':
    main()
