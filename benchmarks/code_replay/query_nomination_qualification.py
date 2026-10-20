"""Fresh installed-source controls for the frozen query-nomination preview."""
import ast
import base64
import json
from pathlib import Path
import subprocess

from benchmarks.code_replay import corrective_qualification as previous
from benchmarks.code_replay.query_nomination_preview import CANDIDATE, RUN as BUILD, evidence

RUN = 'external-windows-query-nomination-qualification-v1-20261018'
SUBMIT = RUN + '-submission'
ROOT = '/home/jt/atmem-benchmark-runtime-20261018/query-nomination-qualification-v1/'
WHEEL = 'c3e6bb211082b6f962869ed4a60945cb3c90d99c784ce7629d423045b8190326'


def driver_source(original):
    """Reuse fresh controls, not previous failure-specific continuations."""
    source = previous.qualification_source(original)
    changes = {
        'RUN=' + repr(previous.RUN): 'RUN=' + repr(RUN),
        repr(previous.BUILD) + ",'external.corrective_build_completed'":
            repr(BUILD) + ",'external.query_nomination_build_completed'",
        repr(previous.ROOT): repr(ROOT),
        "if build['qualified'] is not True:raise ValueError('installed compatibility preview required')":
            "if build['qualified'] is not True or build['wheel_sha256']!=" + repr(WHEEL)
            + " or build['candidate_packing_sha256']!=" + repr(CANDIDATE)
            + ":raise ValueError('exact installed query-nomination preview required')",
        "import os,json,base64,hashlib,subprocess,zlib,shutil\n":
            "import os,json,base64,hashlib,subprocess,zlib,shutil\n"
            "import atmem.knowledge.code.packing as installed_packing\n"
            "import sys\n"
            "from pathlib import Path\n"
            "if not Path(installed_packing.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()):raise ValueError('installed package required')\n"
            "if hashlib.sha256(Path(installed_packing.__file__).read_bytes()).hexdigest()!="
            + repr(CANDIDATE) + ":raise ValueError('installed packer differs')\n",
    }
    for before, after in changes.items():
        if source.count(before) != 1:
            raise ValueError('exact fresh qualification prerequisite differs: ' + before)
        source = source.replace(before, after)
    marker = "'worker_source':PROGRAM,"
    if source.count(marker) != 2:
        raise ValueError('both full worker boundaries required')
    source = source.replace(marker, marker + "'configuration_source':job['configuration_source'],")
    # The controller's legacy main returns zero even after a failed case.
    # Preserve every case and terminal evidence, then fail the transport honestly.
    terminal = "'qualified':len(results)==5 and all(r['qualified'] for r in results),'scored_confirmation':False})"
    if source.count(terminal) != 1:
        raise ValueError('exact all-five terminal boundary required')
    source = source.replace(terminal, terminal + "\n    if not all(r['qualified'] for r in results):raise ValueError('fresh installed controls failed; inspect retained cases')")
    ast.parse(source, feature_version=(3, 10))
    return source


def main():
    import os
    from benchmarks.code_replay.windows_execute import runner_helpers
    from benchmarks.code_replay.windows_transport import framed_command, framed_input
    from benchmarks.code_replay.corrective_transfer_recovery import ssh_options
    os.environ['ATMEM_BENCHMARK_PER_RUN_VAULTS'] = '1'
    vault, principal = evidence(SUBMIT)
    if vault.inspect(principal, SUBMIT):
        raise ValueError('qualification submission already attempted; inspect original state')
    driver = driver_source(Path('benchmarks/code_replay/compatibility_qualification.py').read_text())
    payload = {'driver_source': driver,
               'configuration_source': previous.configuration_source(runner_helpers()[1])}
    setup = '''import os,sys,json
job=json.load(sys.stdin)
os.environ.update(ATMEM_BENCHMARK_ROOT='/home/jt/atmem-benchmark-runtime-20261018/bookkeeping-v1',ATMEM_BENCHMARK_PER_RUN_VAULTS='1',ATMEM_BENCHMARK_LOCAL_WSL='1',PYTHONDONTWRITEBYTECODE='1')
sys.path[:0]=['/home/jt/atmem-benchmark-runtime-20261018/operator-source-v13','/home/jt/atmem-benchmark-runtime-20261018/operator-deps-v1']
os.chdir('/home/jt/atmem-benchmark-runtime-20261018/operator-source-v13')
exec(compile(job['driver_source'],'<query-nomination-real-source-controls>','exec'))
'''
    request = {'program': "import subprocess,sys,json;p=subprocess.run([job['python'],'-I','-u','-c',job['setup']],input=json.dumps(job['payload']).encode());sys.exit(p.returncode)",
               'python': '/home/jt/atmem-benchmark-runtime-20261018/product-build-arw_zz8r/venv/bin/python',
               'setup': setup, 'payload': payload}
    def save(kind, value):
        return vault.capture(run_id=SUBMIT, kind=kind, principal=principal, payload=value)
    save('external.query_nomination_qualification_submission_planned', {
        **payload, 'setup': setup, 'controller_source': Path(__file__).read_text(),
        'remote_run': RUN, 'model_calls': 0, 'owner_install_changed': False})
    result = subprocess.run(ssh_options() + ['user@192.168.0.87', framed_command()[-1]],
                            input=framed_input(request), capture_output=True)
    save('external.query_nomination_qualification_submission_result', {
        'exit_code': result.returncode, 'stdout_base64': base64.b64encode(result.stdout).decode(),
        'stderr_base64': base64.b64encode(result.stderr).decode()})
    print(result.stdout.decode(), end='', flush=True)
    if result.returncode:
        raise RuntimeError('qualification transport failed; inspect retained remote state, no automatic restart')


if __name__ == '__main__':
    main()
