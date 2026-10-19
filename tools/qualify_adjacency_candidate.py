"""Compare exact old/new packs for all five real validation issue queries."""
import json
import os
from pathlib import Path
import zipfile

from benchmarks.code_replay.swebench_pilot import remote, vault


def main():
    root = Path('/Users/javadtaghia/Library/Application Support/AtMem Benchmarks/swebench-threeway-validation-20261019')
    os.environ['ATMEM_HOME'] = str(root / 'home')
    service, principal = vault(root)
    manifest = json.loads((root / 'manifest.json').read_text())
    cases = []
    for row in manifest['selected']:
        events = service.inspect(principal, row['instance_id'])
        task = next(e['envelope']['payload'] for e in events if e['envelope']['event_type'] == 'upstream.task')
        config = next(e['envelope']['payload'] for e in events if e['envelope']['event_type'] == 'trial.configured'
                      and e['envelope']['payload']['arm'] == 'atmem_structure')
        cases.append({'identity': row['instance_id'], 'source': config['stage']['source'],
            'home': config['graph']['home'], 'db': config['graph']['db'],
            'query': task['problem_statement'].encode()[:1000].decode(errors='ignore')})
    with zipfile.ZipFile('dist/atmem-code-navigation-20261019/atmem-2.3.8-py3-none-any.whl') as z:
        baseline = z.read('atmem/knowledge/code/packing.py').decode()
    code = '''import sys,os,json,time,zipfile,hashlib,subprocess
from pathlib import Path
payload=json.load(sys.stdin)
output=Path('/home/user/atmem-swebench-20261019/adjacency-actual-query-qualification-isolated-20261019')
output.mkdir(mode=0o700,exist_ok=False)
os.environ['ATMEM_HOME']=payload['cases'][0]['home']
from atmem.memory import Memory
from atmem.code.identity import CodeIdentity
from atmem.code.application import CodeApplication
from atmem.code.knowledge_setup import mcp_configuration
from atmem.knowledge.projections import CodeKnowledge
from atmem.knowledge.code.packing import pack_generation
runtime=Path('/home/user/atmem-swebench-20261019/candidate-adjacency-20261019')
meta=json.loads((runtime/'runtime.json').read_text())
with zipfile.ZipFile(meta['wheel_path']) as z:
 names=[n for n in z.namelist() if n.startswith('atmem/') and not n.endswith('/')]
 assert all((runtime/'venv/lib/python3.12/site-packages'/n).read_bytes()==z.read(n) for n in names)
old={'__name__':'retained_navigation_baseline'};exec(compile(payload['baseline'],'<retained-packer>','exec'),old)
rows=[]
for case in payload['cases']:
 os.environ['ATMEM_HOME']=case['home'];m=Memory(case['db'],auto_vectors=False)
 try:
  scope=CodeIdentity(m.store).resolve(Path(case['source']),subject_id='swebench-pilot',profile_id='shared',agent_id='claude')
  app=CodeApplication(m,subject_id=scope.subject_id);k=CodeKnowledge(app,scope)
  generation=k.current(case['source']);assert generation
  tick=time.monotonic();a=old['pack_generation'](generation,case['query'],budget=4096);old_seconds=time.monotonic()-tick
  tick=time.monotonic();b=pack_generation(generation,case['query'],budget=4096);new_seconds=time.monotonic()-tick
  assert a==b,'actual issue source pack changed'
  assert k.current(case['source'])['snapshot_id']==generation['snapshot_id']
  server=mcp_configuration(app,scope,case['source'])['configuration']['mcpServers']['atmem_code']
  requests=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-03-26'}},
   {'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'code_context','arguments':{'query':case['query'],'budget':4096}}}]
  tick=time.monotonic();p=subprocess.run([server['command'],*server['args']],input='\\n'.join(map(json.dumps,requests))+'\\n',capture_output=True,text=True,timeout=120)
  replies=[json.loads(line) for line in p.stdout.splitlines()]
  assert p.returncode==0 and len(replies)==2 and all('error' not in r for r in replies)
  answer=json.loads(replies[-1]['result']['content'][0]['text']);assert answer['status']=='current' and answer['content']==b
  row={'identity':case['identity'],'status':'passed','exact_pack_equal':True,'bytes':len(b.encode()),
   'content_sha256':hashlib.sha256(b.encode()).hexdigest(),'old_pack_seconds':old_seconds,'new_pack_seconds':new_seconds,
   'actual_mcp_stage_seconds':time.monotonic()-tick,'installed_package_files_verified':len(names)}
  rows.append(row);(output/'results.json').write_text(json.dumps(rows,indent=2));print(json.dumps(row),flush=True)
 finally:m.close()
'''
    # Each household must be selected before importing AtMem: its key-file
    # default is intentionally resolved at import, not when ATMEM_HOME changes.
    code = code.replace("output.mkdir(mode=0o700,exist_ok=False)", "output=output/payload['cases'][0]['identity'];output.mkdir(parents=True,mode=0o700,exist_ok=False)")
    wrapper = '''import subprocess,json
for case in job['payload']['data']['cases']:
 data={**job['payload']['data'],'cases':[case]}
 r=subprocess.run(['/home/user/atmem-swebench-20261019/candidate-adjacency-20261019/venv/bin/python','-I','-c',job['payload']['code']],input=json.dumps(data),capture_output=True,text=True,timeout=400)
 print(r.stdout,flush=True)
 if r.returncode:print(r.stderr[-2000:]);raise SystemExit(r.returncode)
'''
    result = remote(wrapper, {'code': code, 'data': {'cases': cases, 'baseline': baseline}}, timeout=1130)
    print(result.stdout, flush=True)
    if result.returncode:
        raise RuntimeError('actual issue-query equivalence failed: ' + result.stderr[-1000:])


if __name__ == '__main__':
    main()
