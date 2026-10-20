import ast
import subprocess
import sys
import pytest
from benchmarks.code_replay.program_transport import compact_program


def test_exact_program_and_stdin_survive_individual_argument_limit():
    source='# unchanged operator code\n'*10000+"import json,sys\nprint(json.dumps(json.load(sys.stdin)))\n"
    program=compact_program(source)
    assert len(source.encode())>131072 and len(program.encode())<100000
    ast.parse(program,feature_version=(3,9))
    result=subprocess.run([sys.executable,'-I','-S','-c',program],input=b'{"context":"unchanged"}',capture_output=True,timeout=10)
    assert result.returncode==0 and result.stdout.strip()==b'{"context": "unchanged"}'


def test_program_tamper_and_limits_fail_closed():
    program=compact_program("print('fixture')\n")
    result=subprocess.run([sys.executable,'-I','-S','-c',program.replace('hexdigest()!=','hexdigest()==')],capture_output=True,timeout=10)
    assert result.returncode!=0 and result.stdout==b''
    with pytest.raises(ValueError):compact_program('x'*4000001)
    with pytest.raises(ValueError):compact_program(None)
