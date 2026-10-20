"""Resume the zero-copy SSH failure using interactive password transport.

Passwords are handled by native SSH through the terminal, never by this module.
Only benchmark archives are copied; keys remain on the internal disk.
"""
import base64
from hashlib import sha256
import inspect
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

from benchmarks.code_replay.corrective_controls import PREFIX
from benchmarks.code_replay.corrective_transfer import OUTPUT, KEYS, recovery_program
from benchmarks.code_replay.confirmation_v3_transfer import PROBE, REMOTE

RUN = PREFIX+'MEM-transfer-recovery-v1-20261018'
ORIGINAL = PREFIX+'MEM-transfer-v1-20261018'


def ssh_options():
    return ['ssh', '-T', '-o', 'ControlMaster=no', '-o', 'ControlPath=none',
        '-o', 'PubkeyAuthentication=no', '-o', 'PreferredAuthentications=password',
        '-o', 'NumberOfPasswordPrompts=1', '-o', 'StrictHostKeyChecking=yes']


def copy_command(source, destination):
    allowed = {REMOTE+'/corrective-development-archive-v1/': OUTPUT,
               REMOTE+'/corrective-development-archive-keys-v1/': KEYS}
    if source not in allowed or str(destination) != allowed[source]:
        raise ValueError('exact encrypted archive and separate internal-key destinations required')
    return ['rsync', '-a', '--rsync-path=wsl -d Ubuntu -u root -- rsync',
        '-e', shlex.join(ssh_options()), 'user@192.168.0.87:'+source, str(destination)+'/']


def terminal_proof(value, archive_source, grade_source):
    if (len(value['terminal']) != 1 or value['terminal'][0]['runs'] != 332
            or value['archive_source_sha256'] != sha256(archive_source.encode()).hexdigest()
            or value['grade_source_sha256'] != sha256(grade_source.encode()).hexdigest()):
        raise ValueError('complete original export and exact retained reader sources required')


def main():
    from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
    from benchmarks.code_replay.run_evidence import operational_evidence
    from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
    from benchmarks.code_replay.windows_transport import framed_command, framed_input
    from benchmarks.code_replay.corrective_archive import archive_source, request_audit_source
    from benchmarks.code_replay.corrective_execution import grading_source
    from benchmarks.code_replay import confirmation_v3_archive, confirmation_v3_grade, confirmation_v3_dispatch_audit
    os.environ['ATMEM_BENCHMARK_PER_RUN_VAULTS'] = '1'
    scope = EvidenceScope('benchmark', 'local-operator', 'click-20261017')
    principal = EvidencePrincipal('local-benchmark-operator', EvidenceRole.ADMINISTRATOR, scope)
    vault = operational_evidence(EVIDENCE_ROOT, vault_id='confirmation-v1', scope=scope, writing_run=RUN)
    previous = vault.inspect(principal, ORIGINAL)
    if [e['envelope']['event_type'] for e in previous] != [
            'external.v3_MEM_transfer_planned', 'external.v3_MEM_remote_probe_failed']:
        raise ValueError('exact original zero-copy transport failure required')
    if vault.inspect(principal, RUN): raise ValueError('recovery already attempted; inspect its evidence')
    output, keys = Path(OUTPUT), Path(KEYS)
    if (not Path('/Volumes/MEM').is_mount() or output.exists() or keys.exists()
            or output.parent.is_symlink() or keys.parent.is_symlink()):
        raise ValueError('mounted MEM and fresh exact destinations required; never overwrite')
    archive = archive_source(inspect.getsource(confirmation_v3_archive))
    grade = grading_source(inspect.getsource(confirmation_v3_grade))
    audit = request_audit_source(inspect.getsource(confirmation_v3_dispatch_audit))
    program = recovery_program(archive, grade, audit)
    def save(kind, payload): return vault.capture(run_id=RUN, kind=kind, principal=principal, payload=payload)
    save('external.v3_MEM_transfer_recovery_planned', {
        'driver_source': Path(__file__).read_text(), 'standalone_recovery_program': program,
        'original_failed_run': ORIGINAL, 'models_repeated': 0, 'private_grades_repeated': 0,
        'archive_destination': OUTPUT, 'internal_key_destination': KEYS})
    probe = PROBE[:PROBE.index('es=v.inspect(p,r)')]+'''
from hashlib import sha256
r='external-windows-corrective-development-archive-v1-20261018'
rows=v.inspect(p,r)
plan=[e['envelope']['payload'] for e in rows if e['envelope']['event_type']=='external.v3_archive_planned'][0]
post=v.inspect(p,'external-windows-corrective-development-postprocessing-v1-20261018')
helpers=[e['envelope']['payload']['postprocess_programs'] for e in post if e['envelope']['event_type']=='external.v3_postprocessing_planned'][0]
print(json.dumps({'terminal':[e['envelope']['payload'] for e in rows if e['envelope']['event_type']=='external.v3_archive_export_completed'],
 'archive_source_sha256':sha256(plan['driver_source'].encode()).hexdigest(),
 'grade_source_sha256':sha256(helpers['benchmarks.code_replay.confirmation_v3_grade'].encode()).hexdigest()}),flush=True)
'''
    request = {'program': "import subprocess,sys;p=subprocess.run([job['python'],'-I','-u','-c',job['probe']]);sys.exit(p.returncode)",
        'python': REMOTE+'/product-build-arw_zz8r/venv/bin/python', 'probe': probe}
    result = subprocess.run(ssh_options()+['user@192.168.0.87', framed_command()[-1]],
        input=framed_input(request), capture_output=True, timeout=90)
    save('external.v3_MEM_recovery_probe_result', {'exit_code': result.returncode,
        'stdout_base64': base64.b64encode(result.stdout).decode(),
        'stderr_base64': base64.b64encode(result.stderr).decode()})
    if result.returncode: raise RuntimeError('observation failed; no automatic restart')
    terminal_proof(json.loads(result.stdout), archive, grade)
    output.mkdir(mode=0o700); keys.mkdir(mode=0o700)
    for source, destination in [(REMOTE+'/corrective-development-archive-v1/', output),
                                (REMOTE+'/corrective-development-archive-keys-v1/', keys)]:
        command = copy_command(source, destination)
        save('external.v3_MEM_copy_started', {'command': command})
        result = subprocess.run(command, capture_output=True, timeout=3600)
        save('external.v3_MEM_copy_result', {'destination': str(destination), 'exit_code': result.returncode,
            'stdout_base64': base64.b64encode(result.stdout).decode(),
            'stderr_base64': base64.b64encode(result.stderr).decode()})
        if result.returncode: raise RuntimeError('partial copy preserved; no automatic restart')
    save('external.v3_MEM_recovery_started', {'source_vault_access': False, 'program': program})
    result = subprocess.run([sys.executable, '-c', program], capture_output=True, timeout=3600)
    save('external.v3_MEM_recovery_result', {'exit_code': result.returncode,
        'stdout_base64': base64.b64encode(result.stdout).decode(),
        'stderr_base64': base64.b64encode(result.stderr).decode()})
    if result.returncode: raise RuntimeError('standalone archive recovery failed; retain original evidence')
    proof = json.loads(result.stdout)
    if proof['source_vault_opened'] is not False:
        raise ValueError('no original-vault dependency permitted')
    save('external.v3_MEM_recovery_completed', {'proof': proof, 'archive': OUTPUT,
        'internal_keys': KEYS, 'goal_complete': False})
    print(json.dumps(proof), flush=True)


if __name__ == '__main__': main()
