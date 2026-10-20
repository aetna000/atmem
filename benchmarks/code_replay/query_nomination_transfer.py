"""Copy only CD2 benchmark exports to MEM and recover without live-vault access."""
import base64
import inspect
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

from benchmarks.code_replay.query_nomination_preview import evidence
from benchmarks.code_replay.query_nomination_screen import PREFIX
from benchmarks.code_replay.query_nomination_archive_waiter import REMOTE, OUTPUT as REMOTE_OUTPUT, KEYS as REMOTE_KEYS

RUN = PREFIX+'MEM-transfer-v1-20261018'
OUTPUT = '/Volumes/MEM/AtMem-Code-Replay-20261017/query-nomination-development-protected-20261018'
KEYS = '/Users/javadtaghia/Library/Application Support/AtMem Benchmarks/click-20261017/keys-query-nomination-development-archive-20261018'


def copy_command(source, destination):
    from benchmarks.code_replay.corrective_transfer_recovery import ssh_options
    allowed = {REMOTE_OUTPUT+'/': OUTPUT, REMOTE_KEYS+'/': KEYS}
    if source not in allowed or str(destination) != allowed[source]:
        raise ValueError('only exact benchmark exports and separate internal keys may be copied')
    return ['rsync', '-a', '--rsync-path=wsl -d Ubuntu -u root -- rsync', '-e', shlex.join(ssh_options()),
            'user@192.168.0.87:'+source, str(destination)+'/']


def export_ready(value, expected_archive, expected_helpers):
    plan, = value['plans']; end, = value['terminal']
    if (plan['driver_source'] != expected_archive or value['helpers'] != expected_helpers
            or plan['output'] != REMOTE_OUTPUT or plan['internal_key_root'] != REMOTE_KEYS
            or len(set(plan['runs'])) != len(plan['runs']) or len(plan['runs']) != end['runs']):
        raise ValueError('exact complete export, recorded helper sources and paths required')
    return end['runs']


def recovery_program(archive, helpers, audit):
    sources = {**helpers, 'benchmarks.code_replay.confirmation_v3_archive': archive}
    return '''import json,sys,types
from pathlib import Path
from benchmarks.code_replay import run_evidence
def forbidden(*args,**kwargs):raise RuntimeError('live evidence forbidden in standalone recovery')
run_evidence.operational_evidence=forbidden
sources='''+repr(sources)+'''
for name,source in sources.items():
 module=types.ModuleType(name);sys.modules[name]=module
 exec(compile(source,'<retained-CD2-archive-helper>','exec'),module.__dict__)
archive=sys.modules['benchmarks.code_replay.confirmation_v3_archive']
proof=archive.recover_collection(Path('''+repr(OUTPUT)+'''),Path('''+repr(KEYS)+'''))
audit={}
exec(compile('''+repr(audit)+''','<retained-CD2-original-request-audit>','exec'),audit)
proof['request_audit']=audit['audit_collection'](Path('''+repr(OUTPUT)+'''),Path('''+repr(KEYS)+'''))
if (proof['candidates'],proof['private_grades'],proof['public_vaults'])!=(38,38,38):raise ValueError('all original CD2 cells required')
if proof['request_audit']['verified_original_requests']!=38:raise ValueError('all original CD2 requests required')
print(json.dumps(proof),flush=True)
'''


def main():
    from benchmarks.code_replay.windows_transport import framed_command, framed_input
    from benchmarks.code_replay.corrective_transfer_recovery import ssh_options
    from benchmarks.code_replay import confirmation_v3_archive, confirmation_v3_dispatch_audit
    from benchmarks.code_replay import query_nomination_archive, corrective_archive
    from benchmarks.code_replay.query_nomination_preparation import SUBMIT as PREPARATION_SUBMIT
    os.environ['ATMEM_BENCHMARK_PER_RUN_VAULTS'] = '1'
    vault, principal = evidence(RUN)
    if vault.inspect(principal, RUN):
        raise ValueError('transfer already attempted; inspect retained state, never overwrite')
    output, keys = Path(OUTPUT), Path(KEYS)
    if (not Path('/Volumes/MEM').is_mount() or output.exists() or keys.exists()
            or output.parent.is_symlink() or keys.parent.is_symlink()):
        raise ValueError('mounted MEM and fresh exact destinations required')
    plan, = [r['envelope']['payload'] for r in vault.inspect(principal, PREPARATION_SUBMIT)
             if r['envelope']['event_type'] == 'external.query_nomination_preparation_submission_planned']
    retained = plan['request']['payload']['sources']
    helpers = {'benchmarks.code_replay.confirmation_v3_'+name: retained[name] for name in ('grade', 'report', 'retain')}
    archive = query_nomination_archive.archive_source(inspect.getsource(confirmation_v3_archive))
    audit = corrective_archive.request_audit_source(inspect.getsource(confirmation_v3_dispatch_audit))
    program = recovery_program(archive, helpers, audit)
    def save(kind, payload):
        return vault.capture(run_id=RUN, kind=kind, principal=principal, payload=payload)
    save('external.query_nomination_MEM_transfer_planned', {
        'driver_source': Path(__file__).read_text(), 'standalone_recovery_program': program,
        'archive_source': archive, 'helper_sources': helpers, 'archive_destination': OUTPUT,
        'internal_key_destination': KEYS, 'models_repeated': 0, 'private_grades_repeated': 0})
    probe = '''import os,sys,json
os.environ.update(ATMEM_BENCHMARK_ROOT='/home/jt/atmem-benchmark-runtime-20261018/bookkeeping-v1',ATMEM_BENCHMARK_PER_RUN_VAULTS='1',ATMEM_BENCHMARK_LOCAL_WSL='1')
sys.path[:0]=['/home/jt/atmem-benchmark-runtime-20261018/operator-source-v13','/home/jt/atmem-benchmark-runtime-20261018/operator-deps-v1']
'''+inspect.getsource(evidence)+'''
v,p=evidence('''+repr(PREFIX+'archive-v1-20261018')+''')
rows=v.inspect(p,'''+repr(PREFIX+'archive-v1-20261018')+''')
def of(rows,kind):return [r['envelope']['payload'] for r in rows if r['envelope']['event_type']==kind]
post,=of(v.inspect(p,'''+repr(PREFIX+'postprocessing-v1-20261018')+'''),'external.v3_postprocessing_planned')
print(json.dumps({'plans':of(rows,'external.v3_archive_planned'),'terminal':of(rows,'external.v3_archive_export_completed'),'helpers':post['postprocess_programs']}),flush=True)
'''
    request = {'program': "import subprocess,sys;p=subprocess.run([job['python'],'-I','-c',job['probe']]);sys.exit(p.returncode)",
               'python': REMOTE+'/product-build-arw_zz8r/venv/bin/python', 'probe': probe}
    result = subprocess.run(ssh_options()+['user@192.168.0.87', framed_command()[-1]],
                            input=framed_input(request), capture_output=True, timeout=90)
    save('external.query_nomination_MEM_probe_result', {
        'exit_code': result.returncode, 'stdout_base64': base64.b64encode(result.stdout).decode(),
        'stderr_base64': base64.b64encode(result.stderr).decode()})
    if result.returncode:
        raise RuntimeError('export observation failed; no copy or restart')
    expected_runs = export_ready(json.loads(result.stdout), archive, helpers)
    output.mkdir(mode=0o700); keys.mkdir(mode=0o700)
    for source, destination in [(REMOTE_OUTPUT+'/', output), (REMOTE_KEYS+'/', keys)]:
        command = copy_command(source, destination)
        save('external.query_nomination_MEM_copy_started', {'command': command})
        result = subprocess.run(command, capture_output=True, timeout=3600)
        save('external.query_nomination_MEM_copy_result', {
            'destination': str(destination), 'exit_code': result.returncode,
            'stdout_base64': base64.b64encode(result.stdout).decode(),
            'stderr_base64': base64.b64encode(result.stderr).decode()})
        if result.returncode:
            raise RuntimeError('partial copy preserved; no overwrite or automatic retry')
    loader = "import json,sys;exec(compile(json.load(sys.stdin)['program'],'<retained-stdin-archive-reader>','exec'))"
    save('external.query_nomination_MEM_recovery_started', {'program': program, 'source_vault_access': False})
    result = subprocess.run([sys.executable, '-c', loader], input=json.dumps({'program': program}).encode(),
                            capture_output=True, timeout=3600)
    save('external.query_nomination_MEM_recovery_result', {
        'exit_code': result.returncode, 'stdout_base64': base64.b64encode(result.stdout).decode(),
        'stderr_base64': base64.b64encode(result.stderr).decode()})
    if result.returncode:
        raise RuntimeError('standalone recovery failed; original evidence preserved')
    proof = json.loads(result.stdout)
    if proof['source_vault_opened'] is not False or proof['runs'] != expected_runs:
        raise ValueError('exact complete archive-only recovery required')
    save('external.query_nomination_MEM_recovery_completed', {
        'proof': proof, 'archive': OUTPUT, 'internal_keys': KEYS, 'goal_complete': False})
    print(json.dumps(proof), flush=True)


if __name__ == '__main__':
    main()
