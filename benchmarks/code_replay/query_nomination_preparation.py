"""Prepare fresh CD2 cases; stop before inference and inspect every phase gate."""
import base64
import inspect
import json
from pathlib import Path
import subprocess

from benchmarks.code_replay import query_nomination_screen as screen
from benchmarks.code_replay.query_nomination_preview import evidence

RUN = screen.PREFIX + 'preparation-v1-20261018'
SUBMIT = RUN + '-submission'


def remote():
    import sys
    import types
    from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
    from benchmarks.code_replay.run_evidence import operational_evidence
    from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
    import benchmarks.code_replay
    scope = EvidenceScope('benchmark', 'local-operator', 'click-20261017')
    principal = EvidencePrincipal('local-benchmark-operator', EvidenceRole.ADMINISTRATOR, scope)
    vault = operational_evidence(EVIDENCE_ROOT, vault_id='confirmation-v1', scope=scope, writing_run=job['run'])
    if vault.inspect(principal, job['run']):
        raise ValueError('preparation already attempted; inspect retained phase state')
    def only(run, kind):
        result, = [r['envelope']['payload'] for r in vault.inspect(principal, run)
                   if r['envelope']['event_type'] == kind]
        return result
    qualified = only(job['qualification'], 'external.compatibility_qualification_completed')
    replay = only(job['replay'], 'external.query_nomination_installed_replay_completed')
    if (qualified['qualified'] is not True or len(qualified['results']) != 5
            or any(r['model_calls'] != 0 for r in qualified['results'])
            or replay['qualified'] is not True or replay['identities'] != 19):
        raise ValueError('full installed qualification and all nineteen pack replays required')
    def save(kind, payload):
        return vault.capture(run_id=job['run'], kind=kind, principal=principal, payload=payload)
    save('external.query_nomination_preparation_planned', {
        'job': job, 'model_calls': 0, 'inference_authorized_by_preparation': False})
    for name, source in job['support'].items():
        module = types.ModuleType(name); module.__file__ = '<retained-CD2-support:' + name + '>'
        sys.modules[name] = module
        exec(compile(source, module.__file__, 'exec'), module.__dict__)
        parent, attribute = name.rsplit('.', 1)
        setattr(sys.modules[parent], attribute, module)
    checks = {
        'staging': ('external.confirmation_v3_staging_completed', 'all_38_cases_staged'),
        'readiness': ('external.v3_mcp_readiness_completed', 'all_38_cases_qualified'),
        'sandbox': ('external.v3_sandbox_completed', 'all_38_cases_qualified'),
        'process': ('external.v3_process_scope_completed', 'qualified'),
        'prepare': ('external.v3_execution_preparation_completed', 'all_38_initial_sources_verified'),
    }
    results = []
    for phase, (kind, gate) in checks.items():
        source = job['sources'][phase]
        namespace = {'__name__': 'cd2_phase_definition'}
        exec(compile(source, '<retained-CD2-' + phase + '>', 'exec'), namespace)
        phase_job = {'driver_source': source, 'protocol': job['protocol'],
                     'configuration_source': job['configuration_source'], 'sources': job['support'],
                     'model_driver_source': job['sources']['models']}
        namespace['job'] = phase_job
        save('external.query_nomination_preparation_phase_started', {
            'phase': phase, 'run': namespace['RUN'], 'job': phase_job, 'model_calls': 0})
        namespace['main']()
        terminal = only(namespace['RUN'], kind)
        if terminal.get(gate) is not True or terminal['model_calls'] != 0:
            raise ValueError('phase failed; preserve evidence and inspect: ' + phase)
        result = {'phase': phase, 'run': namespace['RUN'], 'qualified': True, 'model_calls': 0}
        save('external.query_nomination_preparation_phase_completed', result); results.append(result)
    save('external.query_nomination_preparation_completed', {
        'results': results, 'qualified': len(results) == 5, 'model_calls': 0,
        'next': 'separately launch the exact locked model source; no inference run by this controller'})


def main():
    import os
    from benchmarks.code_replay.corrective_qualification import configuration_source
    from benchmarks.code_replay.windows_execute import runner_helpers
    from benchmarks.code_replay.windows_transport import framed_command, framed_input
    from benchmarks.code_replay.corrective_transfer_recovery import ssh_options
    os.environ['ATMEM_BENCHMARK_PER_RUN_VAULTS'] = '1'
    vault, principal = evidence(SUBMIT)
    if vault.inspect(principal, SUBMIT):
        raise ValueError('preparation submission already attempted; inspect original state')
    payload = {'program': inspect.getsource(remote) + '\nremote()\n', 'run': RUN,
               'sources': screen.sources(), 'support': screen.supporting_sources(),
               'qualification': screen.QUALIFICATION, 'replay': screen.REPLAY,
               'configuration_source': configuration_source(runner_helpers()[1]),
               'protocol': Path('specs/042-atmem-code/query-nomination-development-screen-v1.md').read_text()}
    setup = '''import os,sys,json
job=json.load(sys.stdin)
os.environ.update(ATMEM_BENCHMARK_ROOT='/home/jt/atmem-benchmark-runtime-20261018/bookkeeping-v1',ATMEM_BENCHMARK_PER_RUN_VAULTS='1',ATMEM_BENCHMARK_LOCAL_WSL='1',PYTHONDONTWRITEBYTECODE='1')
sys.path[:0]=['/home/jt/atmem-benchmark-runtime-20261018/operator-source-v13','/home/jt/atmem-benchmark-runtime-20261018/operator-deps-v1']
os.chdir('/home/jt/atmem-benchmark-runtime-20261018/operator-source-v13')
exec(compile(job['program'],'<query-nomination-preparation>','exec'))
'''
    request = {'program': "import subprocess,sys,json;p=subprocess.run([job['python'],'-I','-u','-c',job['setup']],input=json.dumps(job['payload']).encode());sys.exit(p.returncode)",
               'python': '/home/jt/atmem-benchmark-runtime-20261018/product-build-arw_zz8r/venv/bin/python',
               'setup': setup, 'payload': payload}
    def save(kind, value):
        return vault.capture(run_id=SUBMIT, kind=kind, principal=principal, payload=value)
    save('external.query_nomination_preparation_submission_planned', {
        'request': request, 'controller_source': Path(__file__).read_text(), 'model_calls': 0})
    result = subprocess.run(ssh_options() + ['user@192.168.0.87', framed_command()[-1]],
                            input=framed_input(request), capture_output=True)
    save('external.query_nomination_preparation_submission_result', {
        'exit_code': result.returncode, 'stdout_base64': base64.b64encode(result.stdout).decode(),
        'stderr_base64': base64.b64encode(result.stderr).decode()})
    print(result.stdout.decode(), end='', flush=True)
    if result.returncode:
        raise RuntimeError('preparation failed; inspect original phase state before further action')


if __name__ == '__main__':
    main()
