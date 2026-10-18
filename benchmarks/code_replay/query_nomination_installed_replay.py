"""Replay every retained CD1 query with the actual installed candidate package."""
import base64
import inspect
import json
from pathlib import Path
import subprocess

from benchmarks.code_replay.query_nomination_preview import CANDIDATE, RUN as BUILD, evidence
from benchmarks.code_replay.query_nomination_qualification import WHEEL

RUN = 'external-windows-query-nomination-installed-replay-v1-20261018'
SUBMIT = RUN + '-submission'
PYTHON = '/home/jt/atmem-benchmark-runtime-20261018/product-build-cc5aho32/venv/bin/python'
LOCK = 'external-windows-corrective-development-execution-lock-v1-20261018'


def worker():
    import base64
    import contextlib
    from hashlib import sha256
    import io
    import json
    import os
    from pathlib import Path
    import sys
    import zlib
    # Import before operator paths: the benchmark checkout must not shadow product.
    from atmem.knowledge.code import packing
    if (not Path(packing.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
            or sha256(Path(packing.__file__).read_bytes()).hexdigest() != job['candidate']):
        raise ValueError('exact installed preview source required')
    os.environ.update(ATMEM_BENCHMARK_ROOT='/home/jt/atmem-benchmark-runtime-20261018/bookkeeping-v1',
                      ATMEM_BENCHMARK_PER_RUN_VAULTS='1', ATMEM_BENCHMARK_LOCAL_WSL='1',
                      PYTHONDONTWRITEBYTECODE='1')
    sys.path[:0] = ['/home/jt/atmem-benchmark-runtime-20261018/operator-source-v13',
                    '/home/jt/atmem-benchmark-runtime-20261018/operator-deps-v1']
    from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
    from benchmarks.code_replay.run_evidence import operational_evidence
    from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
    scope = EvidenceScope('benchmark', 'local-operator', 'click-20261017')
    principal = EvidencePrincipal('local-benchmark-operator', EvidenceRole.ADMINISTRATOR, scope)
    vault = operational_evidence(EVIDENCE_ROOT, vault_id='confirmation-v1', scope=scope, writing_run=job['run'])
    def only(rows, kind):
        value, = [r['envelope']['payload'] for r in rows if r['envelope']['event_type'] == kind]
        return value
    def save(kind, payload):
        return vault.capture(run_id=job['run'], kind=kind, principal=principal, payload=payload)
    if vault.inspect(principal, job['run']):
        raise ValueError('installed replay already attempted; inspect original state')
    build_rows = vault.inspect(principal, job['build'])
    build = only(build_rows, 'external.query_nomination_build_completed')
    plan = only(build_rows, 'external.query_nomination_build_planned')
    if (build['qualified'] is not True or build['wheel_sha256'] != job['wheel']
            or build['python'] != sys.executable or build['candidate_packing_sha256'] != job['candidate']):
        raise ValueError('exact qualified installed build required')
    static_root = 'external-windows-corrective-development-source-location-diagnostic-v1-20261018'
    report = only(plan['static_proofs'][static_root], 'external.nomination_diagnostic_completed')
    expected = {r['identity']: r for r in report['cases']}
    lock = only(vault.inspect(principal, job['lock']), 'external.v3_execution_manifest_frozen')
    stages = lock['staged_blocks']
    if (len(stages) != 19 or len(expected) != 19
            or {r['block']['instance_id'] for r in stages} != set(expected)
            or set(lock['staging_manifest']['issues']) != set(expected)):
        raise ValueError('all nineteen original queries and source bindings required')
    namespace = {'base64': base64, 'sha256': sha256, 'json': json, 'zlib': zlib}
    exec(compile(job['generation_helper'], '<retained-generation-decoder>', 'exec'), namespace)
    save('external.query_nomination_installed_replay_planned', {
        'worker_source': job['program'], 'generation_helper': job['generation_helper'],
        'build': build, 'lock_run': job['lock'], 'model_calls': 0,
        'static_comparison_origin': 'Mac archive-only replay; actual installed packs recomputed here'})
    results = []
    for stage in stages:
        identity = stage['block']['instance_id']; reference = expected[identity]
        if stage['task_run'] != reference['stage_run']:
            raise ValueError('original stage differs from static comparison')
        generation, case = namespace['retained_generation'](vault.inspect(principal, stage['task_run']))
        task = lock['staging_manifest']['issues'][identity]
        if (case['prepared']['request']['task'] != task
                or case['prepared']['package']['content'] != reference['baseline_pack']):
            raise ValueError('original query or baseline pack differs')
        warnings = io.StringIO()
        with contextlib.redirect_stderr(warnings):
            actual = packing.pack_generation(generation, task, budget=4096)
        result = {'identity': identity, 'stage_run': stage['task_run'], 'task': task,
                  'installed_pack': actual, 'expected_pack': reference['candidate_pack'],
                  'pack_sha256': sha256(actual.encode()).hexdigest(), 'pack_bytes': len(actual.encode()),
                  'matches': actual == reference['candidate_pack'] and len(actual.encode()) <= 4096,
                  'warnings': warnings.getvalue(), 'model_calls': 0}
        save('external.query_nomination_installed_replay_case', result)
        results.append(result)
    summary = {'qualified': len(results) == 19 and all(r['matches'] for r in results),
               'identities': len(results), 'model_calls': 0, 'wheel_sha256': job['wheel'],
               'packing_path': packing.__file__, 'candidate_sha256': job['candidate']}
    save('external.query_nomination_installed_replay_completed', summary)
    print(json.dumps(summary), flush=True)
    if not summary['qualified']:
        raise ValueError('installed pack differs; preserve every case and investigate')


def main():
    import os
    from benchmarks.code_replay.packing_replay_audit import retained_generation
    from benchmarks.code_replay.windows_transport import framed_command, framed_input
    from benchmarks.code_replay.corrective_transfer_recovery import ssh_options
    os.environ['ATMEM_BENCHMARK_PER_RUN_VAULTS'] = '1'
    vault, principal = evidence(SUBMIT)
    if vault.inspect(principal, SUBMIT):
        raise ValueError('installed replay already submitted; inspect original handle')
    payload = {'program': inspect.getsource(worker) + '\nworker()\n',
               'generation_helper': inspect.getsource(retained_generation),
               'run': RUN, 'build': BUILD, 'lock': LOCK, 'candidate': CANDIDATE, 'wheel': WHEEL}
    loader = "import json,sys;job=json.load(sys.stdin);exec(compile(job['program'],'<installed-query-nomination-replay>','exec'))"
    request = {'program': "import subprocess,sys,json;p=subprocess.run([job['python'],'-I','-u','-c',job['loader']],input=json.dumps(job['payload']).encode());sys.exit(p.returncode)",
               'python': PYTHON, 'loader': loader, 'payload': payload}
    def save(kind, value):
        return vault.capture(run_id=SUBMIT, kind=kind, principal=principal, payload=value)
    save('external.query_nomination_installed_replay_submission_planned', {
        'request': request, 'controller_source': Path(__file__).read_text(), 'model_calls': 0})
    result = subprocess.run(ssh_options() + ['user@192.168.0.87', framed_command()[-1]],
                            input=framed_input(request), capture_output=True)
    save('external.query_nomination_installed_replay_submission_result', {
        'exit_code': result.returncode, 'stdout_base64': base64.b64encode(result.stdout).decode(),
        'stderr_base64': base64.b64encode(result.stderr).decode()})
    print(result.stdout.decode(), end='', flush=True)
    if result.returncode:
        raise RuntimeError('installed replay failed; inspect retained state, no automatic restart')


if __name__ == '__main__':
    main()
