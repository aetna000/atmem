"""Fresh full-cohort staging for the disclosed compatibility preview."""
import base64
from concurrent.futures import ThreadPoolExecutor,as_completed
from hashlib import sha256
import json
from pathlib import Path
import subprocess

RUN='external-windows-confirmation-v3-staging-v1-20261018'
CASE_ROOT='/home/jt/atmem-benchmark-runtime-20261018/confirmation-stage-v3'


def timed_stage(original):
    markers=('import base64,json,os,subprocess,zlib',
             ' case=root/arm;case.mkdir(mode=0o711)',"\nif len({case['initial_commit']")
    if any(original.count(m)!=1 for m in markers):raise ValueError('exact retained stage implementation required')
    source=original.replace(markers[0],markers[0]+',time')
    source=source.replace(markers[1],' case_started=time.monotonic()\n'+markers[1])
    return source.replace(markers[2],"\n cases[arm]['stage_elapsed_ms']=int((time.monotonic()-case_started)*1000)"+markers[2])


def main():
    from atmem.evidence import EvidenceScope,EvidencePrincipal,EvidenceRole
    from atmem.core.canonical import canonical_json
    from benchmarks.code_replay.run_evidence import operational_evidence
    from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
    from benchmarks.code_replay.confirmation_staging import RUN as OLD
    from benchmarks.code_replay.windows_confirmation_exports import recover_export
    from benchmarks.code_replay.windows_transport import framed_command,framed_input
    from benchmarks.code_replay.windows_cohort import model_program
    from benchmarks.code_replay.windows_execute import runner_helpers
    scope=EvidenceScope('benchmark','local-operator','click-20261017')
    principal=EvidencePrincipal('local-benchmark-operator',EvidenceRole.ADMINISTRATOR,scope)
    vault=operational_evidence(EVIDENCE_ROOT,vault_id='confirmation-v1',scope=scope,writing_run=RUN)
    if vault.inspect(principal,RUN):raise ValueError('v3 staging already attempted; inspect original handle')
    def only(run,kind):
        rows=[e['envelope']['payload'] for e in vault.inspect(principal,run) if e['envelope']['event_type']==kind]
        if len(rows)!=1:raise ValueError('exact retained prerequisite required: '+kind)
        return rows[0]
    build=only('external-windows-product-build-source-storage-v1-20261018','external.compatibility_build_completed')
    ready=only('external-windows-source-storage-qualification-v1-20261018','external.compatibility_qualification_completed')
    old=only(OLD,'external.confirmation_manifest_frozen')
    terminal=only(OLD,'external.confirmation_staging_completed')
    if (build['qualified'] is not True or ready['qualified'] is not True or ready['model_calls']!=0
            or len(old['tasks'])!=19 or len(old['blocks'])!=38 or terminal['blocks']!=28
            or len(terminal['blocked_slots'])!=10):raise ValueError('complete retained compatibility history required')
    source=timed_stage(old['stage_program'])
    runner,helpers=runner_helpers()
    cli=Path('/home/jt/atmem-benchmark-runtime-20261018/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex')
    cli_hash=sha256(cli.read_bytes()).hexdigest()
    if cli_hash!='628e35487d888a28f0427fc37501da529dd3d81fcbad7a2c3421c1e8670d92e1':raise ValueError('pinned CLI differs')
    manifest={**old,'format':'atmem-confirmation-amended19-v3-staging-v1','stage_program':source,
        'product_python':build['python'],'wheel_sha256':build['wheel_sha256'],'prior_manifest_run':OLD,
        'protocol':job['protocol'],'driver_source':job['driver_source'],'build':build,
        'model_program':model_program(),'runner':runner,'mcp_helpers':helpers,'cli_sha256':cli_hash,
        'max_stage_workers':2,'model_calls':0,'inference_authorized_by_staging':False,
        'readiness':'full cohort restaging only; final execution lock and actual MCP/sandbox gates still required'}
    def save(kind,payload):return vault.capture(run_id=RUN,kind=kind,principal=principal,payload=payload)
    save('external.confirmation_v3_manifest_frozen',manifest)
    root=Path(CASE_ROOT);root.mkdir(mode=0o711,exist_ok=False)
    plans={}
    sources={}
    for block in old['blocks']:
        slot=block['slot'];identity=block['instance_id']
        plans[slot]=only(OLD+'-block-'+str(slot),'external.confirmation_stage_planned')
        if identity not in sources:
            descriptor=old['source_descriptors'][identity]
            sources[identity]=recover_export(vault.inspect(principal,descriptor['export_run']),descriptor)
    def stage(block):
        import shutil
        if min(shutil.disk_usage('/tmp').free,shutil.disk_usage('/mnt/c').free)<8*1024**3:
            raise ValueError('physical disk guard')
        slot=block['slot'];identity=block['instance_id'];source=sources[identity];plan=plans[slot]
        task_run=RUN+'-block-'+str(slot)
        target=operational_evidence(EVIDENCE_ROOT,vault_id='confirmation-v1',scope=scope,writing_run=task_run)
        if target.inspect(principal,task_run):raise ValueError('v3 block already attempted')
        def retain(kind,payload):return target.capture(run_id=task_run,kind=kind,principal=principal,payload=payload)
        thin={k:source[k] for k in ('base_commit','files_base64','modes')}
        worker=plan['public_worker_source']
        payload={'program':manifest['stage_program'],'root':str(root/('block-'+str(slot))),
            'source':thin,'issue':old['issues'][identity],'order':block['order'],'block_id':'confirmation19-v3-'+str(slot),
            'extractor':old['extractor'],'lane_source':old['lane_source'],
            'public_preset':{'image':old['images'][identity],'worker_source':worker,
                'worker_sha256':sha256(worker.encode()).hexdigest(),'source':thin,
                'run_id':'operator-replaced','evidence_root':'operator-replaced'},
            'server_template':plan['server_template'],'preset_placeholder':'/dev/shm/ATMEM_CONFIRMATION_PRESET_PLACEHOLDER'}
        retain('external.confirmation_v3_stage_planned',{'block':block,'source_descriptor':old['source_descriptors'][identity],
            'root':payload['root'],'job_sha256':sha256(canonical_json(payload).encode()).hexdigest(),
            'server_template':plan['server_template'],'public_worker_source':worker,'model_calls':0})
        wrapper="import subprocess,sys,json;p=subprocess.run([job['python'],'-I','-c',\"import json,sys;job=json.load(sys.stdin);exec(job['program'])\"],input=json.dumps(job['payload']).encode());sys.exit(p.returncode)"
        proc=subprocess.run(framed_command(),input=framed_input({'program':wrapper,'python':build['python'],'payload':payload}),capture_output=True,timeout=360)
        streams={}
        for name,raw in [('stdout',proc.stdout),('stderr',proc.stderr)]:
            receipts=[]
            for offset in range(0,len(raw),3_000_000):
                receipts.append(retain('external.confirmation_v3_stage_chunk',{'stream':name,'offset':offset,
                    'bytes_base64':base64.b64encode(raw[offset:offset+3_000_000]).decode()}))
            streams[name]={'bytes':len(raw),'sha256':sha256(raw).hexdigest(),'receipts':receipts}
        retain('external.confirmation_v3_stage_transport',{'exit_code':proc.returncode,'streams':streams})
        result={'block':block,'task_run':task_run,'qualified':False,'exit_code':proc.returncode,'model_calls':0}
        if proc.returncode==0:
            value=json.loads(proc.stdout)
            cases={a:{k:v for k,v in c.items() if k!='generation_zlib_base64'} for a,c in value['cases'].items()}
            if (set(cases)!={'native','tools'} or not cases['tools']['database'] or not cases['tools']['atmem_home']
                    or cases['native']['database'] is not None or cases['native']['atmem_home'] is not None
                    or cases['native']['initial_commit']!=cases['tools']['initial_commit']
                    or len(cases['tools']['prepared']['package']['content'].encode())>4096):
                raise ValueError('fresh paired descriptors or bounded context differ')
            result.update(qualified=True,cases=cases,transport=streams)
        return result
    results=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures={pool.submit(stage,b):b for b in old['blocks']}
        for future in as_completed(futures):
            block=futures[future]
            try:result=future.result()
            except Exception as exc:result={'block':block,'qualified':False,'failure':type(exc).__name__+': '+str(exc),'model_calls':0}
            save('external.confirmation_v3_block_result',result);results.append(result)
            print(json.dumps({'slot':block['slot'],'identity':block['instance_id'],'qualified':result['qualified'],
                              'completed_blocks':len(results),'model_calls':0}),flush=True)
    save('external.confirmation_v3_staging_completed',{'results':results,'blocks':len(results),
        'qualified_blocks':sum(r['qualified'] for r in results),'model_calls':0,
        'all_76_cases_staged':len(results)==38 and all(r['qualified'] for r in results),
        'mcp_sandbox_and_scored_readiness':'pending'})


if __name__=='__main__':main()
