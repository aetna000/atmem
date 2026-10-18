"""Offline pinned-CLI read/exec/network controls using the frozen model policy."""
import base64
from concurrent.futures import ThreadPoolExecutor,as_completed
import json
import subprocess

PREVIOUS='external-windows-confirmation-v3-sandbox-v1-20261018'
RUN='external-windows-confirmation-v3-sandbox-v2-20261018'
STAGING='external-windows-confirmation-v3-staging-v1-20261018'


def model_prefix(source):
    marker="auth=session.cli_home/'auth.json';memory=None"
    if source.count(marker)!=1:raise ValueError('exact frozen pre-auth model prefix required')
    prefix=source.split(marker)[0]
    if 'auth.write_bytes(' in prefix or 'run_cli(session,' in prefix:
        raise ValueError('sandbox controls must not copy credentials or invoke a model')
    return prefix


PROGRAM=r'''
import os,json,base64,subprocess,socket,threading
exec(job['model_prefix'])
environment={'PATH':'/usr/bin:/bin','CODEX_HOME':str(session.cli_home),'LANG':'C.UTF-8','TMPDIR':str(session.temporary)}
canary=session.cli_home/'private-read-canary-v3'
value=('BENCHMARK_PRIVATE_CANARY_'+os.urandom(16).hex()).encode()
with canary.open('xb') as stream:stream.write(value)
canary.chmod(0o600)
listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(4);listener.settimeout(.2)
port=listener.getsockname()[1];stop=threading.Event();connections=[]
def serve():
 while not stop.is_set():
  try:client,_=listener.accept()
  except socket.timeout:continue
  except OSError:break
  with client:connections.append(True);client.sendall(b'NETWORK_CANARY_OK')
thread=threading.Thread(target=serve,daemon=True);thread.start()
def retained(command):
 proc=subprocess.run(command,env=environment,cwd=session.workspace,capture_output=True,timeout=45)
 return {'command':command,'exit_code':proc.returncode,'stdout_base64':base64.b64encode(proc.stdout).decode(),
         'stderr_base64':base64.b64encode(proc.stderr).decode()}
try:
 baseline="from pathlib import Path\nimport socket,os\nassert os.geteuid()==1000\nassert Path("+repr(str(canary))+").read_bytes()=="+repr(value)+"\nassert Path("+repr(job['probe_source'])+").is_file()\nwith socket.create_connection(('127.0.0.1',"+str(port)+"),timeout=3) as c: assert c.recv(64)==b'NETWORK_CANARY_OK'\nprint('UNRESTRICTED_CANARY_OK')\n"
 unrestricted=retained(['/usr/bin/python3','-I','-c',baseline])
 denied=[str(Path(case['operator'])/'preset.json')]
 if arm!='native':denied.extend([case['database'],str(Path(case['atmem_home'])/'identity/keys/db.key')])
 probe="from pathlib import Path\nimport subprocess,socket,os\nassert os.geteuid()==1000\nassert Path("+repr(job['probe_source'])+").is_file()\n"
 probe+="try:\n Path("+repr(str(canary))+").read_bytes()\nexcept PermissionError:\n pass\nelse:\n raise RuntimeError('owned private canary readable inside sandbox')\n"
 for path in denied:
  probe+="try:\n Path("+repr(path)+").read_bytes()\nexcept (PermissionError,FileNotFoundError):\n pass\nelse:\n raise RuntimeError('private benchmark file readable')\n"
 probe+="try:\n subprocess.run(['/mnt/c/Windows/System32/wsl.exe','-d','Ubuntu','-u','root','--','true'],capture_output=True,timeout=5)\nexcept (PermissionError,FileNotFoundError):\n pass\nelse:\n raise RuntimeError('privileged broker executable')\n"
 probe+="try:\n c=socket.create_connection(('127.0.0.1',"+str(port)+"),timeout=3)\nexcept OSError:\n pass\nelse:\n c.close()\n raise RuntimeError('controlled host listener reachable inside sandbox')\nprint('V3_SANDBOX_BOUNDARIES_OK')\n"
 command=[str(cli),'sandbox','-C',str(session.workspace),'-P','click-replay',*permission_arguments(),'/usr/bin/python3','-I','-c',probe]
 sandbox=retained(command)
 qualified=(unrestricted['exit_code']==0 and base64.b64decode(unrestricted['stdout_base64']).strip()==b'UNRESTRICTED_CANARY_OK'
  and sandbox['exit_code']==0 and base64.b64decode(sandbox['stdout_base64']).strip()==b'V3_SANDBOX_BOUNDARIES_OK' and len(connections)==1)
 print(json.dumps({'qualified':qualified,'uid':os.geteuid(),'unrestricted':unrestricted,'sandbox':sandbox,
  'host_listener_connections':len(connections),'canary_path':str(canary),'canary_base64':base64.b64encode(value).decode(),
  'model_calls':0,'credentials_copied':False,'network_scope':'controlled loopback listener unreachable; frozen network-disabled policy unchanged'}),flush=True)
finally:
 stop.set();listener.close();thread.join(timeout=2)
 if canary.read_bytes()!=value:raise ValueError('owned benchmark canary changed; do not delete unexpected data')
 canary.unlink()
'''


def hidden_view_program():
    before='except PermissionError:\\n pass\\nelse:\\n raise RuntimeError(\'owned private canary readable inside sandbox\')'
    after=before.replace('except PermissionError:', 'except (PermissionError,FileNotFoundError):')
    if PROGRAM.count(before)!=1:raise ValueError('exact canary denial expectation required')
    return PROGRAM.replace(before,after)


def hidden_canary_failure(result):
    if result.get('exit_code')!=0:return False
    worker=json.loads(base64.b64decode(result['stdout_base64'],validate=True))
    if (worker.get('qualified') is not False or worker.get('uid')!=1000
            or worker.get('model_calls')!=0 or worker.get('credentials_copied') is not False
            or worker.get('host_listener_connections')!=1):return False
    unrestricted,sandbox=worker['unrestricted'],worker['sandbox']
    error=base64.b64decode(sandbox['stderr_base64'],validate=True)
    return (unrestricted['exit_code']==0 and base64.b64decode(unrestricted['stdout_base64'],validate=True).strip()==b'UNRESTRICTED_CANARY_OK'
        and sandbox['exit_code']==1 and not base64.b64decode(sandbox['stdout_base64'],validate=True)
        and error.endswith(('FileNotFoundError: [Errno 2] No such file or directory: '+repr(worker['canary_path'])+'\n').encode())
        and repr(worker['canary_path']) in unrestricted['command'][-1])


def main():
    from atmem.evidence import EvidenceScope,EvidencePrincipal,EvidenceRole
    from benchmarks.code_replay.run_evidence import operational_evidence
    from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
    from benchmarks.code_replay.windows_confirmation_exports import recover_export
    from benchmarks.code_replay.windows_transport import framed_command,framed_input
    from benchmarks.code_replay.eligibility_binding import SOURCE_PROFILES
    scope=EvidenceScope('benchmark','local-operator','click-20261017')
    principal=EvidencePrincipal('local-benchmark-operator',EvidenceRole.ADMINISTRATOR,scope)
    vault=operational_evidence(EVIDENCE_ROOT,vault_id='confirmation-v1',scope=scope,writing_run=RUN)
    if vault.inspect(principal,RUN):raise ValueError('sandbox batch already attempted; inspect original handle')
    previous=vault.inspect(principal,PREVIOUS)
    old_ends=[e['envelope']['payload'] for e in previous if e['envelope']['event_type']=='external.v3_sandbox_completed']
    old_plans=[e['envelope']['payload'] for e in previous if e['envelope']['event_type']=='external.v3_sandbox_planned']
    if (len(old_ends)!=1 or len(old_plans)!=1 or old_plans[0]['worker_source']!=PROGRAM
            or len(old_ends[0]['results'])!=76 or old_ends[0]['all_76_cases_qualified'] is not False
            or old_ends[0]['model_calls']!=0):raise ValueError('exact terminal zero-model canary failures required')
    for row in old_ends[0]['results']:
        es=vault.inspect(principal,row['task_run'])
        rs=[e['envelope']['payload'] for e in es if e['envelope']['event_type']=='external.v3_sandbox_case_result']
        if len(rs)!=1 or not hidden_canary_failure(rs[0]):raise ValueError('original failure is not proved hidden-canary visibility')
    events=vault.inspect(principal,STAGING)
    def rows(kind):return [e['envelope']['payload'] for e in events if e['envelope']['event_type']==kind]
    manifests=rows('external.confirmation_v3_manifest_frozen');ends=rows('external.confirmation_v3_staging_completed')
    cases=rows('external.confirmation_v3_block_result')
    if len(manifests)!=1 or len(ends)!=1 or not ends[0]['all_76_cases_staged'] or len(cases)!=38:
        raise ValueError('complete fresh v3 staging required')
    manifest=manifests[0];prefix=model_prefix(manifest['model_program']);worker=hidden_view_program()
    if old_plans[0]['model_prefix']!=prefix:raise ValueError('frozen model permission policy changed')
    probes={}
    for identity,d in manifest['source_descriptors'].items():
        source=recover_export(vault.inspect(principal,d['export_run']),d)
        roots,_=SOURCE_PROFILES[identity.rsplit('-',1)[0].replace('__','/')]
        probes[identity]=next(n for n in sorted(source['files_base64']) if n.endswith('.py') and any(n.startswith(r) for r in roots))
    def save(kind,payload):return vault.capture(run_id=RUN,kind=kind,principal=principal,payload=payload)
    save('external.v3_sandbox_planned',{'driver_source':job['driver_source'],'worker_source':worker,
        'model_prefix':prefix,'cases':76,'max_workers':4,'model_calls':0,'credentials_copied':False,
        'policy_source':'exact frozen model prefix before credential handling/inference',
        'previous_run':PREVIOUS,'correction':'accept hidden-view ENOENT after positive unrestricted canary control; policy unchanged'})
    def check(row,arm):
        block=row['block'];slot=block['slot'];identity=block['instance_id'];case=row['cases'][arm]
        task_run=RUN+'-block-'+str(slot)+'-'+arm
        target=operational_evidence(EVIDENCE_ROOT,vault_id='confirmation-v1',scope=scope,writing_run=task_run)
        if target.inspect(principal,task_run):raise ValueError('sandbox case already attempted')
        def retain(kind,payload):return target.capture(run_id=task_run,kind=kind,principal=principal,payload=payload)
        payload={'program':worker,'model_prefix':prefix,'case':case,'arm':arm,
                 'product_python':manifest['product_python'],'cli_sha256':manifest['cli_sha256'],
                 'mcp_helpers':manifest['mcp_helpers'],'runner':manifest['runner'],'probe_source':probes[identity]}
        retain('external.v3_sandbox_case_planned',{'block':block,'arm':arm,'case':case,'worker_source':worker,'model_calls':0})
        wrapper="import subprocess,sys,json;p=subprocess.run([job['python'],'-I','-c',\"import json,sys;job=json.load(sys.stdin);exec(job['program'])\"],input=json.dumps(job['payload']).encode(),user=1000,group=1000,extra_groups=[],env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1'});sys.exit(p.returncode)"
        proc=subprocess.run(framed_command(),input=framed_input({'program':wrapper,'python':manifest['product_python'],'payload':payload}),capture_output=True,timeout=120)
        result={'exit_code':proc.returncode,'stdout_base64':base64.b64encode(proc.stdout).decode(),
                'stderr_base64':base64.b64encode(proc.stderr).decode()}
        if proc.returncode==0:result['result']=json.loads(proc.stdout)
        retain('external.v3_sandbox_case_result',result)
        return {'slot':slot,'instance_id':identity,'repeat':block['repeat'],'arm':arm,'task_run':task_run,
                'qualified':result.get('result',{}).get('qualified') is True,'model_calls':0}
    results=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(check,row,arm):(row['block'],arm) for row in cases for arm in row['block']['order']}
        for future in as_completed(futures):
            block,arm=futures[future]
            try:result=future.result()
            except Exception as exc:result={'slot':block['slot'],'arm':arm,'qualified':False,'failure':type(exc).__name__+': '+str(exc),'model_calls':0}
            save('external.v3_sandbox_case_summary',result);results.append(result)
            print(json.dumps({**result,'completed_cases':len(results)}),flush=True)
    save('external.v3_sandbox_completed',{'results':results,'model_calls':0,'credentials_copied':False,
         'all_76_cases_qualified':len(results)==76 and all(r['qualified'] for r in results)})


if __name__=='__main__':main()
