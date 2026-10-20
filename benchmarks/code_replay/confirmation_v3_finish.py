"""Postprocess the existing cohort only; never launch or retry model inference."""
import json
import time
import types
import sys
import ast

RUN = 'external-windows-confirmation-v3-postprocessing-v1-20261018'


def readiness(events):
    completed = [e for e in events if e['envelope']['event_type'] == 'external.v3_models_completed']
    stopped = [e for e in events if e['envelope']['event_type'] == 'external.v3_models_stopped']
    if stopped or len(completed) > 1:
        raise ValueError('model execution stopped or ambiguous; do not restart it')
    if not completed:
        return False
    if completed[0]['envelope']['payload']['attempts_completed'] != 76:
        raise ValueError('incomplete terminal cohort')
    return True


def pregrading_amendment(existing,programs):
    kinds=[e['envelope']['event_type'] for e in existing]
    if kinds!=['external.v3_postprocessing_planned','external.v3_pregrading_transport_pause']:
        raise ValueError('only exact zero-phase paused postprocessor may be resumed')
    old=existing[0]['envelope']['payload']['postprocess_programs']
    if set(old)!=set(programs):raise ValueError('postprocessing module set changed')
    name='benchmarks.code_replay.confirmation_v3_grade'
    if any(old[k]!=programs[k] for k in old if k!=name):raise ValueError('only grader dispatch retention may change')
    current=programs[name]
    helpers=[n for n in ast.parse(current).body if isinstance(n,ast.FunctionDef) and n.name=='retain_dispatch']
    if len(helpers)!=1:raise ValueError('one bounded dispatch retention helper required')
    helper=ast.get_source_segment(current,helpers[0])
    stripped=current.replace(helper+'\n\n\n','',1)
    marker="retain('external.v3_grade_dispatch',"
    if old[name].count(marker)!=1 or stripped!=old[name].replace(marker,'retain_dispatch(retain,',1):
        raise ValueError('grader, request or execution semantics changed beyond retention')
    if existing[1]['envelope']['payload']['grading_phases_started']!=0:
        raise ValueError('no grading outcome may be retried')
    return True


def main(*,resume_pregrading=False):
    from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
    from benchmarks.code_replay.run_evidence import operational_evidence
    from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
    scope = EvidenceScope('benchmark', 'local-operator', 'click-20261017')
    principal = EvidencePrincipal('local-benchmark-operator', EvidenceRole.ADMINISTRATOR, scope)
    vault = operational_evidence(EVIDENCE_ROOT, vault_id='confirmation-v1', scope=scope, writing_run=RUN)
    existing=vault.inspect(principal,RUN)
    if existing and not resume_pregrading:raise ValueError('postprocessor already dispatched; inspect its handle')
    if resume_pregrading:
        pregrading_amendment(existing,job['postprocess_programs'])
        grading='external-windows-confirmation-v3-grading-v1-20261018'
        probe=operational_evidence(EVIDENCE_ROOT,vault_id='confirmation-v1',scope=scope,writing_run=grading)
        if probe.inspect(principal,grading):raise ValueError('grading already started; amendment prohibited')
    def save(kind, payload): return vault.capture(run_id=RUN, kind=kind, principal=principal, payload=payload)
    save('external.v3_postprocessing_pregrading_amended' if resume_pregrading else 'external.v3_postprocessing_planned', {'driver_source': job['driver_source'],
        'postprocess_programs': job['postprocess_programs'], 'bridge_source': job['bridge_source'],
        'model_retries': 0, 'grading_only_after_all_76_models': True, 'archive_acceptance': 'separate required gate'})
    model_run = 'external-windows-confirmation-v3-models-v1-20261018'
    while not readiness(vault.inspect(principal, model_run)):
        time.sleep(30)
    for name, source in job['postprocess_programs'].items():
        module = types.ModuleType(name); sys.modules[name] = module
        exec(compile(source, name + '.py', 'exec'), module.__dict__)
    for short in ('grade', 'report', 'retain'):
        name = 'benchmarks.code_replay.confirmation_v3_' + short
        module = sys.modules[name]
        module.job = {'driver_source': job['postprocess_programs'][name], 'bridge_source': job['bridge_source']}
        save('external.v3_postprocessing_phase_started', {'phase': short, 'model_retries': 0})
        print(json.dumps({'postprocessing_phase': short}), flush=True)
        module.main()
        save('external.v3_postprocessing_phase_completed', {'phase': short, 'model_retries': 0})
    save('external.v3_postprocessing_completed', {'comparison_and_public_recovery': True,
        'archive_acceptance': 'pending', 'goal_complete': False})


if __name__ == '__main__': main(resume_pregrading=job.get('resume_pregrading',False))
