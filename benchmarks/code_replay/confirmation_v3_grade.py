"""Use the exact previously qualified private commands after all 76 models stop."""
import base64
from concurrent.futures import ThreadPoolExecutor,as_completed
from hashlib import sha256
import json
from uuid import uuid4

RUN='external-windows-confirmation-v3-grading-v1-20261018'
MODELS='external-windows-confirmation-v3-models-v1-20261018'
LOCK='external-windows-confirmation-v3-execution-lock-v1-20261018'


def complete_cases(manifest,rows,terminal):
    expected={(b['slot'],a):(b['instance_id'],b['repeat']) for b in manifest['staging_manifest']['blocks'] for a in b['order']}
    if (len(expected)!=76 or len(rows)!=76 or len(terminal)!=1 or terminal[0]['attempts_completed']!=76
            or len({(r['slot'],r['arm']) for r in rows})!=76):
        raise ValueError('all seventy-six model/capture cells required before private grading')
    if any(expected.get((r['slot'],r['arm']))!=(r['instance_id'],r['repeat']) for r in rows):
        raise ValueError('captured cohort differs from frozen identities')
    return expected


def recover_candidate(events,summary):
    from benchmarks.code_replay.windows_metrics import recover_stream
    by_id={e['object_id']:e for e in events}
    if not 0<summary['source_bytes']<=128_000_000 or len(summary['receipts'])>128:
        raise ValueError('bounded complete candidate transport required')
    for receipt in summary['receipts']:
        e=by_id[receipt['object_id']]['envelope']
        if e['event_type']!='external.v3_candidate_chunk' or e['run_id']!=summary['task_run'] or receipt['run_id']!=summary['task_run']:
            raise ValueError('candidate receipt role differs')
    return json.loads(recover_stream(by_id,{'bytes':summary['source_bytes'],
        'sha256':summary['source_sha256'],'receipts':summary['receipts']}))


def retain_dispatch(retain,payload):
    """Preserve the full request without raising the protected per-event limit."""
    from atmem.core.canonical import canonical_json
    raw=canonical_json(payload).encode()
    if len(raw)<=16_000_000:
        return retain('external.v3_grade_dispatch',payload)
    if len(raw)>64_000_000:raise ValueError('bounded full grader dispatch required')
    receipts=[]
    for offset in range(0,len(raw),3_000_000):
        receipts.append(retain('external.v3_grade_dispatch_chunk',{'offset':offset,
            'total_bytes':len(raw),'sha256':sha256(raw).hexdigest(),
            'content_base64':base64.b64encode(raw[offset:offset+3_000_000]).decode()}))
    return retain('external.v3_grade_dispatch',{**{k:v for k,v in payload.items() if k!='request'},
        'full_dispatch_transport':{'bytes':len(raw),'sha256':sha256(raw).hexdigest(),'receipts':receipts},
        'full_request_retained':True})


def main():
    from atmem.evidence import EvidenceScope,EvidencePrincipal,EvidenceRole
    from atmem.core.canonical import canonical_json
    from benchmarks.code_replay.run_evidence import operational_evidence
    from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
    from benchmarks.code_replay.windows_confirmation_exports import recover_export
    from benchmarks.code_replay.windows_transport import framed_command,framed_input
    from benchmarks.code_replay.retained_control import retain_control
    from benchmarks.code_replay.solver_proposal import proposal_request
    scope=EvidenceScope('benchmark','local-operator','click-20261017')
    principal=EvidencePrincipal('local-benchmark-operator',EvidenceRole.ADMINISTRATOR,scope)
    vault=operational_evidence(EVIDENCE_ROOT,vault_id='confirmation-v1',scope=scope,writing_run=RUN)
    if vault.inspect(principal,RUN):raise ValueError('grading already dispatched; never automatically repeat')
    def es(run):return vault.inspect(principal,run)
    locks=[e['envelope']['payload'] for e in es(LOCK) if e['envelope']['event_type']=='external.v3_execution_manifest_frozen']
    if len(locks)!=1:raise ValueError('exact pre-inference lock required')
    lock=locks[0];events=es(MODELS)
    completed=[e['envelope']['payload'] for e in events if e['envelope']['event_type']=='external.v3_case_completed']
    terminal=[e['envelope']['payload'] for e in events if e['envelope']['event_type']=='external.v3_models_completed']
    complete_cases(lock,completed,terminal)
    cases={r['block']['slot']:r for r in lock['staged_blocks']};sources={};plans={}
    for identity,d in lock['staging_manifest']['source_descriptors'].items():
        sources[identity]=recover_export(es(d['export_run']),d)
        reference=lock['grade_plans'][identity];records=es(reference['task_run'])
        record=next(e for e in records if e['object_id']==reference['receipt']['object_id'])
        if (record['envelope']['event_type']!='external.v3_private_grader_frozen'
                or sha256(canonical_json(record['envelope']['payload']).encode()).hexdigest()!=reference['receipt']['payload_sha256']):
            raise ValueError('frozen grader receipt identity differs')
        plans[identity]=record['envelope']['payload']
    def save(kind,payload):return vault.capture(run_id=RUN,kind=kind,principal=principal,payload=payload)
    save('external.v3_grading_planned',{'driver_source':job['driver_source'],'lock_run':LOCK,
        'models_run':MODELS,'cases':76,'max_workers':2,'model_feedback':False})
    def grade(summary):
        identity=summary['instance_id'];slot=summary['slot'];arm=summary['arm'];source=sources[identity]
        candidate=recover_candidate(es(summary['task_run']),summary)
        models=[e for e in es(summary['task_run']) if e['envelope']['event_type']=='external.v3_model_result']
        if len(models)!=1:raise ValueError('exact full model receipt required')
        expected=cases[slot]['cases'][arm]
        if (candidate['workspace']!=expected['workspace'] or candidate['case_root']!=expected['root']
                or candidate['temporary_cli_auth_absent'] is not True or candidate['writer_processes_observed'] is not False):
            raise ValueError('candidate source origin or terminal state differs')
        plan=plans[identity];command=list(plan['command_template'])
        if sha256(command[-1].encode()).hexdigest()!=plan['program_sha256']:
            raise ValueError('qualified private grader changed')
        name='atmem-reference-control-'+uuid4().hex
        command[command.index('--name')+1]=name
        payload=proposal_request(plan['material'],source,candidate['files_base64'])
        request={'program':plan['controller_program'],'name':name,'command':command,'payload':payload}
        target_run=RUN+'-block-'+str(slot)+'-'+arm
        target=operational_evidence(EVIDENCE_ROOT,vault_id='confirmation-v1',scope=scope,writing_run=target_run)
        if target.inspect(principal,target_run):raise ValueError('grade already attempted')
        def retain(kind,payload):return target.capture(run_id=target_run,kind=kind,principal=principal,payload=payload)
        retain_dispatch(retain,{'slot':slot,'instance_id':identity,'repeat':summary['repeat'],'arm':arm,
            'request':request,'frozen_grader_receipt':lock['grade_plans'][identity],'candidate_case_run':summary['task_run']})
        proc=__import__('subprocess').run(framed_command(),input=framed_input(request),capture_output=True,timeout=205)
        row=retain_control(retain,identity,'solver_candidate',proc)
        retain('external.v3_private_grade',row)
        return {'slot':slot,'instance_id':identity,'repeat':summary['repeat'],'arm':arm,'task_run':target_run,
            'transport_exit_code':proc.returncode,'controller':row.get('controller'),
            'source_policy_compliant':candidate['source_policy_compliant'],
            'expected_f2p':plan['expected_f2p'],'expected_p2p':plan['expected_p2p']}
    results=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures={pool.submit(grade,row):row for row in completed}
        for future in as_completed(futures):
            row=futures[future]
            try:result=future.result()
            except Exception as exc:result={k:row[k] for k in ('slot','instance_id','repeat','arm')};result.update(failure=type(exc).__name__+': '+str(exc))
            save('external.v3_grade_summary',result);results.append(result)
            print(json.dumps({'slot':row['slot'],'arm':row['arm'],'graded':len(results),'failure':result.get('failure')}),flush=True)
    save('external.v3_grading_completed',{'cases':len(results),'model_feedback':False,'comparison_and_archive':'pending'})


if __name__=='__main__':main()
