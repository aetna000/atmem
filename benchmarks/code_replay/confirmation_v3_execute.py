"""Execute once per frozen confirmation cell; preserve full streams and stopped source."""
import base64
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import time

RUN='external-windows-confirmation-v3-models-v1-20261018'
LOCK='external-windows-confirmation-v3-execution-lock-v1-20261018'


def main():
    from atmem.evidence import EvidenceScope,EvidencePrincipal,EvidenceRole
    from benchmarks.code_replay.run_evidence import operational_evidence
    from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
    from benchmarks.code_replay.confirmation_v3_process_scope import create_group,quiesce,CHILD_BOOTSTRAP
    from benchmarks.code_replay.confirmation_v3_capture import captured_case
    from benchmarks.code_replay.windows_confirmation_exports import recover_export
    from benchmarks.code_replay.windows_execute import model_metadata
    from benchmarks.code_replay.source_policy import SourcePolicy,collect_source_patch
    scope=EvidenceScope('benchmark','local-operator','click-20261017')
    principal=EvidencePrincipal('local-benchmark-operator',EvidenceRole.ADMINISTRATOR,scope)
    vault=operational_evidence(EVIDENCE_ROOT,vault_id='confirmation-v1',scope=scope,writing_run=RUN)
    if vault.inspect(principal,RUN):raise ValueError('model cohort already dispatched; never replay a model outcome')
    es=vault.inspect(principal,LOCK)
    locks=[e['envelope']['payload'] for e in es if e['envelope']['event_type']=='external.v3_execution_manifest_frozen']
    ends=[e['envelope']['payload'] for e in es if e['envelope']['event_type']=='external.v3_execution_preparation_completed']
    if (len(locks)!=1 or len(ends)!=1 or not ends[0]['all_76_initial_sources_verified']
            or not ends[0]['all_19_private_graders_bound']):raise ValueError('complete pre-inference lock required')
    lock=locks[0];manifest=lock['staging_manifest']
    if (job['driver_source']!=lock['model_driver_source'] or lock['model_workers']!=1
            or lock['model_attempts']!=76 or lock['process_bootstrap']!=CHILD_BOOTSTRAP):
        raise ValueError('execution implementation or prospective budgets differ from lock')
    sources={}
    for identity,d in manifest['source_descriptors'].items():
        sources[identity]=recover_export(vault.inspect(principal,d['export_run']),d)
    staged={r['block']['slot']:r for r in lock['staged_blocks']}
    def save(kind,payload):return vault.capture(run_id=RUN,kind=kind,principal=principal,payload=payload)
    save('external.v3_models_execution_planned',{'driver_source':job['driver_source'],'lock_run':LOCK,
        'lock_sha256':ends[0]['manifest_sha256'],'attempts':76,'model_workers':1,
        'model':'gpt-6-luna','effort':'low','subscription_cli':True,'private_grading':'after all models',
        'no_model_retries':True})
    finished=[]
    for block in manifest['blocks']:
        slot=block['slot'];identity=block['instance_id'];source=sources[identity]
        for arm in block['order']:
            case=staged[slot]['cases'][arm]
            target_run=RUN+'-block-'+str(slot)+'-'+arm
            target=operational_evidence(EVIDENCE_ROOT,vault_id='confirmation-v1',scope=scope,writing_run=target_run)
            if target.inspect(principal,target_run):raise ValueError('case already attempted; no automatic retry')
            def retain(kind,payload):return target.capture(run_id=target_run,kind=kind,principal=principal,payload=payload)
            cell={'slot':slot,'instance_id':identity,'repeat':block['repeat'],'arm':arm,'task_run':target_run}
            initial=lock['initial_sources'][str(slot)][arm]
            before=captured_case(case,writers_stopped=True)
            if (before['source_sha256']!=initial['source_sha256'] or before['git_metadata']!=initial['git_metadata']
                    or not before['temporary_cli_auth_absent']):raise ValueError('fresh source/ref/auth state changed before inference')
            group=create_group('block-'+str(slot)+'-'+arm)
            payload={'program':manifest['model_program'],'case':case,'arm':arm,
                'runner':manifest['runner'],'mcp_helpers':manifest['mcp_helpers'],
                'product_python':manifest['product_python'],'prompt':lock['prompts'][identity],
                'probe_source':lock['probe_sources'][identity],'cli_sha256':manifest['cli_sha256'],
                'process_scope':str(group)}
            command=[manifest['product_python'],'-I','-c',CHILD_BOOTSTRAP]
            retain('external.v3_model_dispatch',{**cell,'job':payload,'command':command,'lock_run':LOCK})
            print(json.dumps({**cell,'phase':'model_running'}),flush=True)
            started=time.monotonic()
            try:
                process=subprocess.run(command,input=json.dumps(payload).encode(),capture_output=True,timeout=690,
                    env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1'})
                output,error,exit_code=process.stdout,process.stderr,process.returncode
            except subprocess.TimeoutExpired as exc:
                output,error,exit_code=exc.stdout or b'',exc.stderr or b'',None
            termination=quiesce(group)
            auth=Path(case['cli_home'])/'auth.json'
            # This exact home was freshly allocated and proved credential-free
            # before the authorized actor copied its temporary subscription auth.
            # Never touch the owner's Windows credential source.
            auth_cleanup=False
            if auth.exists() or auth.is_symlink():auth.unlink();auth_cleanup=True
            supervisor_ms=int((time.monotonic()-started)*1000)
            streams={}
            for name,raw in [('stdout',output),('stderr',error)]:
                receipts=[]
                for offset in range(0,len(raw),3_000_000):
                    receipts.append(retain('external.v3_model_stream_chunk',{'stream':name,'offset':offset,
                        'total_bytes':len(raw),'sha256':sha256(raw).hexdigest(),
                        'content_base64':base64.b64encode(raw[offset:offset+3_000_000]).decode()}))
                streams[name]={'bytes':len(raw),'sha256':sha256(raw).hexdigest(),'receipts':receipts}
            retain('external.v3_model_transport',{'exit_code':exit_code,'streams':streams,
                'supervisor_elapsed_ms':supervisor_ms,'termination':termination,'temporary_auth_cleanup':auth_cleanup})
            if exit_code!=0:
                save('external.v3_models_stopped',{**cell,'reason':'supervisor_failure','process_scope_empty':True,
                    'no_automatic_retry':True,'remaining_cells_not_dispatched':True})
                raise RuntimeError('supervisor failure retained; inspect before any further inference')
            result=json.loads(output)
            retain('external.v3_model_result',{**cell,**model_metadata(result),'raw_response_transport':streams,
                    'supervisor_elapsed_ms':supervisor_ms,'termination':termination})
            candidate=captured_case(case,writers_stopped=True,expected_git=initial['git_metadata'],process_scope=str(group))
            original={n:base64.b64decode(v,validate=True) for n,v in source['files_base64'].items()}
            current={n:base64.b64decode(v,validate=True) for n,v in candidate['files_base64'].items()}
            from benchmarks.code_replay.eligibility_binding import SOURCE_PROFILES
            roots,tests=SOURCE_PROFILES[identity.rsplit('-',1)[0].replace('__','/')]
            comparison=collect_source_patch(original,current,SourcePolicy(roots,test_roots=tests))
            mode_changes=[n for n in source['modes'] if n in candidate['modes'] and source['modes'][n]!=candidate['modes'][n]]
            candidate.update(changed_paths=comparison['changed_paths'],ignored_test_changes=comparison['ignored_test_changes'],
                out_of_scope_changes=comparison['out_of_scope_changes'],mode_changes=mode_changes,
                source_policy_compliant=not comparison['out_of_scope_changes'] and not comparison['ignored_test_changes']
                    and not mode_changes and candidate['git_metadata_unchanged'])
            raw=json.dumps(candidate,sort_keys=True,separators=(',',':')).encode();receipts=[]
            for offset in range(0,len(raw),3_000_000):
                receipts.append(retain('external.v3_candidate_chunk',{'offset':offset,
                    'total_bytes':len(raw),'sha256':sha256(raw).hexdigest(),
                    'content_base64':base64.b64encode(raw[offset:offset+3_000_000]).decode()}))
            summary={**cell,'source_bytes':len(raw),'source_sha256':sha256(raw).hexdigest(),'receipts':receipts,
                'source_policy_compliant':candidate['source_policy_compliant'],'changed_paths':candidate['changed_paths'],
                'usage_receipts':model_metadata(result)['usage_receipts'],'stop_reason':result['stop_reason'],
                'elapsed_ms':result['elapsed_ms'],'supervisor_elapsed_ms':supervisor_ms,'private_grade':'pending'}
            retain('external.v3_case_completed',summary);save('external.v3_case_completed',summary);finished.append(summary)
            print(json.dumps({**cell,'phase':'captured','completed_attempts':len(finished),
                              'elapsed_ms':result['elapsed_ms'],'stop_reason':result['stop_reason']}),flush=True)
    save('external.v3_models_completed',{'attempts_completed':len(finished),'expected_attempts':76,
         'private_grading':'pending','not_goal_acceptance':True,'case_runs':[r['task_run'] for r in finished]})


if __name__=='__main__':main()
