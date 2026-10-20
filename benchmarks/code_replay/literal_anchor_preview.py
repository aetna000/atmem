"""Literal-anchor profile over the exercised frozen single-file builder."""
import ast
import base64
from hashlib import sha256
import inspect
import json
import os
from pathlib import Path
import subprocess

from benchmarks.code_replay import query_nomination_preview as previous
from benchmarks.code_replay.literal_anchor_diagnostic import RUN as DIAGNOSTIC, BASELINE
from benchmarks.code_replay.query_nomination_preview import evidence, of

RUN = 'external-windows-product-build-literal-anchors-v1-20261018'
SUBMIT = RUN+'-submission'
CANDIDATE = '2d8b53e65f4b3c06628e191bb083ba95064f9fd51d5578c915ba424d68938a97'
ROOTS = (DIAGNOSTIC,)


def static_ready(proofs, candidate):
    if set(proofs) != set(ROOTS) or sha256(candidate.encode()).hexdigest() != CANDIDATE:
        raise ValueError('exact literal candidate and complete static proof required')
    rows = proofs[ROOTS[0]]
    plan, = of(rows, 'external.literal_anchors_planned')
    started, = of(rows, 'external.literal_anchors_started')
    done, = of(rows, 'external.literal_anchors_completed')
    summary, cases = done['summary'], done['cases']
    if (plan['baseline_sha256'] != '004a4ff9f66843206456f28d2bd08b59c09196ecee16c88a25b51dc85fa62020'
            or sha256(plan['baseline_source'].encode()).hexdigest() != plan['baseline_sha256']
            or summary['identities'] != 19 or summary['all_original_packs_reproduced'] is not True
            or summary['source_vault_opened'] is not False or summary['models_repeated'] != 0
            or summary['private_grades_repeated'] != 0 or len(cases) != 19
            or len({r['identity'] for r in cases}) != 19
            or any(r['original_pack_reproduced'] is not True or len(r['candidate_pack'].encode()) > 4096 for r in cases)
            or started['candidate_source'] != candidate or started['candidate_sha256'] != CANDIDATE):
        raise ValueError('complete bounded source-bound no-inference literal replay required')
    return True


def build_driver(original):
    source = original
    changes = {
        'RUN = '+repr(previous.RUN): 'RUN = '+repr(RUN),
        'CANDIDATE = '+repr(previous.CANDIDATE): 'CANDIDATE = '+repr(CANDIDATE),
    }
    for before, after in changes.items():
        if source.count(before) != 1:
            raise ValueError('exact exercised build profile required')
        source = source.replace(before, after)
    tree = ast.parse(source)
    roots = next(n for n in tree.body if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == 'ROOTS' for t in n.targets))
    old_gate = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'static_ready')
    source = source.replace(ast.get_source_segment(source, roots), 'ROOTS = '+repr(ROOTS), 1)
    source = source.replace(ast.get_source_segment(original, old_gate), inspect.getsource(static_ready).rstrip(), 1)
    marker = "print(json.dumps({'query_nomination_import':True}))"
    if source.count(marker) != 1:
        raise ValueError('exact ordinary-user query probe required')
    source = source.replace(marker, '''from atmem.knowledge.code.packing import _query_literal_targets
assert _query_literal_targets('`style-mode`',{'a.py':['def callback(v):','    return v','TABLE = {"style-mode": callback}']},{('a.py',1,'callback')})=={('a.py',1,'callback'):8000}
print(json.dumps({'query_nomination_import':True,'literal_anchor_import':True}))''', 1)
    ast.parse(source, feature_version=(3, 10))
    return source


def main():
    from benchmarks.code_replay.windows_transport import framed_command, framed_input
    from benchmarks.code_replay.corrective_transfer_recovery import ssh_options
    os.environ['ATMEM_BENCHMARK_PER_RUN_VAULTS'] = '1'
    vault, principal = evidence(SUBMIT)
    if vault.inspect(principal, SUBMIT):
        raise ValueError('literal preview already submitted; inspect original handle')
    candidate = Path('atmem/knowledge/code/packing.py').read_text()
    proofs = {root: vault.inspect(principal, root) for root in ROOTS}
    static_ready(proofs, candidate)
    driver = build_driver(inspect.getsource(previous))
    namespace = {'__name__': 'literal_build_preflight'}
    exec(compile(driver, '<literal-build-preflight>', 'exec'), namespace)
    namespace['static_ready'](proofs, candidate)
    payload = {'driver_source': driver, 'candidate_source': candidate,
               'static_proofs': proofs, 'builder_source': Path('benchmarks/code_replay/corrective_build.py').read_text(),
               'protocol': Path('specs/042-atmem-code/literal-anchor-preview-v1.md').read_text()}
    setup = '''import os,sys,json
job=json.load(sys.stdin)
os.environ.update(ATMEM_BENCHMARK_ROOT='/home/jt/atmem-benchmark-runtime-20261018/bookkeeping-v1',ATMEM_BENCHMARK_PER_RUN_VAULTS='1',ATMEM_BENCHMARK_LOCAL_WSL='1',PYTHONDONTWRITEBYTECODE='1')
sys.path[:0]=['/home/jt/atmem-benchmark-runtime-20261018/operator-source-v13','/home/jt/atmem-benchmark-runtime-20261018/operator-deps-v1']
os.chdir('/home/jt/atmem-benchmark-runtime-20261018/operator-source-v13')
exec(compile(job['driver_source'],'<literal-anchor-preview>','exec'))
'''
    request = {'program': "import subprocess,sys,json;p=subprocess.run([job['python'],'-I','-u','-c',job['setup']],input=json.dumps(job['payload']).encode());sys.exit(p.returncode)",
               'python': '/home/jt/atmem-benchmark-runtime-20261018/product-build-arw_zz8r/venv/bin/python',
               'setup': setup, 'payload': payload}
    def save(kind, value):
        return vault.capture(run_id=SUBMIT, kind=kind, principal=principal, payload=value)
    save('external.literal_anchor_build_submission_planned', {
        **payload, 'setup': setup, 'profile_adapter_source': Path(__file__).read_text(),
        'remote_run': RUN, 'model_calls': 0, 'owner_install_changed': False})
    result = subprocess.run(ssh_options()+['user@192.168.0.87', framed_command()[-1]],
                            input=framed_input(request), capture_output=True)
    save('external.literal_anchor_build_submission_result', {
        'exit_code': result.returncode, 'stdout_base64': base64.b64encode(result.stdout).decode(),
        'stderr_base64': base64.b64encode(result.stderr).decode()})
    print(result.stdout.decode(), end='', flush=True)
    if result.returncode:
        raise RuntimeError('preview transport failed; inspect original remote state, no automatic restart')


if __name__ == '__main__':
    main()
