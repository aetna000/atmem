import ast
import base64
from hashlib import sha256
import json
import zlib

import pytest

from benchmarks.code_replay.windows_retain import PROGRAM, decode_recovery


def payload(result):
    raw = json.dumps(result).encode()
    return json.dumps({'bytes': len(raw), 'sha256': sha256(raw).hexdigest(),
        'zlib_base64': base64.b64encode(zlib.compress(raw)).decode()})


def test_recovery_requires_verified_protected_full_evidence():
    result = {'status': {'at_rest_state': 'encrypted', 'capture_mode': 'full'},
        'public_test_events': [], 'code_audit_chain_verified': True}
    assert decode_recovery(payload(result))[1] == result
    with pytest.raises(ValueError, match='audit chain'):
        decode_recovery(payload({**result, 'code_audit_chain_verified': False}))
    with pytest.raises(ValueError, match='full encrypted'):
        decode_recovery(payload({**result, 'status': {'at_rest_state': 'plaintext', 'capture_mode': 'full'}}))
    corrupted = json.loads(payload(result)); corrupted['bytes'] += 1
    with pytest.raises(ValueError, match='digest'):
        decode_recovery(json.dumps(corrupted))


def test_program_is_inspection_not_solver_or_deletion():
    ast.parse(PROGRAM)
    assert "os.environ['ATMEM_HOME']" in PROGRAM
    assert 'preset.json' in PROGRAM
    assert 'verify_audit_chain' in PROGRAM
    assert 'auth.json' not in PROGRAM
    assert 'subprocess' not in PROGRAM
    assert 'unlink' not in PROGRAM
