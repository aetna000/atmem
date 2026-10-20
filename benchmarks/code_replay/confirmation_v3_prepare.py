"""Final pre-inference execution lock with exact private graders and source state."""
import base64
from hashlib import sha256
import json
from pathlib import Path

RUN='external-windows-confirmation-v3-execution-lock-v1-20261018'


def main():
    from atmem.evidence import EvidenceScope,EvidencePrincipal,EvidenceRole
    from benchmarks.code_replay.run_evidence import operational_evidence
    from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
    from benchmarks.code_replay.confirmation_v3_lock import require_cases,qualified_grade_plan
    from benchmarks.code_replay.confirmation_v3_capture import captured_case
    from benchmarks.code_replay.confirmation_v3_process_scope import CHILD_BOOTSTRAP
    from benchmarks.code_replay.windows_confirmation_exports import recover_export
    from benchmarks.code_replay.windows_cohort import policy
    from benchmarks.code_replay.eligibility_binding import SOURCE_PROFILES
    scope=EvidenceScope('benchmark','local-operator','click-20261017')
    principal=EvidencePrincipal('local-benchmark-operator',EvidenceRole.ADMINISTRATOR,scope)
    vault=operational_evidence(EVIDENCE_ROOT,vault_id='confirmation-v1',scope=scope,writing_run=RUN)
    if vault.inspect(principal,RUN):raise ValueError('execution preparation already attempted')
    def events(run):return vault.inspect(principal,run)
    def only(run,kind):
        rows=[e['envelope']['payload'] for e in events(run) if e['envelope']['event_type']==kind]
        if len(rows)!=1:raise ValueError('exact terminal prerequisite required: '+kind)
        return rows[0]
    staging='external-windows-confirmation-v3-staging-v1-20261018'
    manifest=only(staging,'external.confirmation_v3_manifest_frozen')
    stages=[e['envelope']['payload'] for e in events(staging) if e['envelope']['event_type']=='external.confirmation_v3_block_result']
    end=only(staging,'external.confirmation_v3_staging_completed')
    mcp=only('external-windows-confirmation-v3-mcp-readiness-v1-20261018','external.v3_mcp_readiness_completed')
    sandbox=only('external-windows-confirmation-v3-sandbox-v2-20261018','external.v3_sandbox_completed')
    processes=only('external-windows-confirmation-v3-process-scope-v1-20261018','external.v3_process_scope_completed')
    require_cases(mcp['results'],manifest['blocks']);require_cases(sandbox['results'],manifest['blocks'])
    if (not end['all_76_cases_staged'] or len(stages)!=38 or processes['qualified'] is not True
            or processes['model_calls']!=0):raise ValueError('complete installed/case/lifecycle qualification required')
    def save(kind,payload):return vault.capture(run_id=RUN,kind=kind,principal=principal,payload=payload)
    save('external.v3_execution_preparation_planned',{'driver_source':job['driver_source'],
         'sources':job['sources'],'protocol':job['protocol'],'model_calls':0,'stage_run':staging,
         'model_driver_source':job['model_driver_source'],'grading_after_all_model_attempts':True})
    sources={};grade_refs={};prompts={};probes={};boundary_events={}
    def grading_events(run):
        if run.startswith('external-windows-runtime-projection-'):
            if run not in boundary_events:boundary_events[run]=events(run)
            return boundary_events[run]
        return events(run)
    for identity,d in manifest['source_descriptors'].items():
        source=recover_export(events(d['export_run']),d);sources[identity]=source
        grade=qualified_grade_plan(vault,principal,identity,d,manifest['images'][identity],event_reader=grading_events)
        if grade['material']['base_commit']!=source['base_commit']:raise ValueError('private/public base differs')
        target_run=RUN+'-task-'+identity
        target=operational_evidence(EVIDENCE_ROOT,vault_id='confirmation-v1',scope=scope,writing_run=target_run)
        if target.inspect(principal,target_run):raise ValueError('grader binding already retained')
        receipt=target.capture(run_id=target_run,kind='external.v3_private_grader_frozen',principal=principal,payload=grade)
        grade_refs[identity]={'task_run':target_run,'receipt':receipt,'expected_f2p':grade['expected_f2p'],
                              'expected_p2p':grade['expected_p2p'],'program_sha256':grade['program_sha256']}
        roots,_=SOURCE_PROFILES[identity.rsplit('-',1)[0].replace('__','/')]
        prompts[identity]=policy(roots)+manifest['issues'][identity]
        probes[identity]=next(n for n in sorted(source['files_base64']) if n.endswith('.py') and any(n.startswith(r) for r in roots))
        print(json.dumps({'phase':'grader_locked','identity':identity,'model_calls':0}),flush=True)
    originals={}
    for row in sorted(stages,key=lambda r:r['block']['slot']):
        block=row['block'];originals[str(block['slot'])]={}
        for arm in block['order']:
            case=row['cases'][arm];current=captured_case(case,writers_stopped=True)
            original=sources[block['instance_id']]
            if (current['files_base64']!=original['files_base64'] or current['modes']!=original['modes']
                    or current['git_metadata'] is None or current['git_metadata']['commit']!=case['initial_commit']
                    or not current['temporary_cli_auth_absent']):raise ValueError('initial full source/auth/ref state differs')
            metadata={k:v for k,v in current.items() if k not in {'files_base64','modes'}}
            originals[str(block['slot'])][arm]=metadata
            save('external.v3_initial_source_verified',{'block':block,'arm':arm,**metadata,'model_calls':0})
    lock={'format':'atmem-confirmation-v3-execution-lock-v1','staging_manifest':manifest,
        'staged_blocks':sorted(stages,key=lambda r:r['block']['slot']),'grade_plans':grade_refs,
        'initial_sources':originals,'prompts':prompts,'probe_sources':probes,
        'process_bootstrap':CHILD_BOOTSTRAP,'supporting_sources':job['sources'],
        'model_driver_source':job['model_driver_source'],'protocol':job['protocol'],
        'model_workers':1,'model_attempts':76,'max_seconds':600,'max_tool_calls':100,
        'max_context_bytes':4096,'private_grading':'after all attempts; no feedback',
        'model_calls_so_far':0,'readiness_cases':76}
    receipt=save('external.v3_execution_manifest_frozen',lock)
    save('external.v3_execution_preparation_completed',{'manifest_receipt':receipt,
        'manifest_sha256':sha256(json.dumps(lock,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        'all_76_initial_sources_verified':True,'all_19_private_graders_bound':True,'model_calls':0})
    print(json.dumps({'ready_for_scoring':True,'model_attempts':76,'model_calls':0}),flush=True)


if __name__=='__main__':main()
