"""Separate one-file preview using the already exercised frozen-source builder."""
import base64
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

RUN = 'external-windows-product-build-query-nomination-v1-20261018'
SUBMIT = RUN+'-submission'
PRIOR = 'external-windows-product-build-source-storage-v1-20261018'
CANDIDATE = '004a4ff9f66843206456f28d2bd08b59c09196ecee16c88a25b51dc85fa62020'
BASE_WHEEL = 'e8d98dadfa98554ba38311096a7b90dac815bbbe03c6c35dae430bed54ee7bf6'
ROOTS = ('external-windows-corrective-development-layout-diagnostic-v1-20261018',
         'external-windows-corrective-development-reference-diagnostic-v1-20261018',
         'external-windows-corrective-development-source-location-diagnostic-v1-20261018')


def of(rows, kind):
    return [r['envelope']['payload'] for r in rows if r['envelope']['event_type'] == kind]


def static_ready(proofs, candidate):
    if set(proofs) != set(ROOTS) or sha256(candidate.encode()).hexdigest() != CANDIDATE:
        raise ValueError('exact candidate and complete three-step static evidence required')
    originals = None
    for root in ROOTS:
        rows = proofs[root]
        kind = 'external.layout_diagnostic_completed' if root == ROOTS[0] else 'external.nomination_diagnostic_completed'
        done, = of(rows, kind)
        summary = done['summary']; cases = done['cases']
        if (summary['identities'] != 19 or summary['all_original_packs_reproduced'] is not True
                or summary['source_vault_opened'] is not False
                or summary['models_repeated'] != 0 or summary['private_grades_repeated'] != 0
                or len(cases) != 19 or len({r['identity'] for r in cases}) != 19
                or any(r['original_pack_reproduced'] is not True or len(r['candidate_pack'].encode()) > 4096 for r in cases)):
            raise ValueError('complete bounded no-inference static proof required')
        old = {r['identity']: (r['stage_run'], r['baseline_pack']) for r in cases}
        if originals is not None and originals != old:
            raise ValueError('static reports differ in original query/source cohort')
        originals = old
    final, = of(proofs[ROOTS[-1]], 'external.nomination_diagnostic_started')
    if final['candidate_source'] != candidate or final['candidate_sha256'] != CANDIDATE:
        raise ValueError('current source differs from terminal static candidate')
    return True


def evidence(run):
    from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
    from benchmarks.code_replay.run_evidence import operational_evidence
    from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
    scope = EvidenceScope('benchmark', 'local-operator', 'click-20261017')
    principal = EvidencePrincipal('local-benchmark-operator', EvidenceRole.ADMINISTRATOR, scope)
    return operational_evidence(EVIDENCE_ROOT, vault_id='confirmation-v1', scope=scope, writing_run=run), principal


def build():
    vault, principal = evidence(RUN)
    if vault.inspect(principal, RUN): raise ValueError('preview build already attempted; inspect its handle')
    static_ready(job['static_proofs'], job['candidate_source'])
    previous = vault.inspect(principal, PRIOR)
    plan, = of(previous, 'external.compatibility_build_planned')
    qualified, = of(previous, 'external.compatibility_build_completed')
    if qualified['qualified'] is not True or qualified['wheel_sha256'] != BASE_WHEEL:
        raise ValueError('exact qualified full-source base required')
    helper = {'__name__': 'retained_builder_helpers'}
    exec(compile(job['builder_source'], '<retained-frozen-source-builder>', 'exec'), helper)
    request = helper['candidate_job'](plan['job'], job['candidate_source'].encode())
    def save(kind, payload): return vault.capture(run_id=RUN, kind=kind, principal=principal, payload=payload)
    save('external.query_nomination_build_planned', {'driver_source': job['driver_source'],
        'builder_source': job['builder_source'], 'job': request, 'candidate_packing_sha256': CANDIDATE,
        'baseline_wheel_sha256': BASE_WHEEL, 'changed_product_files': ['atmem/knowledge/code/packing.py'],
        'static_proofs': job['static_proofs'], 'static_proof_origin': 'Mac-produced authorized records, not a Windows rerun',
        'prior_dependency_versions': qualified['dependency_versions'], 'protocol': job['protocol'],
        'owner_install_changed': False, 'frozen_candidate_replaced': False, 'model_calls': 0})
    from benchmarks.code_replay.windows_transport import framed_command, framed_input
    result = subprocess.run(framed_command(), input=framed_input(request), capture_output=True, timeout=1100)
    save('external.query_nomination_build_transport', {'exit_code': result.returncode,
        'stdout_base64': base64.b64encode(result.stdout).decode(), 'stderr_base64': base64.b64encode(result.stderr).decode()})
    if result.returncode: raise RuntimeError('preview build failed; no automatic restart')
    installed = json.loads(result.stdout); save('external.query_nomination_build_result', installed)
    if installed['qualified_installed_source_identity'] is not True:
        raise ValueError('complete installed source identity failed')
    program = "import importlib.metadata as m,json;print(json.dumps(sorted([{'name':d.metadata['Name'].lower(),'version':d.version} for d in m.distributions()],key=lambda r:r['name'])))"
    deps = subprocess.run([installed['python'], '-I', '-c', program], capture_output=True, timeout=30)
    actual = json.loads(deps.stdout) if deps.returncode == 0 else None
    program = '''from atmem.knowledge.code.packing import _query_term_weights,_query_call_names,_query_source_locations
import json
assert _query_term_weights('### Configuration\\nFix cache expiry.')['configuration']==0.25
assert 'name' not in _query_call_names('Reject an empty name (for example).')
assert _query_source_locations('https://host/src/api.py#L2',{'src/api.py':['','']})=={'src/api.py':[(2,2)]}
print(json.dumps({'query_nomination_import':True}))
'''
    ordinary = subprocess.run([installed['python'], '-I', '-c', program], capture_output=True, timeout=30,
        user=1000, group=1000, extra_groups=[],
        env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1'})
    proof = {'qualified': actual == qualified['dependency_versions'] and ordinary.returncode == 0,
        'wheel_sha256': installed['wheel_sha256'], 'python': installed['python'],
        'candidate_packing_sha256': CANDIDATE, 'dependency_versions': actual,
        'dependencies_equal': actual == qualified['dependency_versions'], 'ordinary_user_exit': ordinary.returncode,
        'ordinary_stdout_base64': base64.b64encode(ordinary.stdout).decode(),
        'ordinary_stderr_base64': base64.b64encode(ordinary.stderr).decode(),
        'model_calls': 0, 'preview_not_release': True, 'installed_real_source_replay_and_controls': 'still required'}
    save('external.query_nomination_build_completed', proof)
    if not proof['qualified']: raise ValueError('dependency or ordinary-user gate failed')
    print(json.dumps(proof), flush=True)


def main():
    import os
    from benchmarks.code_replay.windows_transport import framed_command, framed_input
    from benchmarks.code_replay.corrective_transfer_recovery import ssh_options
    os.environ['ATMEM_BENCHMARK_PER_RUN_VAULTS'] = '1'
    vault, principal = evidence(SUBMIT)
    if vault.inspect(principal, SUBMIT): raise ValueError('build submission already attempted; inspect retained state')
    source = Path(__file__).read_text(); candidate = Path('atmem/knowledge/code/packing.py').read_text()
    proofs = {root: vault.inspect(principal, root) for root in ROOTS}
    static_ready(proofs, candidate)
    payload = {'driver_source': source, 'candidate_source': candidate, 'static_proofs': proofs,
        'builder_source': Path('benchmarks/code_replay/corrective_build.py').read_text(),
        'protocol': Path('specs/042-atmem-code/query-nomination-development-screen-v1.md').read_text()}
    setup = '''import os,sys,json
job=json.load(sys.stdin)
os.environ.update(ATMEM_BENCHMARK_ROOT='/home/jt/atmem-benchmark-runtime-20261018/bookkeeping-v1',ATMEM_BENCHMARK_PER_RUN_VAULTS='1',ATMEM_BENCHMARK_LOCAL_WSL='1',PYTHONDONTWRITEBYTECODE='1')
sys.path[:0]=['/home/jt/atmem-benchmark-runtime-20261018/operator-source-v13','/home/jt/atmem-benchmark-runtime-20261018/operator-deps-v1']
os.chdir('/home/jt/atmem-benchmark-runtime-20261018/operator-source-v13')
exec(compile(job['driver_source'],'<query-nomination-preview>','exec'))
'''
    request = {'program': "import subprocess,sys,json;p=subprocess.run([job['python'],'-I','-u','-c',job['setup']],input=json.dumps(job['payload']).encode());sys.exit(p.returncode)",
        'python': '/home/jt/atmem-benchmark-runtime-20261018/product-build-arw_zz8r/venv/bin/python',
        'setup': setup, 'payload': payload}
    def save(kind, value): return vault.capture(run_id=SUBMIT, kind=kind, principal=principal, payload=value)
    save('external.query_nomination_build_submission_planned', {**payload, 'setup': setup,
         'models_repeated': 0, 'remote_run': RUN})
    result = subprocess.run(ssh_options()+['user@192.168.0.87', framed_command()[-1]],
                            input=framed_input(request), capture_output=True)
    save('external.query_nomination_build_submission_result', {'exit_code': result.returncode,
        'stdout_base64': base64.b64encode(result.stdout).decode(), 'stderr_base64': base64.b64encode(result.stderr).decode()})
    if result.returncode: raise RuntimeError('build transport failed; inspect remote state before any further action')
    print(result.stdout.decode(), end='', flush=True)


if __name__ == '__main__':
    build() if 'job' in globals() else main()
