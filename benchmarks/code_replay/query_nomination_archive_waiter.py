"""Wait for original CD2 results, then export using the actual retained helpers."""
import base64
import inspect
import json
from pathlib import Path
import subprocess

from benchmarks.code_replay import confirmation_v3_archive, query_nomination_archive
from benchmarks.code_replay.query_nomination_preview import evidence
from benchmarks.code_replay.query_nomination_screen import PREFIX

RUN = PREFIX + 'archive-waiter-v1-20261018'
SUBMIT = RUN + '-submission'
REMOTE = '/home/jt/atmem-benchmark-runtime-20261018'
OUTPUT = REMOTE + '/query-nomination-development-archive-v1'
KEYS = REMOTE + '/query-nomination-development-archive-keys-v1'


def remote():
    import sys
    import time
    import types
    from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
    from benchmarks.code_replay.run_evidence import operational_evidence
    from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
    scope = EvidenceScope('benchmark', 'local-operator', 'click-20261017')
    principal = EvidencePrincipal('local-benchmark-operator', EvidenceRole.ADMINISTRATOR, scope)
    vault = operational_evidence(EVIDENCE_ROOT, vault_id='confirmation-v1', scope=scope, writing_run=job['run'])
    if vault.inspect(principal, job['run']):
        raise ValueError('archive waiter already submitted; inspect original handle')
    def of(rows, kind):
        return [r['envelope']['payload'] for r in rows if r['envelope']['event_type'] == kind]
    def save(kind, payload):
        return vault.capture(run_id=job['run'], kind=kind, principal=principal, payload=payload)
    save('external.query_nomination_archive_waiter_planned', {
        'job': job, 'models_repeated': 0, 'private_grades_repeated': 0})
    while True:
        rows = vault.inspect(principal, job['prefix']+'postprocessing-v1-20261018')
        ends = of(rows, 'external.v3_postprocessing_completed')
        models = vault.inspect(principal, job['prefix']+'models-v1-20261018')
        if of(models, 'external.v3_models_stopped') or len(ends) > 1:
            raise ValueError('stopped or ambiguous original cohort; no restart')
        if ends:
            if ends[0]['comparison_and_public_recovery'] is not True:
                raise ValueError('complete original comparison/public recovery required')
            break
        time.sleep(30)
    post, = of(rows, 'external.v3_postprocessing_planned')
    for name, source in post['postprocess_programs'].items():
        module = types.ModuleType(name); module.__file__ = '<actual-retained-CD2-helper:' + name + '>'
        sys.modules[name] = module
        exec(compile(source, module.__file__, 'exec'), module.__dict__)
    archive = types.ModuleType('benchmarks.code_replay.confirmation_v3_archive')
    sys.modules[archive.__name__] = archive
    exec(compile(job['archive_source'], '<retained-CD2-archive>', 'exec'), archive.__dict__)
    # Resolve actual helper imports before allocating an export directory.
    archive.validate_run(job['prefix']+'postprocessing-v1-20261018', rows)
    archive.job = {'driver_source': job['archive_source'], 'output': job['output'], 'key_root': job['keys']}
    save('external.query_nomination_archive_export_started', {
        'archive_source': job['archive_source'], 'helper_sources': post['postprocess_programs'],
        'models_repeated': 0, 'private_grades_repeated': 0})
    archive.main()
    terminal, = of(vault.inspect(principal, archive.RUN), 'external.v3_archive_export_completed')
    save('external.query_nomination_archive_waiter_completed', {
        'archive_run': archive.RUN, 'exported_runs': terminal['runs'],
        'MEM_copy_and_independent_recovery': 'still required', 'goal_complete': False})


def main():
    import os
    from benchmarks.code_replay.windows_transport import framed_command, framed_input
    from benchmarks.code_replay.corrective_transfer_recovery import ssh_options
    os.environ['ATMEM_BENCHMARK_PER_RUN_VAULTS'] = '1'
    vault, principal = evidence(SUBMIT)
    if vault.inspect(principal, SUBMIT):
        raise ValueError('archive waiter already submitted; inspect original handle')
    payload = {'program': inspect.getsource(remote)+'\nremote()\n', 'run': RUN, 'prefix': PREFIX,
               'archive_source': query_nomination_archive.archive_source(inspect.getsource(confirmation_v3_archive)),
               'output': OUTPUT, 'keys': KEYS}
    setup = '''import os,sys,json
job=json.load(sys.stdin)
os.environ.update(ATMEM_BENCHMARK_ROOT='/home/jt/atmem-benchmark-runtime-20261018/bookkeeping-v1',ATMEM_BENCHMARK_PER_RUN_VAULTS='1',ATMEM_BENCHMARK_LOCAL_WSL='1',PYTHONDONTWRITEBYTECODE='1')
sys.path[:0]=['/home/jt/atmem-benchmark-runtime-20261018/operator-source-v13','/home/jt/atmem-benchmark-runtime-20261018/operator-deps-v1']
os.chdir('/home/jt/atmem-benchmark-runtime-20261018/operator-source-v13')
exec(compile(job['program'],'<query-nomination-archive-waiter>','exec'))
'''
    request = {'program': "import subprocess,sys,json;p=subprocess.run([job['python'],'-I','-u','-c',job['setup']],input=json.dumps(job['payload']).encode());sys.exit(p.returncode)",
               'python': REMOTE+'/product-build-arw_zz8r/venv/bin/python', 'setup': setup, 'payload': payload}
    def save(kind, value):
        return vault.capture(run_id=SUBMIT, kind=kind, principal=principal, payload=value)
    save('external.query_nomination_archive_waiter_submission_planned', {
        'request': request, 'controller_source': Path(__file__).read_text(), 'models_repeated': 0})
    result = subprocess.run(ssh_options()+['user@192.168.0.87', framed_command()[-1]],
                            input=framed_input(request), capture_output=True)
    save('external.query_nomination_archive_waiter_submission_result', {
        'exit_code': result.returncode, 'stdout_base64': base64.b64encode(result.stdout).decode(),
        'stderr_base64': base64.b64encode(result.stderr).decode()})
    print(result.stdout.decode(), end='', flush=True)
    if result.returncode:
        raise RuntimeError('archive observation failed; inspect original remote state, no automatic restart')


if __name__ == '__main__':
    main()
