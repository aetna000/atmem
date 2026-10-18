"""Resume only Code MCP startups; recover completed public checks from evidence."""
import ast
import base64
import json
from pathlib import Path
import subprocess

from benchmarks.code_replay.confirmation_bridge_readiness import PROGRAM as ORIGINAL

RUN='external-windows-confirmation-code-readiness-v1-20261018'


def code_only_program():
    nodes=[n for n in ast.parse(ORIGINAL).body if isinstance(n,ast.If)
           and ast.get_source_segment(ORIGINAL,n.test)=="case['database'] is not None"]
    if len(nodes)!=1:
        raise ValueError('exact original Code MCP phase required')
    return ("import base64,json,subprocess\ncase=job['case'];result={}\n"
            +ast.get_source_segment(ORIGINAL,nodes[0])+"\nprint(json.dumps(result),flush=True)\n")


RECOVER_PUBLIC=r'''
import os,json
from pathlib import Path
case=job['case'];operator=Path(case['operator']);qualification=operator/'qualification-public'
if operator!=Path(case['root'])/'operator':raise ValueError('staged operator binding differs')
preset=json.loads((qualification/'preset.json').read_bytes())
original=json.loads((operator/'preset.json').read_bytes())
if preset!={**original,'run_id':'qualification-'+original['run_id'],'evidence_root':str(qualification/'protected/vault')}:
 raise ValueError('qualification preset differs')
os.environ['ATMEM_HOME']=str(qualification/'protected')
from atmem.evidence import EvidenceScope,EvidencePrincipal,EvidenceRole
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
scope=EvidenceScope('benchmark','local-operator',preset['run_id'])
principal=EvidencePrincipal('local-benchmark-operator',EvidenceRole.ADMINISTRATOR,scope)
vault=ReplayEvidence(Path(preset['evidence_root']),vault_id=preset['run_id'],scope=scope)
events=vault.inspect(principal,preset['run_id'])
completed=[e for e in events if e['envelope']['event_type']=='public_tests.completed']
responses=[e for e in events if e['envelope']['event_type']=='public_tests.mcp_response']
if len(completed)!=1 or len(responses)!=1:raise ValueError('exact completed public check required')
message=responses[0]['envelope']['payload']['message']
answer=json.loads(message['result']['content'][0]['text'])
if (message['id']!='qualification-public' or answer['status']!='executed' or answer['test_exit_code']!=0
 or '3 passed' not in answer['output_tail'] or answer['evidence_object_id']!=completed[0]['object_id']):
 raise ValueError('recovered public check does not qualify')
print(json.dumps({'qualified':True,'answer':answer,'run_id':preset['run_id'],
 'evidence_root':preset['evidence_root'],'completed_object_id':completed[0]['object_id'],
 'response_object_id':responses[0]['object_id'],'new_public_executions':0}),flush=True)
'''


def main():
    from atmem.evidence import EvidenceScope,EvidencePrincipal,EvidenceRole
    from benchmarks.code_replay.run_evidence import operational_evidence
    from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
    from benchmarks.code_replay.confirmation_bridge_readiness import RUN as PREVIOUS
    from benchmarks.code_replay.confirmation_staging import RUN as STAGING
    from benchmarks.code_replay.confirmation_runtime_access import RUN as ACCESS
    from benchmarks.code_replay.windows_operator_host import PYTHON
    scope=EvidenceScope('benchmark','local-operator','click-20261017')
    principal=EvidencePrincipal('local-benchmark-operator',EvidenceRole.ADMINISTRATOR,scope)
    vault=operational_evidence(EVIDENCE_ROOT,vault_id='confirmation-v1',scope=scope,writing_run=RUN)
    if vault.inspect(principal,RUN):raise ValueError('code readiness already attempted')
    def payloads(run,kind):
        return [e['envelope']['payload'] for e in vault.inspect(principal,run) if e['envelope']['event_type']==kind]
    access=payloads(ACCESS,'external.runtime_access_repair_completed')
    terminal=payloads(PREVIOUS,'external.confirmation_bridge_readiness_completed')
    if len(access)!=1 or not access[0]['qualified'] or len(terminal)!=1:
        raise ValueError('completed runtime-access qualification and original readiness required')
    staging=payloads(STAGING,'external.confirmation_block_staged')
    manifest=payloads(STAGING,'external.confirmation_manifest_frozen')[0]
    worker=code_only_program()
    def save(kind,payload):return vault.capture(run_id=RUN,kind=kind,principal=principal,payload=payload)
    save('external.code_readiness_planned',{'driver_source':job['driver_source'],
         'worker_source':worker,'recover_source':RECOVER_PUBLIC,'previous':PREVIOUS,
         'runtime_access':ACCESS,'model_calls':0,'new_public_executions':0})
    results=[]
    for previous in terminal[0]['results']:
        if previous['arm']!='tools':continue
        identity=previous['instance_id']
        old=payloads(previous['task_run'],'external.bridge_readiness_case_result')
        if (len(old)!=1 or old[0]['transport_exit']!=1 or
            "PermissionError: [Errno 13] Permission denied: '"+PYTHON+"'" not in
            base64.b64decode(old[0]['stderr_base64'],validate=True).decode()):
            raise ValueError('Code MCP must have failed before process startup')
        block=next(r for r in staging if r['block']['instance_id']==identity)
        case=block['cases']['tools']
        descriptor=manifest['source_descriptors'][identity]
        from benchmarks.code_replay.windows_confirmation_exports import recover_export
        source=recover_export(vault.inspect(principal,descriptor['export_run']),descriptor)
        from benchmarks.code_replay.eligibility_binding import SOURCE_PROFILES
        roots,_=SOURCE_PROFILES[identity.rsplit('-',1)[0].replace('__','/')]
        probe=next(n for n in sorted(source['files_base64']) if n.endswith('.py') and any(n.startswith(r) for r in roots))
        def execute(program,job_payload):
            bootstrap="import sys,json;sys.path[:0]="+repr(job['operator_paths'])+";job=json.load(sys.stdin);exec(job['program'])"
            proc=subprocess.run([PYTHON,'-I','-c',bootstrap],input=json.dumps({**job_payload,'program':program}).encode(),
                capture_output=True,timeout=120,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
            raw={'exit_code':proc.returncode,'stdout_base64':base64.b64encode(proc.stdout).decode(),
                 'stderr_base64':base64.b64encode(proc.stderr).decode()}
            if proc.returncode==0:raw['result']=json.loads(proc.stdout)
            return raw
        public=execute(RECOVER_PUBLIC,{'case':case})
        save('external.public_readiness_recovered',{'identity':identity,'result':public})
        if public.get('result',{}).get('qualified') is not True:
            raise ValueError('completed public qualification could not be recovered; do not rerun')
        code=execute(worker,{'case':case,'python':PYTHON,'source_probe':probe,'source':source,
             'configuration_source':Path('benchmarks/code_replay/progressive.py').read_text()})
        row={'identity':identity,'public_recovered':True,'code':code,'model_calls':0,
             'qualified':code.get('result',{}).get('code_qualified') is True}
        save('external.code_readiness_case_result',row)
        results.append({'identity':identity,'qualified':row['qualified']})
        print(json.dumps(results[-1]),flush=True)
    save('external.code_readiness_completed',{'results':results,'model_calls':0,'new_public_executions':0,
         'qualified':len(results)==14 and all(r['qualified'] for r in results),
         'does_not_waive_staging_failures':True})


if __name__=='__main__':
    import os
    main()
