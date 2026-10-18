"""Fresh unchanged/candidate public-test control for the original nested root."""
import base64
import inspect
import json
import os
from pathlib import Path
import subprocess

from benchmarks.code_replay.literal_anchor_screen import PREFIX, readiness_worker, replace_once
from benchmarks.code_replay.query_nomination_preview import evidence, of

RUN = PREFIX+'public-selector-runtime-v1-20261018'


def worker_source():
    from benchmarks.code_replay.query_nomination_screen import sources
    namespace = {'__name__': 'public_readiness_definition'}
    exec(compile(sources()['readiness'], '<original-public-readiness>', 'exec'), namespace)
    source = readiness_worker(namespace['worker_program']())
    source = replace_once(source, "qualification=operator/'qualification-public'",
                          "qualification=operator/'qualification-public-selector-baseline'")
    source = replace_once(source, 'started=time.monotonic()\nprocess=subprocess.run',
        "requests.insert(2,{'jsonrpc':'2.0','id':'qualification-baseline','method':'tools/call','params':{\n"
        " 'name':'run_public_tests','arguments':{'patch':'','paths':['xarray/tests/test_options.py']}}})\n"
        'started=time.monotonic()\nprocess=subprocess.run')
    marker = "result['qualified']=bool(result['selector_denials_qualified'] and public_ok and result.get('code_qualified',True)"
    return replace_once(source, marker,
        "baseline=next(r for r in result['public_responses'] if r.get('id')=='qualification-baseline')\n"
        "try:baseline_answer=json.loads(baseline['result']['content'][0]['text'])\n"
        "except (KeyError,ValueError,IndexError):baseline_answer={}\n"
        "result['unchanged_public_result']=baseline_answer\n"
        "result['unchanged_public_qualified']=baseline_answer.get('status')=='executed' and baseline_answer.get('test_exit_code')==0\n"
        "result['qualified']=bool(result['unchanged_public_qualified'] and result['selector_denials_qualified'] and public_ok and result.get('code_qualified',True)")


def remote():
    import base64
    import json
    import subprocess
    from benchmarks.code_replay.windows_confirmation_exports import recover_export
    from benchmarks.code_replay.windows_transport import framed_command, framed_input
    vault, principal = evidence(job['run'])
    if vault.inspect(principal, job['run']):
        raise ValueError('runtime control already attempted; inspect original state')
    rows = vault.inspect(principal, job['staging'])
    manifest, = of(rows, 'external.confirmation_v3_manifest_frozen')
    end, = of(rows, 'external.confirmation_v3_staging_completed')
    if end['all_38_cases_staged'] is not True:
        raise ValueError('complete fresh staging required')
    block, = [r for r in of(rows, 'external.confirmation_v3_block_result')
              if r['block']['instance_id'] == 'pydata__xarray-3812']
    plan, = of(vault.inspect(principal, block['task_run']), 'external.confirmation_v3_stage_planned')
    source = recover_export(vault.inspect(principal, manifest['source_descriptors']['pydata__xarray-3812']['export_run']),
                            manifest['source_descriptors']['pydata__xarray-3812'])
    if 'xarray/tests/test_options.py' not in source['files_base64']:
        raise ValueError('exact original public nested test must exist')
    payload = {**job['payload'], 'case': block['cases']['native'], 'python': manifest['product_python'],
        'source': {k: source[k] for k in ('base_commit', 'files_base64', 'modes')},
        'image': manifest['images']['pydata__xarray-3812'], 'server_template': plan['server_template'],
        'public_worker_source': plan['public_worker_source'],
        'source_probe': next(n for n in sorted(source['files_base64']) if n.startswith('xarray/') and n.endswith('.py'))}
    def save(kind, value):
        return vault.capture(run_id=job['run'], kind=kind, principal=principal, payload=value)
    save('external.public_selector_runtime_planned', {'job': job, 'payload': payload, 'model_calls': 0,
        'unchanged_selector': 'xarray/tests/test_options.py', 'candidate': 'three public isolation canaries'})
    request = {'program': "import subprocess,sys,json;p=subprocess.run([job['python'],'-I','-c',\"import json,sys;job=json.load(sys.stdin);exec(job['program'])\"],input=json.dumps(job['payload']).encode());sys.exit(p.returncode)",
               'python': manifest['product_python'], 'payload': payload}
    result = subprocess.run(framed_command(), input=framed_input(request), capture_output=True, timeout=360)
    save('external.public_selector_runtime_result', {'exit_code': result.returncode,
        'stdout_base64': base64.b64encode(result.stdout).decode(), 'stderr_base64': base64.b64encode(result.stderr).decode()})
    value = json.loads(result.stdout) if result.returncode == 0 else {}
    qualified = value.get('qualified') is True
    save('external.public_selector_runtime_completed', {'qualified': qualified, 'result': value, 'model_calls': 0})
    print(json.dumps({'qualified': qualified, 'model_calls': 0,
                      'unchanged_public_result': value.get('unchanged_public_result'),
                      'candidate_public_result': value.get('public_result')}), flush=True)
    if not qualified:
        raise ValueError('public runtime control failed; retain full outcome, no automatic retry')


def main():
    from benchmarks.code_replay.windows_transport import framed_command, framed_input
    from benchmarks.code_replay.corrective_transfer_recovery import ssh_options
    from benchmarks.code_replay.confirmation_bridge_readiness import probe_patch
    os.environ['ATMEM_BENCHMARK_PER_RUN_VAULTS'] = '1'
    submit = RUN+'-submission';vault, principal = evidence(submit)
    if vault.inspect(principal, submit):
        raise ValueError('runtime control already submitted; inspect original handle')
    probe = 'tests/test_atmem_public_boundary_20261018.py'
    nested = 'xarray/tests/test_atmem_public_boundary_20261018.py'
    payload = {'program': inspect.getsource(evidence)+'\n'+inspect.getsource(of)+'\n'+inspect.getsource(remote)+'\nremote()\n', 'run': RUN,
        'staging': PREFIX+'staging-v1-20261018', 'payload': {'program': worker_source(),
        'probe_patch': probe_patch('xarray').replace(probe, nested), 'probe_paths': [nested],
        'placeholder': '/dev/shm/ATMEM_CONFIRMATION_PRESET_PLACEHOLDER'}}
    setup = "import os,sys,json\njob=json.load(sys.stdin)\nos.environ.update(ATMEM_BENCHMARK_ROOT='/home/jt/atmem-benchmark-runtime-20261018/bookkeeping-v1',ATMEM_BENCHMARK_PER_RUN_VAULTS='1',ATMEM_BENCHMARK_LOCAL_WSL='1',PYTHONDONTWRITEBYTECODE='1')\nsys.path[:0]=['/home/jt/atmem-benchmark-runtime-20261018/operator-source-v13','/home/jt/atmem-benchmark-runtime-20261018/operator-deps-v1']\nexec(compile(job['program'],'<selector-runtime-control>','exec'))\n"
    request = {'program': "import subprocess,sys,json;p=subprocess.run([job['python'],'-I','-u','-c',job['setup']],input=json.dumps(job['payload']).encode());sys.exit(p.returncode)",
        'python': '/home/jt/atmem-benchmark-runtime-20261018/product-build-arw_zz8r/venv/bin/python', 'setup': setup, 'payload': payload}
    vault.capture(run_id=submit, kind='external.public_selector_runtime_submission_planned', principal=principal,
                  payload={'request': request, 'driver_source': Path(__file__).read_text(), 'model_calls': 0})
    result = subprocess.run(ssh_options()+['user@192.168.0.87', framed_command()[-1]],
                            input=framed_input(request), capture_output=True)
    vault.capture(run_id=submit, kind='external.public_selector_runtime_submission_result', principal=principal,
        payload={'exit_code': result.returncode, 'stdout_base64': base64.b64encode(result.stdout).decode(),
                 'stderr_base64': base64.b64encode(result.stderr).decode()})
    print(result.stdout.decode(), end='', flush=True)
    if result.returncode:
        raise RuntimeError('runtime control observation failed; inspect original state')


if __name__ == '__main__':
    main()
