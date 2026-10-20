"""Actual stdio MCP controls for every fresh v3 case, without model inference."""
import base64
from concurrent.futures import ThreadPoolExecutor,as_completed
import json
import subprocess

from benchmarks.code_replay.confirmation_bridge_readiness import PROGRAM as ORIGINAL

RUN='external-windows-confirmation-v3-mcp-readiness-v1-20261018'
STAGING='external-windows-confirmation-v3-staging-v1-20261018'


def worker_program():
    before='/home/jt/atmem-benchmark-runtime-20261018/confirmation-stage-v1/block-'
    after='/home/jt/atmem-benchmark-runtime-20261018/confirmation-stage-v3/block-'
    if ORIGINAL.count(before)!=1:raise ValueError('exact original readiness root check required')
    return ORIGINAL.replace(before,after)


def main():
    from atmem.evidence import EvidenceScope,EvidencePrincipal,EvidenceRole
    from benchmarks.code_replay.run_evidence import operational_evidence
    from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
    from benchmarks.code_replay.windows_confirmation_exports import recover_export
    from benchmarks.code_replay.windows_transport import framed_command,framed_input
    from benchmarks.code_replay.eligibility_binding import SOURCE_PROFILES
    from benchmarks.code_replay.confirmation_bridge_readiness import probe_patch
    from benchmarks.code_replay.windows_confirmation_checks import MODULES,PROBE_PATH
    scope=EvidenceScope('benchmark','local-operator','click-20261017')
    principal=EvidencePrincipal('local-benchmark-operator',EvidenceRole.ADMINISTRATOR,scope)
    vault=operational_evidence(EVIDENCE_ROOT,vault_id='confirmation-v1',scope=scope,writing_run=RUN)
    if vault.inspect(principal,RUN):raise ValueError('v3 readiness already attempted; inspect original handle')
    events=vault.inspect(principal,STAGING)
    def payloads(kind):return [e['envelope']['payload'] for e in events if e['envelope']['event_type']==kind]
    locks=payloads('external.confirmation_v3_manifest_frozen');ends=payloads('external.confirmation_v3_staging_completed')
    blocks=payloads('external.confirmation_v3_block_result')
    if (len(locks)!=1 or len(ends)!=1 or ends[0]['all_76_cases_staged'] is not True
            or len(blocks)!=38 or len({b['block']['slot'] for b in blocks})!=38
            or any(not b['qualified'] for b in blocks)):
        raise ValueError('all 76 independently staged v3 cases required')
    manifest=locks[0];sources={};plans={}
    for row in blocks:
        identity=row['block']['instance_id']
        if identity not in sources:
            d=manifest['source_descriptors'][identity]
            sources[identity]=recover_export(vault.inspect(principal,d['export_run']),d)
        es=vault.inspect(principal,row['task_run'])
        ps=[e['envelope']['payload'] for e in es if e['envelope']['event_type']=='external.confirmation_v3_stage_planned']
        if len(ps)!=1:raise ValueError('exact stage source plan required')
        plans[row['block']['slot']]=ps[0]
    program=worker_program()
    def save(kind,payload):return vault.capture(run_id=RUN,kind=kind,principal=principal,payload=payload)
    save('external.v3_mcp_readiness_planned',{'driver_source':job['driver_source'],'worker_source':program,
        'staging_run':STAGING,'max_workers':4,'cases':76,'model_calls':0,
        'probe_scope':'fixed public source/import/private-artifact/network assertions plus ordinary-user Code MCP source response'})
    def check(row,arm):
        block=row['block'];slot=block['slot'];identity=block['instance_id'];case=row['cases'][arm]
        source=sources[identity];plan=plans[slot];repo=identity.rsplit('-',1)[0].replace('__','/')
        roots,_=SOURCE_PROFILES[repo]
        probe=next(n for n in sorted(source['files_base64']) if n.endswith('.py') and any(n.startswith(r) for r in roots))
        payload={'program':program,'case':case,'python':manifest['product_python'],
            'source':{k:source[k] for k in ('base_commit','files_base64','modes')},'image':manifest['images'][identity],
            'server_template':plan['server_template'],'public_worker_source':plan['public_worker_source'],
            'placeholder':'/dev/shm/ATMEM_CONFIRMATION_PRESET_PLACEHOLDER',
            'probe_patch':probe_patch(MODULES[repo]),'probe_path':PROBE_PATH,'source_probe':probe,
            'configuration_source':job['configuration_source']}
        task_run=RUN+'-block-'+str(slot)+'-'+arm
        target=operational_evidence(EVIDENCE_ROOT,vault_id='confirmation-v1',scope=scope,writing_run=task_run)
        if target.inspect(principal,task_run):raise ValueError('readiness case already attempted')
        def retain(kind,payload):return target.capture(run_id=task_run,kind=kind,principal=principal,payload=payload)
        retain('external.v3_mcp_case_planned',{'block':block,'arm':arm,'worker_source':program,
            'source_descriptor':manifest['source_descriptors'][identity],'case':case,'model_calls':0})
        wrapper="import subprocess,sys,json;p=subprocess.run([job['python'],'-I','-c',\"import json,sys;job=json.load(sys.stdin);exec(job['program'])\"],input=json.dumps(job['payload']).encode());sys.exit(p.returncode)"
        try:
            proc=subprocess.run(framed_command(),input=framed_input({'program':wrapper,'python':manifest['product_python'],'payload':payload}),capture_output=True,timeout=360)
            result={'exit_code':proc.returncode,'stdout_base64':base64.b64encode(proc.stdout).decode(),
                    'stderr_base64':base64.b64encode(proc.stderr).decode()}
            if proc.returncode==0:result['result']=json.loads(proc.stdout)
        except subprocess.TimeoutExpired as exc:
            result={'exit_code':None,'failure':'observation_timeout_not_proof_of_worker_termination',
                    'stdout_base64':base64.b64encode(exc.stdout or b'').decode(),'stderr_base64':base64.b64encode(exc.stderr or b'').decode()}
        retain('external.v3_mcp_case_result',result)
        return {'slot':slot,'instance_id':identity,'repeat':block['repeat'],'arm':arm,'task_run':task_run,
                'qualified':result.get('result',{}).get('qualified') is True,'model_calls':0}
    results=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(check,row,arm):(row['block'],arm) for row in blocks for arm in row['block']['order']}
        for future in as_completed(futures):
            block,arm=futures[future]
            try:result=future.result()
            except Exception as exc:result={'slot':block['slot'],'arm':arm,'qualified':False,
                                          'failure':type(exc).__name__+': '+str(exc),'model_calls':0}
            save('external.v3_mcp_case_summary',result);results.append(result)
            print(json.dumps({**result,'completed_cases':len(results)}),flush=True)
    save('external.v3_mcp_readiness_completed',{'results':results,'model_calls':0,
        'all_76_cases_qualified':len(results)==76 and all(r['qualified'] for r in results),
        'sandbox_and_model_qualification':'not established by direct stdio MCP checks'})


if __name__=='__main__':main()
