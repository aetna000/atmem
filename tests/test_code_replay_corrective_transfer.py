import ast
import inspect
import json
from pathlib import Path
import subprocess
import sys

import pytest

from benchmarks.code_replay import confirmation_v3_transfer
from benchmarks.code_replay.corrective_transfer import transfer_source, recovery_program, OUTPUT, KEYS


def test_transfer_keeps_exact_paths_no_delete_and_internal_keys():
    source = transfer_source(inspect.getsource(confirmation_v3_transfer), 'archive', 'grade', 'audit')
    namespace = {'__name__': 'CD1_transfer_test'}
    exec(compile(source, '<transfer-test>', 'exec'), namespace)
    assert namespace['OUTPUT'] == Path(OUTPUT)
    assert namespace['KEYS'] == Path(KEYS)
    remote = namespace['REMOTE']
    command = namespace['transfer_command'](remote+'/corrective-development-archive-v1/', Path(OUTPUT))
    assert '--delete' not in command
    with pytest.raises(ValueError):
        namespace['transfer_command'](remote+'/corrective-development-archive-keys-v1/', Path(OUTPUT))
    with pytest.raises(ValueError):
        namespace['transfer_command'](remote+'/confirmation-archive-v3/', Path(OUTPUT))


def test_fresh_reader_checks_all_cells_and_denies_live_vault():
    program = recovery_program('archive', 'grade', 'audit')
    ast.parse(program, feature_version=(3, 10))
    assert 'operational_evidence=forbidden' in program
    assert "proof['request_audit']['verified_original_requests']!=38" in program
    assert 'subprocess' not in program
    assert '/Volumes/MEM/' in program and KEYS in program


def test_actual_fresh_reader_bootstrap_executes_with_no_live_vault():
    # Bootstrap/import contract only; these stubs are not benchmark evidence.
    archive = '''def recover_collection(output,keys):
 from benchmarks.code_replay import run_evidence
 try:run_evidence.operational_evidence()
 except RuntimeError:pass
 else:raise AssertionError('live vault boundary was not denied')
 return {'candidates':38,'private_grades':38,'public_vaults':38,'source_vault_opened':False}
'''
    audit = "def audit_collection(output,keys):return {'verified_original_requests':38}\n"
    program = recovery_program(archive, 'qualification_only=True', audit)
    proc = subprocess.run([sys.executable, '-c', program], capture_output=True, text=True, timeout=15)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)['request_audit']['verified_original_requests'] == 38
    failed = recovery_program(archive, 'qualification_only=True', audit.replace(':38', ':37'))
    proc = subprocess.run([sys.executable, '-c', failed], capture_output=True, text=True, timeout=15)
    assert proc.returncode != 0 and 'all original CD1 requests required' in proc.stderr
