import ast

import pytest

from benchmarks.code_replay.query_nomination_trace_audit import reader_program


def test_audit_reuses_the_verified_bootstrap_and_separate_stdin_program():
    bootstrap = 'import json\nfrom pathlib import Path\narchive=None\nproof=archive.recover_collection(None,None)\n'
    program = reader_program(bootstrap, 'def audit(archive,output,keys):return {}\n')
    ast.parse(program, feature_version=(3, 10))
    assert program.startswith(bootstrap[:bootstrap.index('\nproof=archive.recover_collection')])
    assert 'proof=archive.recover_collection' not in program
    assert 'ns["audit"](archive' in program
    with pytest.raises(ValueError):
        reader_program('different bootstrap', '')
