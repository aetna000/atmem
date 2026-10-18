"""Archive-only recovery and binding checks for original full grader requests."""
from hashlib import sha256
import json
import re


def recover_dispatch(events):
    from benchmarks.code_replay.windows_metrics import recover_stream
    indexes=[e for e in events if e['envelope']['event_type']=='external.v3_grade_dispatch']
    if len(indexes)!=1:raise ValueError('one original grade dispatch required')
    event=indexes[0];index=event['envelope']['payload']
    if 'full_dispatch_transport' not in index:
        if 'request' not in index:raise ValueError('complete original request missing')
        return index,False
    transport=index['full_dispatch_transport']
    if (index.get('full_request_retained') is not True or not 0<transport['bytes']<=64_000_000
            or not 1<=len(transport['receipts'])<=32):
        raise ValueError('bounded complete dispatch framing required')
    by_id={e['object_id']:e for e in events}
    for receipt in transport['receipts']:
        part=by_id[receipt['object_id']]['envelope']
        if (part['event_type']!='external.v3_grade_dispatch_chunk'
                or part['run_id']!=event['envelope']['run_id'] or receipt['run_id']!=part['run_id']):
            raise ValueError('grade dispatch chunk role or run differs')
    full=json.loads(recover_stream(by_id,transport))
    if any(full.get(k)!=v for k,v in index.items() if k not in {'full_dispatch_transport','full_request_retained'}):
        raise ValueError('recovered dispatch differs from index metadata')
    if 'request' not in full:raise ValueError('recovered full request missing')
    return full,True


def bound_request(dispatch,case,reference,plan,source,candidate):
    from benchmarks.code_replay.solver_proposal import proposal_request
    if (any(dispatch[k]!=case[k] for k in ('slot','instance_id','repeat','arm'))
            or dispatch['candidate_case_run']!=case['task_run']
            or dispatch['frozen_grader_receipt']!=reference):
        raise ValueError('request case or frozen grader binding differs')
    request=dispatch['request'];name=request['name']
    if re.fullmatch(r'atmem-reference-control-[0-9a-f]{32}',name) is None:
        raise ValueError('exact generated container identity required')
    command=list(plan['command_template'])
    if sha256(command[-1].encode()).hexdigest()!=reference['program_sha256']:
        raise ValueError('frozen private grading program differs')
    command[command.index('--name')+1]=name
    expected={'program':plan['controller_program'],'name':name,'command':command,
              'payload':proposal_request(plan['material'],source,candidate['files_base64'])}
    if request!=expected:raise ValueError('actual full request differs from frozen grader/source/candidate')
    return True


def audit_collection(output,key_root):
    """Read only authenticated archive files and internal keys, not original vaults."""
    from atmem.core.canonical import canonical_json
    from benchmarks.code_replay.windows_archive import recover_snapshot
    from benchmarks.code_replay.confirmation_v3_archive import COLLECTION,LOCK,MODELS,GRADING,of
    from benchmarks.code_replay.confirmation_v3_grade import recover_candidate,complete_cases
    from benchmarks.code_replay.windows_confirmation_exports import recover_export
    raw,_=recover_snapshot(run_id=COLLECTION,output=output/'collection',key_root=key_root/'collection')
    manifest=json.loads(raw);members={r['run_id']:r for r in manifest['runs']}
    def read(run):
        row=members[run];directory=sha256(run.encode()).hexdigest()
        if row['directory']!=directory:raise ValueError('exact archive member path required')
        raw,observed=recover_snapshot(run_id=run,output=output/directory,key_root=key_root/directory)
        if observed['raw_sha256']!=row['raw_sha256'] or len(raw)!=row['raw_bytes']:
            raise ValueError('authenticated collection member differs')
        return json.loads(raw)
    lock,=of(read(LOCK),'external.v3_execution_manifest_frozen')
    models=read(MODELS);cases=of(models,'external.v3_case_completed')
    complete_cases(lock,cases,of(models,'external.v3_models_completed'))
    grades=of(read(GRADING),'external.v3_grade_summary')
    by_cell={(r['slot'],r['arm']):r for r in grades}
    if len(grades)!=76 or len(by_cell)!=76:raise ValueError('all original grade attempts required')
    chunked=0;total_bytes=0
    for case in cases:
        identity=case['instance_id'];reference=lock['grade_plans'][identity]
        records=read(reference['task_run'])
        record=next(e for e in records if e['object_id']==reference['receipt']['object_id'])
        plan=record['envelope']['payload']
        if sha256(canonical_json(plan).encode()).hexdigest()!=reference['receipt']['payload_sha256']:
            raise ValueError('private grader receipt differs')
        descriptor=lock['staging_manifest']['source_descriptors'][identity]
        source=recover_export(read(descriptor['export_run']),descriptor)
        candidate=recover_candidate(read(case['task_run']),case)
        grade=by_cell[(case['slot'],case['arm'])]
        dispatch,is_chunked=recover_dispatch(read(grade['task_run']))
        bound_request(dispatch,case,reference,plan,source,candidate)
        chunked+=is_chunked;total_bytes+=len(canonical_json(dispatch).encode())
    return {'verified_original_requests':76,'chunked_requests':chunked,'canonical_dispatch_bytes':total_bytes,
            'source_vault_opened':False,'model_or_grade_retries':0}


def main():
    import os
    from pathlib import Path
    import time
    if Path(__file__).read_text()!=job['driver_source']:
        raise ValueError('request auditor implementation changed since scheduling')
    os.environ['ATMEM_BENCHMARK_PER_RUN_VAULTS']='1'
    from atmem.evidence import EvidenceScope,EvidencePrincipal,EvidenceRole
    from benchmarks.code_replay.run_evidence import operational_evidence
    from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
    from benchmarks.code_replay.confirmation_v3_transfer import RUN as TRANSFER,OUTPUT,KEYS
    run='external-windows-confirmation-v3-archive-request-audit-v1-20261018'
    scope=EvidenceScope('benchmark','local-operator','click-20261017')
    principal=EvidencePrincipal('local-benchmark-operator',EvidenceRole.ADMINISTRATOR,scope)
    vault=operational_evidence(EVIDENCE_ROOT,vault_id='confirmation-v1',scope=scope,writing_run=run)
    if vault.inspect(principal,run):raise ValueError('archive request audit already attempted')
    def save(kind,payload):return vault.capture(run_id=run,kind=kind,principal=principal,payload=payload)
    save('external.v3_archive_request_audit_planned',{'driver_source':job['driver_source'],
        'archive':str(OUTPUT),'internal_key_root':str(KEYS),'source_vault_access':False,
        'model_or_grade_retries':0})
    while True:
        events=vault.inspect(principal,TRANSFER)
        done=[e for e in events if e['envelope']['event_type']=='external.v3_MEM_recovery_completed']
        if len(done)>1:raise ValueError('ambiguous independent recovery terminal')
        if done:break
        failures=[e for e in events if e['envelope']['event_type'] in {
            'external.v3_MEM_remote_probe_failed','external.v3_MEM_copy_result','external.v3_MEM_recovery_result'}
            and e['envelope']['payload'].get('exit_code')!=0]
        if failures:raise RuntimeError('transfer/recovery failure retained; no automatic retry')
        time.sleep(30)
    result=audit_collection(OUTPUT,KEYS)
    save('external.v3_archive_request_audit_completed',{'proof':result,'final_goal_audit':'still required'})
    print(json.dumps({'independent_original_request_audit':result}),flush=True)
