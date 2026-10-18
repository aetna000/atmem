"""Explicit fresh qualification profiles over the exercised CD2 controls."""
import ast
import base64
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys

from benchmarks.code_replay import query_nomination_qualification as qualification
from benchmarks.code_replay import query_nomination_installed_replay as replay
from benchmarks.code_replay import literal_anchor_preview as preview
from benchmarks.code_replay.query_nomination_preview import evidence, of

QUALIFY = 'external-windows-literal-anchor-qualification-v1-20261018'
REPLAY = 'external-windows-literal-anchor-installed-replay-v1-20261018'
ROOT = '/home/jt/atmem-benchmark-runtime-20261018/literal-anchor-qualification-v1/'
WHEEL = '3b56928a20c07fdbddcca64167ad19efdb80db396e41637d5e837b9e9958ad65'
PYTHON = '/home/jt/atmem-benchmark-runtime-20261018/product-build-ajmlwpno/venv/bin/python'
LOCK = 'external-windows-query-nomination-development-execution-lock-v1-20261018'


def qualification_source(original):
    source = qualification.driver_source(original)
    for old, new, count in (
        ('RUN='+repr(qualification.RUN), 'RUN='+repr(QUALIFY), 1),
        (repr(qualification.BUILD), repr(preview.RUN), 1),
        (repr(qualification.ROOT), repr(ROOT), 1),
        (repr(qualification.WHEEL), repr(WHEEL), 1),
        (repr(qualification.CANDIDATE), repr(preview.CANDIDATE), 2),
    ):
        if source.count(old) != count:
            raise ValueError('exact exercised installed qualification required: '+old)
        source = source.replace(old, new)
    ast.parse(source, feature_version=(3, 10))
    return source


def replay_source():
    source = inspect.getsource(replay.worker)
    for old, new in (
        ("static_root = 'external-windows-corrective-development-source-location-diagnostic-v1-20261018'",
         'static_root = '+repr(preview.DIAGNOSTIC)),
        ("'external.nomination_diagnostic_completed'", "'external.literal_anchors_completed'"),
    ):
        if source.count(old) != 1:
            raise ValueError('exact installed nineteen-pack worker required')
        source = source.replace(old, new)
    ast.parse(source, feature_version=(3, 10))
    return source+'\nworker()\n'


def verified_build(rows):
    result, = of(rows, 'external.literal_anchor_build_submission_result')
    if result['exit_code'] != 0:
        raise ValueError('terminal successful preview submission required')
    proof = json.loads(base64.b64decode(result['stdout_base64'], validate=True))
    ordinary = json.loads(base64.b64decode(proof['ordinary_stdout_base64'], validate=True))
    if (proof['qualified'] is not True or proof['wheel_sha256'] != WHEEL or proof['python'] != PYTHON
            or proof['candidate_packing_sha256'] != preview.CANDIDATE
            or proof['dependencies_equal'] is not True or proof['ordinary_user_exit'] != 0
            or ordinary.get('literal_anchor_import') is not True):
        raise ValueError('exact source-qualified installed literal preview required')
    return proof


def main():
    from benchmarks.code_replay.windows_transport import framed_command, framed_input
    from benchmarks.code_replay.corrective_transfer_recovery import ssh_options
    from benchmarks.code_replay.windows_execute import runner_helpers
    from benchmarks.code_replay.corrective_qualification import configuration_source
    from benchmarks.code_replay.packing_replay_audit import retained_generation
    if sys.argv[1:] not in (['qualify'], ['replay']):
        raise ValueError('select qualify or replay; no model phase exists')
    mode = sys.argv[1]; run = QUALIFY if mode == 'qualify' else REPLAY
    submit = run+'-submission'
    os.environ['ATMEM_BENCHMARK_PER_RUN_VAULTS'] = '1'
    vault, principal = evidence(submit)
    if vault.inspect(principal, submit):
        raise ValueError('control already submitted; inspect original handle')
    proof = verified_build(vault.inspect(principal, preview.SUBMIT))
    if mode == 'qualify':
        payload = {'driver_source': qualification_source(Path('benchmarks/code_replay/compatibility_qualification.py').read_text()),
                   'configuration_source': configuration_source(runner_helpers()[1])}
        setup = '''import os,sys,json
job=json.load(sys.stdin)
os.environ.update(ATMEM_BENCHMARK_ROOT='/home/jt/atmem-benchmark-runtime-20261018/bookkeeping-v1',ATMEM_BENCHMARK_PER_RUN_VAULTS='1',ATMEM_BENCHMARK_LOCAL_WSL='1',PYTHONDONTWRITEBYTECODE='1')
sys.path[:0]=['/home/jt/atmem-benchmark-runtime-20261018/operator-source-v13','/home/jt/atmem-benchmark-runtime-20261018/operator-deps-v1']
os.chdir('/home/jt/atmem-benchmark-runtime-20261018/operator-source-v13')
exec(compile(job['driver_source'],'<literal-real-source-controls>','exec'))
'''
        python = '/home/jt/atmem-benchmark-runtime-20261018/product-build-arw_zz8r/venv/bin/python'
    else:
        payload = {'program': replay_source(), 'generation_helper': inspect.getsource(retained_generation),
                   'run': REPLAY, 'build': preview.RUN, 'lock': LOCK, 'candidate': preview.CANDIDATE, 'wheel': WHEEL}
        setup = "import json,sys;job=json.load(sys.stdin);exec(compile(job['program'],'<literal-installed-replay>','exec'))"
        python = PYTHON
    request = {'program': "import subprocess,sys,json;p=subprocess.run([job['python'],'-I','-u','-c',job['setup']],input=json.dumps(job['payload']).encode());sys.exit(p.returncode)",
               'python': python, 'setup': setup, 'payload': payload}
    def save(kind, value):
        return vault.capture(run_id=submit, kind=kind, principal=principal, payload=value)
    save('external.literal_anchor_control_submission_planned', {
        'request': request, 'driver_source': Path(__file__).read_text(), 'build_proof': proof,
        'mode': mode, 'remote_run': run, 'model_calls': 0, 'owner_install_changed': False})
    result = subprocess.run(ssh_options()+['user@192.168.0.87', framed_command()[-1]],
                            input=framed_input(request), capture_output=True)
    save('external.literal_anchor_control_submission_result', {
        'exit_code': result.returncode, 'stdout_base64': base64.b64encode(result.stdout).decode(),
        'stderr_base64': base64.b64encode(result.stderr).decode()})
    print(result.stdout.decode(), end='', flush=True)
    if result.returncode:
        raise RuntimeError('control observation failed; inspect original remote state, no automatic restart')


if __name__ == '__main__':
    main()
