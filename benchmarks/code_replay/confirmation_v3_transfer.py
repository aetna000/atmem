"""Copy completed encrypted benchmark archives to MEM; recover on the separate Mac."""
import base64
import json
from pathlib import Path
import subprocess
import sys
import time

RUN = 'external-windows-confirmation-v3-MEM-transfer-v1-20261018'
REMOTE = '/home/jt/atmem-benchmark-runtime-20261018'
OUTPUT = Path('/Volumes/MEM/AtMem-Code-Replay-20261017/windows-confirmation-v3-protected-20261018')
KEYS = Path('/Users/javadtaghia/Library/Application Support/AtMem Benchmarks/click-20261017/keys-confirmation-v3-archive-20261018')

PROBE = r'''
import os,sys,json
os.environ.update(ATMEM_BENCHMARK_ROOT='/home/jt/atmem-benchmark-runtime-20261018/bookkeeping-v1',ATMEM_BENCHMARK_PER_RUN_VAULTS='1',PYTHONDONTWRITEBYTECODE='1')
sys.path[:0]=['/home/jt/atmem-benchmark-runtime-20261018/operator-source-v13','/home/jt/atmem-benchmark-runtime-20261018/operator-deps-v1']
from atmem.evidence import EvidenceScope,EvidencePrincipal,EvidenceRole
from benchmarks.code_replay.run_evidence import operational_evidence
from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
s=EvidenceScope('benchmark','local-operator','click-20261017');p=EvidencePrincipal('local-benchmark-operator',EvidenceRole.ADMINISTRATOR,s)
r='external-windows-confirmation-v3-archive-v1-20261018'
v=operational_evidence(EVIDENCE_ROOT,vault_id='confirmation-v1',scope=s,writing_run=r)
es=v.inspect(p,r)
done=[e['envelope']['payload'] for e in es if e['envelope']['event_type']=='external.v3_archive_export_completed']
model=v.inspect(p,'external-windows-confirmation-v3-models-v1-20261018')
print(json.dumps({'archive_terminals':done,'models_stopped':any(e['envelope']['event_type']=='external.v3_models_stopped' for e in model)}))
'''


def ready(value):
    if value['models_stopped'] or len(value['archive_terminals']) > 1:
        raise ValueError('stopped or ambiguous cohort; never restart it from transfer')
    return len(value['archive_terminals']) == 1


def transfer_command(remote_path, destination):
    if remote_path not in (REMOTE + '/confirmation-archive-v3/', REMOTE + '/confirmation-archive-keys-v3/'):
        raise ValueError('only the two exact benchmark archive paths may be copied')
    expected = OUTPUT if remote_path.endswith('/confirmation-archive-v3/') else KEYS
    if Path(destination) != expected:
        raise ValueError('encrypted archives go to MEM; keys remain at the exact internal destination')
    return ['rsync', '-a', '--rsync-path=wsl -d Ubuntu -u root -- rsync',
            '-e', 'ssh -S /private/tmp/atmem-click-windows-20261018.sock -o BatchMode=yes',
            'user@192.168.0.87:' + remote_path, str(destination) + '/']


def main():
    import os
    if Path(__file__).read_text() != job['driver_source']:
        raise ValueError('transfer implementation changed since scheduling')
    os.environ['ATMEM_BENCHMARK_PER_RUN_VAULTS'] = '1'
    from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
    from benchmarks.code_replay.run_evidence import operational_evidence
    from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
    from benchmarks.code_replay.windows_transport import framed_command, framed_input
    scope = EvidenceScope('benchmark', 'local-operator', 'click-20261017')
    principal = EvidencePrincipal('local-benchmark-operator', EvidenceRole.ADMINISTRATOR, scope)
    vault = operational_evidence(EVIDENCE_ROOT, vault_id='confirmation-v1', scope=scope, writing_run=RUN)
    if vault.inspect(principal, RUN): raise ValueError('transfer already attempted; inspect its handle')
    if OUTPUT.exists() or KEYS.exists(): raise ValueError('new archive/key destinations required; no overwrite')
    def save(kind, payload): return vault.capture(run_id=RUN, kind=kind, principal=principal, payload=payload)
    save('external.v3_MEM_transfer_planned', {'driver_source': job['driver_source'],
        'archive_destination': str(OUTPUT), 'internal_key_destination': str(KEYS),
        'models_repeated': 0, 'source_vault_access_during_recovery': False})
    wrapper = "import subprocess,sys;p=subprocess.run([job['python'],'-I','-c',job['probe']]);sys.exit(p.returncode)"
    request = {'program': wrapper, 'python': REMOTE+'/product-build-arw_zz8r/venv/bin/python', 'probe': PROBE}
    while True:
        proc = subprocess.run(framed_command(), input=framed_input(request), capture_output=True, timeout=90)
        if proc.returncode:
            save('external.v3_MEM_remote_probe_failed', {'exit_code': proc.returncode,
                'stdout_base64': base64.b64encode(proc.stdout).decode(), 'stderr_base64': base64.b64encode(proc.stderr).decode()})
            raise RuntimeError('remote observation failed; no automatic model or transfer restart')
        value = json.loads(proc.stdout)
        if ready(value): break
        time.sleep(30)
    if not Path('/Volumes/MEM').is_mount(): raise ValueError('MEM must be mounted; do not write into a missing-mount directory')
    if OUTPUT.parent.is_symlink() or KEYS.parent.is_symlink(): raise ValueError('real benchmark-owned destination parents required')
    OUTPUT.mkdir(mode=0o700); KEYS.mkdir(mode=0o700)
    for source, destination in [(REMOTE+'/confirmation-archive-v3/', OUTPUT), (REMOTE+'/confirmation-archive-keys-v3/', KEYS)]:
        command = transfer_command(source, destination)
        save('external.v3_MEM_copy_started', {'command': command})
        proc = subprocess.run(command, capture_output=True, timeout=3600)
        save('external.v3_MEM_copy_result', {'destination': str(destination), 'exit_code': proc.returncode,
            'stdout_base64': base64.b64encode(proc.stdout).decode(), 'stderr_base64': base64.b64encode(proc.stderr).decode()})
        if proc.returncode: raise RuntimeError('copy failed; partial files preserved, no deletion or automatic retry')
    program = ('import json;from pathlib import Path;'
               'from benchmarks.code_replay.confirmation_v3_archive import recover_collection;'
               'print(json.dumps(recover_collection(Path('+repr(str(OUTPUT))+'),Path('+repr(str(KEYS))+'))))')
    if Path(__file__).with_name('confirmation_v3_archive.py').read_text() != job['recovery_source']:
        raise ValueError('recovery implementation changed since scheduling; do not claim it was used')
    command = [sys.executable, '-c', program]
    save('external.v3_MEM_recovery_started', {'command': command, 'source_vault_access': False,
                                           'recovery_implementation': job['recovery_source']})
    proc = subprocess.run(command, capture_output=True, timeout=3600)
    save('external.v3_MEM_recovery_result', {'exit_code': proc.returncode,
        'stdout_base64': base64.b64encode(proc.stdout).decode(), 'stderr_base64': base64.b64encode(proc.stderr).decode()})
    if proc.returncode: raise RuntimeError('separate-host fresh-process archive recovery failed; evidence retained')
    proof = json.loads(proc.stdout)
    if (proof['source_vault_opened'] is not False
            or (proof['candidates'], proof['private_grades'], proof['public_vaults']) != (76, 76, 76)):
        raise ValueError('complete independent archive recovery not proved')
    save('external.v3_MEM_recovery_completed', {'proof': proof, 'archive': str(OUTPUT),
        'internal_keys': str(KEYS), 'final_goal_audit': 'still required'})
    print(json.dumps({'MEM_archive_recovery': proof, 'goal_complete': False}), flush=True)


if __name__ == '__main__': main()
