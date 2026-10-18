from hashlib import sha256

import pytest

from benchmarks.code_replay.corrective_transfer_recovery import copy_command, terminal_proof, ssh_options
from benchmarks.code_replay.corrective_transfer import OUTPUT, KEYS
from benchmarks.code_replay.confirmation_v3_transfer import REMOTE


def test_copy_never_moves_keys_to_mem_or_deletes_or_reuses_dead_master():
    for source, target in [(REMOTE+'/corrective-development-archive-v1/', OUTPUT),
                           (REMOTE+'/corrective-development-archive-keys-v1/', KEYS)]:
        command = copy_command(source, target)
        assert '--delete' not in command and 'ControlPath=none' in command[4]
        assert 'StrictHostKeyChecking=yes' in ssh_options()
    with pytest.raises(ValueError): copy_command(REMOTE+'/corrective-development-archive-keys-v1/', OUTPUT)
    with pytest.raises(ValueError): copy_command(REMOTE+'/', KEYS)


def test_original_source_and_terminal_are_required():
    proof = {'terminal': [{'runs': 332}], 'archive_source_sha256': sha256(b'archive').hexdigest(),
             'grade_source_sha256': sha256(b'grade').hexdigest()}
    terminal_proof(proof, 'archive', 'grade')
    with pytest.raises(ValueError): terminal_proof(proof, 'changed', 'grade')
    proof['terminal'] = []
    with pytest.raises(ValueError): terminal_proof(proof, 'archive', 'grade')
