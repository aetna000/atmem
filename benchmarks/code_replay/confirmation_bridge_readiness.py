"""Installed MCP qualification on staged cases; zero inference and no repairs."""
import base64
from hashlib import sha256
import json
from pathlib import Path
import subprocess

from atmem.evidence import EvidenceScope,EvidencePrincipal,EvidenceRole
from benchmarks.code_replay.confirmation_staging import RUN as STAGING
from benchmarks.code_replay.run_evidence import operational_evidence
from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
from benchmarks.code_replay.windows_operator_host import PYTHON
from benchmarks.code_replay.windows_transport import framed_command,framed_input
from benchmarks.code_replay.windows_confirmation_checks import MODULES,isolation_probe,PROBE_PATH

RUN='external-windows-confirmation-bridge-readiness-v1-20261018'
PROGRAM=r'''
import base64,hashlib,json,os,subprocess,time
from pathlib import Path
case=job['case'];operator=Path(case['operator']);root=Path(case['root'])
if (operator!=root/'operator' or operator.is_symlink() or not operator.is_dir()
 or not str(root).startswith('/home/jt/atmem-benchmark-runtime-20261018/confirmation-stage-v1/block-')):
 raise ValueError('exact staged operator root required')
preset_path=operator/'preset.json';server_path=operator/'server.py'
preset_bytes=preset_path.read_bytes();server_bytes=server_path.read_bytes();preset=json.loads(preset_bytes)
if (set(preset)!={'image','worker_source','worker_sha256','source','run_id','evidence_root'}
 or preset['image']!=job['image'] or preset['source']!=job['source']
 or hashlib.sha256(preset['worker_source'].encode()).hexdigest()!=preset['worker_sha256']
 or preset['worker_source']!=job['public_worker_source']
 or preset['evidence_root']!=str(operator/'protected/vault')):
 raise ValueError('staged public preset differs from frozen inputs')
expected="import os\nos.environ['ATMEM_HOME']="+repr(str(operator/'protected'))+'\n'+job['server_template'].replace(job['placeholder'],str(preset_path))
if server_bytes!=expected.encode():raise ValueError('staged public server differs from frozen template')
qualification=operator/'qualification-public';qualification.mkdir(mode=0o700,exist_ok=False)
qual_preset=qualification/'preset.json';qual_server=qualification/'server.py'
qualified_preset={**preset,'run_id':'qualification-'+preset['run_id'],
 'evidence_root':str(qualification/'protected/vault')}
qual_preset.write_text(json.dumps(qualified_preset));qual_preset.chmod(0o600)
qual_source=expected.replace(repr(str(preset_path)),repr(str(qual_preset)))
qual_source=qual_source.replace(repr(str(operator/'protected')),repr(str(qualification/'protected')))
qual_server.write_text(qual_source);qual_server.chmod(0o600)
requests=[{'jsonrpc':'2.0','id':'qualification-init','method':'initialize','params':{}},
 {'jsonrpc':'2.0','id':'qualification-list','method':'tools/list'},
 {'jsonrpc':'2.0','id':'qualification-public','method':'tools/call','params':{
  'name':'run_public_tests','arguments':{'patch':job['probe_patch'],'paths':[job['probe_path']]}}}]
started=time.monotonic()
process=subprocess.run([job['python'],'-I',str(qual_server)],
 input=('\n'.join(json.dumps(r) for r in requests)+'\n').encode(),capture_output=True,timeout=240,
 env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1'})
responses=[json.loads(line) for line in process.stdout.splitlines()]
response=next((r for r in responses if r.get('id')=='qualification-public'),{})
try:answer=json.loads(response['result']['content'][0]['text'])
except (KeyError,ValueError,IndexError):answer={}
public_ok=(process.returncode==0 and len(process.stdout)<=1000000 and answer.get('status')=='executed'
 and answer.get('test_exit_code')==0 and '3 passed' in answer.get('output_tail',''))
result={'public_qualified':public_ok,'public_result':answer,'public_responses':responses,
 'public_stdout_base64':base64.b64encode(process.stdout).decode(),
 'public_stderr_base64':base64.b64encode(process.stderr).decode(),
 'public_elapsed_ms':int((time.monotonic()-started)*1000),
 'qualification_evidence_root':qualified_preset['evidence_root'],
 'original_preset_unchanged':preset_path.read_bytes()==preset_bytes,
 'original_server_unchanged':server_path.read_bytes()==server_bytes,
 'model_calls':0,'not_a_model_public_test_call':True}
if case['database'] is not None:
 from types import SimpleNamespace
 helpers={};exec(job['configuration_source'],helpers)
 config=helpers['configuration'](job['python'],[],database=case['database'],root=case['workspace'],
  scope=SimpleNamespace(**case['scope']),focused=True)
 config['args'][2]="import os;os.environ['ATMEM_HOME']="+repr(case['atmem_home'])+';'+config['args'][2]
 args={'path':job['source_probe'],'start_line':1,'line_count':3}
 requests=[{'jsonrpc':'2.0','id':'qualification-code-init','method':'initialize','params':{}},
  {'jsonrpc':'2.0','id':'qualification-code-list','method':'tools/list'},
  {'jsonrpc':'2.0','id':'qualification-code-source','method':'tools/call','params':{'name':'code_source','arguments':args}}]
 process=subprocess.run([config['command'],*config['args']],
  input=('\n'.join(json.dumps(r) for r in requests)+'\n').encode(),capture_output=True,timeout=90,
  env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1'},user=1000,group=1000,extra_groups=[])
 responses=[json.loads(line) for line in process.stdout.splitlines()]
 response=next((r for r in responses if r.get('id')=='qualification-code-source'),{})
 try:answer=json.loads(response['result']['content'][0]['text'])
 except (KeyError,ValueError,IndexError):answer={}
 expected='\n'.join(base64.b64decode(job['source']['files_base64'][job['source_probe']]).decode().splitlines()[:3])
 result.update(code_qualified=process.returncode==0 and answer.get('status')=='current' and answer.get('content')==expected,
  code_result=answer,code_responses=responses,code_stdout_base64=base64.b64encode(process.stdout).decode(),
  code_stderr_base64=base64.b64encode(process.stderr).decode())
result['qualified']=bool(public_ok and result.get('code_qualified',True)
 and result['original_preset_unchanged'] and result['original_server_unchanged'])
print(json.dumps(result),flush=True)
'''


def probe_patch(module):
    lines=isolation_probe(module).splitlines()
    return ('diff --git a/'+PROBE_PATH+' b/'+PROBE_PATH+'\nnew file mode 100644\n--- /dev/null\n+++ b/'+PROBE_PATH+
            '\n@@ -0,0 +1,'+str(len(lines))+' @@\n'+''.join('+'+line+'\n' for line in lines))


def main():
    scope=EvidenceScope('benchmark','local-operator','click-20261017')
    principal=EvidencePrincipal('local-benchmark-operator',EvidenceRole.ADMINISTRATOR,scope)
    vault=operational_evidence(EVIDENCE_ROOT,vault_id='confirmation-v1',scope=scope,writing_run=RUN)
    if vault.inspect(principal,RUN):raise ValueError('readiness already dispatched; inspect original handle')
    events=vault.inspect(principal,STAGING)
    manifests=[e['envelope']['payload'] for e in events if e['envelope']['event_type']=='external.confirmation_manifest_frozen']
    ends=[e['envelope']['payload'] for e in events if e['envelope']['event_type']=='external.confirmation_staging_completed']
    if len(manifests)!=1 or len(ends)!=1:raise ValueError('terminal staging report required, including blocked slots')
    manifest=manifests[0]
    from benchmarks.code_replay.windows_confirmation_exports import recover_export
    def save(kind,payload):return vault.capture(run_id=RUN,kind=kind,principal=principal,payload=payload)
    # First successful repeat per task; never claim blocked cases ready.
    staged={}
    for e in events:
        if e['envelope']['event_type']=='external.confirmation_block_staged':
            row=e['envelope']['payload'];staged.setdefault(row['block']['instance_id'],row)
    save('external.confirmation_bridge_readiness_planned',{'driver_source':Path(__file__).read_text(),
        'worker_program':PROGRAM,'staging_run':STAGING,'identities':sorted(staged),
        'blocked_slots':ends[0]['blocked_slots'],'model_calls':0,'does_not_waive_blocked_slots':True})
    results=[]
    for identity,row in sorted(staged.items()):
        descriptor=manifest['source_descriptors'][identity]
        source=recover_export(vault.inspect(principal,descriptor['export_run']),descriptor)
        block_events=vault.inspect(principal,row['task_run'])
        plan=next(e['envelope']['payload'] for e in block_events if e['envelope']['event_type']=='external.confirmation_stage_planned')
        roots=(identity.rsplit('-',1)[0].replace('__','/'),)
        from benchmarks.code_replay.eligibility_binding import SOURCE_PROFILES
        source_roots,_=SOURCE_PROFILES[roots[0]]
        probe=next(n for n in sorted(source['files_base64']) if n.endswith('.py') and any(n.startswith(r) for r in source_roots))
        for arm,case in row['cases'].items():
            thin={k:source[k] for k in ('base_commit','files_base64','modes')}
            job={'program':PROGRAM,'case':case,'python':PYTHON,'source':thin,'image':manifest['images'][identity],
                'server_template':plan['server_template'],'public_worker_source':plan['public_worker_source'],
                'placeholder':'/dev/shm/ATMEM_CONFIRMATION_PRESET_PLACEHOLDER',
                'probe_patch':probe_patch(MODULES[roots[0]]),'probe_path':PROBE_PATH,'source_probe':probe,
                'configuration_source':Path('benchmarks/code_replay/progressive.py').read_text()}
            target_run=RUN+'-'+identity+'-'+arm
            target=operational_evidence(EVIDENCE_ROOT,vault_id='confirmation-v1',scope=scope,writing_run=target_run)
            if target.inspect(principal,target_run):raise ValueError('readiness case already attempted')
            def retain(kind,payload):return target.capture(run_id=target_run,kind=kind,principal=principal,payload=payload)
            retain('external.bridge_readiness_case_planned',{'identity':identity,'arm':arm,
                'staged_block':row['block'],'source_descriptor':descriptor,'worker_source':PROGRAM,'model_calls':0})
            code="import subprocess,sys,json;p=subprocess.run([job['python'],'-I','-c',\"import sys,json;job=json.load(sys.stdin);exec(job['program'])\"],input=json.dumps(job['payload']).encode());sys.exit(p.returncode)"
            try:
                proc=subprocess.run(framed_command(),input=framed_input({'program':code,'python':PYTHON,'payload':job}),
                                    capture_output=True,timeout=350)
                result={'instance_id':identity,'arm':arm,'transport_exit':proc.returncode,
                    'stdout_base64':base64.b64encode(proc.stdout).decode(),'stderr_base64':base64.b64encode(proc.stderr).decode()}
                if proc.returncode==0:result['result']=json.loads(proc.stdout)
            except subprocess.TimeoutExpired as exc:
                result={'instance_id':identity,'arm':arm,'transport_exit':None,'failure':'transport_timeout',
                    'stdout_base64':base64.b64encode(exc.stdout or b'').decode(),'stderr_base64':base64.b64encode(exc.stderr or b'').decode()}
            retain('external.bridge_readiness_case_result',result)
            summary={'instance_id':identity,'arm':arm,'task_run':target_run,
                'qualified':result.get('result',{}).get('qualified') is True,'model_calls':0}
            save('external.confirmation_bridge_case_result',summary);results.append(summary)
            print(json.dumps(summary),flush=True)
    save('external.confirmation_bridge_readiness_completed',{'results':results,'model_calls':0,
        'blocked_staging_slots':ends[0]['blocked_slots'],'all_76_cases_ready':False,
        'sandbox_and_scoring_readiness':'not established by this MCP control'})


if __name__=='__main__':main()
