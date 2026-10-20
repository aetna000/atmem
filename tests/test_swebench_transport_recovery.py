import json
from pathlib import Path
import select
import subprocess
import sys
import pytest
from tools.recover_swebench_grade import framing_only, NEW_LOADER, OLD_LOADER


def test_framed_job_finishes_without_ssh_eof_and_children_get_empty_stdin():
    code = 'import subprocess;data=subprocess.check_output([sys.executable,"-c","import sys;print(len(sys.stdin.read()))"]);print(json.dumps({"value":job["payload"],"child_eof":data.decode().strip()=="0"}),flush=True)'
    process = subprocess.Popen([sys.executable, '-c', NEW_LOADER], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        process.stdin.write(json.dumps({'program': code, 'payload': '结构\nlate'}) + '\n')
        process.stdin.flush()  # Deliberately leave stdin open, as in the Windows failure.
        assert select.select([process.stdout], [], [], 5)[0]
        response = json.loads(process.stdout.readline())
        assert response == {'value': '结构\nlate', 'child_eof': True}
        assert process.wait(timeout=5) == 0
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        process.stdin.close()


def test_recovery_refuses_any_change_beyond_exact_transport_framing():
    current = Path('benchmarks/code_replay/swebench_pilot.py').read_text()
    original = current.replace(NEW_LOADER, OLD_LOADER).replace(
        "input=json.dumps({'program': program, 'payload': payload}) + '\\n',",
        "input=json.dumps({'program': program, 'payload': payload}),")
    framing_only(original, current)
    with pytest.raises(ValueError, match='beyond exact'):
        framing_only(original, current + '\n# unrelated change')
