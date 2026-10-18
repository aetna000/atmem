"""Run the already locked CD2 models once, then postprocess the terminal cohort."""
import base64
import inspect
import json
from pathlib import Path
import subprocess

from benchmarks.code_replay import query_nomination_screen as screen
from benchmarks.code_replay.query_nomination_preparation import RUN as PREPARATION
from benchmarks.code_replay.query_nomination_preview import evidence

RUN = screen.PREFIX + 'execution-v1-20261018'
SUBMIT = RUN + '-submission'


def remote():
    import sys
    import types
    import benchmarks.code_replay
    from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
    from benchmarks.code_replay.run_evidence import operational_evidence
    from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
    scope = EvidenceScope('benchmark', 'local-operator', 'click-20261017')
    principal = EvidencePrincipal('local-benchmark-operator', EvidenceRole.ADMINISTRATOR, scope)
    vault = operational_evidence(EVIDENCE_ROOT, vault_id='confirmation-v1', scope=scope, writing_run=job['run'])
    if vault.inspect(principal, job['run']):
        raise ValueError('execution already attempted; never restart original models or grades')
    def only(run, kind):
        result, = [r['envelope']['payload'] for r in vault.inspect(principal, run)
                   if r['envelope']['event_type'] == kind]
        return result
    ready = only(job['preparation'], 'external.query_nomination_preparation_completed')
    plan = only(job['preparation'], 'external.query_nomination_preparation_planned')['job']
    if (ready['qualified'] is not True or ready['model_calls'] != 0
            or [r['phase'] for r in ready['results']] != ['staging', 'readiness', 'sandbox', 'process', 'prepare']):
        raise ValueError('all five terminal pre-inference phases required')
    def save(kind, payload):
        return vault.capture(run_id=job['run'], kind=kind, principal=principal, payload=payload)
    old_post = only('external-windows-corrective-development-postprocessing-v1-20261018',
                    'external.v3_postprocessing_planned')
    save('external.query_nomination_execution_planned', {
        'controller_source': job['program'], 'preparation_run': job['preparation'],
        'sources': plan['sources'], 'support': plan['support'],
        'bridge_source': old_post['bridge_source'], 'no_model_retries': True,
        'grading_only_after_all_38_models': True, 'archive_acceptance': 'separate required gate'})
    for name, source in plan['support'].items():
        module = types.ModuleType(name); module.__file__ = '<retained-CD2-support:' + name + '>'
        sys.modules[name] = module
        exec(compile(source, module.__file__, 'exec'), module.__dict__)
        parent, attribute = name.rsplit('.', 1)
        setattr(sys.modules[parent], attribute, module)
    model = {'__name__': 'locked_cd2_model_definition'}
    exec(compile(plan['sources']['models'], '<locked-CD2-models>', 'exec'), model)
    model['job'] = {'driver_source': plan['sources']['models']}
    save('external.query_nomination_execution_phase_started', {'phase': 'models', 'outcome_retries': 0})
    model['main']()
    terminal = only(model['RUN'], 'external.v3_models_completed')
    if terminal['attempts_completed'] != 38:
        raise ValueError('all 38 model captures required before any private grading')
    save('external.query_nomination_execution_phase_completed', {
        'phase': 'models', 'attempts_completed': 38, 'outcome_retries': 0})
    post = {'__name__': 'locked_cd2_postprocessing_definition'}
    exec(compile(plan['sources']['finish'], '<locked-CD2-postprocessing>', 'exec'), post)
    post['job'] = {'driver_source': plan['sources']['finish'], 'bridge_source': old_post['bridge_source'],
                   'postprocess_programs': {'benchmarks.code_replay.confirmation_v3_' + name:
                                            plan['sources'][name] for name in ('grade', 'report', 'retain')}}
    save('external.query_nomination_execution_phase_started', {'phase': 'postprocess', 'outcome_retries': 0})
    post['main']()
    done = only(post['RUN'], 'external.v3_postprocessing_completed')
    if done['comparison_and_public_recovery'] is not True:
        raise ValueError('complete matched comparison and public recovery required')
    save('external.query_nomination_execution_completed', {
        'comparison_and_public_recovery': True, 'archive_acceptance': 'still required',
        'goal_complete': False, 'outcome_retries': 0})


def main():
    import os
    from benchmarks.code_replay.windows_transport import framed_command, framed_input
    from benchmarks.code_replay.corrective_transfer_recovery import ssh_options
    os.environ['ATMEM_BENCHMARK_PER_RUN_VAULTS'] = '1'
    vault, principal = evidence(SUBMIT)
    if vault.inspect(principal, SUBMIT):
        raise ValueError('execution already submitted; inspect original handle')
    payload = {'program': inspect.getsource(remote) + '\nremote()\n', 'run': RUN, 'preparation': PREPARATION}
    setup = '''import os,sys,json
job=json.load(sys.stdin)
os.environ.update(ATMEM_BENCHMARK_ROOT='/home/jt/atmem-benchmark-runtime-20261018/bookkeeping-v1',ATMEM_BENCHMARK_PER_RUN_VAULTS='1',ATMEM_BENCHMARK_LOCAL_WSL='1',PYTHONDONTWRITEBYTECODE='1')
sys.path[:0]=['/home/jt/atmem-benchmark-runtime-20261018/operator-source-v13','/home/jt/atmem-benchmark-runtime-20261018/operator-deps-v1']
os.chdir('/home/jt/atmem-benchmark-runtime-20261018/operator-source-v13')
exec(compile(job['program'],'<query-nomination-execution>','exec'))
'''
    request = {'program': "import subprocess,sys,json;p=subprocess.run([job['python'],'-I','-u','-c',job['setup']],input=json.dumps(job['payload']).encode());sys.exit(p.returncode)",
               'python': '/home/jt/atmem-benchmark-runtime-20261018/product-build-arw_zz8r/venv/bin/python',
               'setup': setup, 'payload': payload}
    def save(kind, value):
        return vault.capture(run_id=SUBMIT, kind=kind, principal=principal, payload=value)
    save('external.query_nomination_execution_submission_planned', {
        'request': request, 'controller_source': Path(__file__).read_text(), 'outcome_retries': 0})
    result = subprocess.run(ssh_options() + ['user@192.168.0.87', framed_command()[-1]],
                            input=framed_input(request), capture_output=True)
    save('external.query_nomination_execution_submission_result', {
        'exit_code': result.returncode, 'stdout_base64': base64.b64encode(result.stdout).decode(),
        'stderr_base64': base64.b64encode(result.stderr).decode()})
    print(result.stdout.decode(), end='', flush=True)
    if result.returncode:
        raise RuntimeError('execution observation failed; inspect original remote state, never restart outcomes')


if __name__ == '__main__':
    main()
