import ast

from benchmarks.code_replay.confirmation_bridge_readiness import PROGRAM,probe_patch
from benchmarks.code_replay.windows_confirmation_checks import PROBE_PATH


def test_installed_readiness_is_zero_model_and_preserves_original_server():
    ast.parse(PROGRAM,feature_version=(3,9))
    assert "'model_calls':0" in PROGRAM
    assert "qualification.mkdir(mode=0o700,exist_ok=False)" in PROGRAM
    assert "preset_path.read_bytes()==preset_bytes" in PROGRAM
    assert "server_path.read_bytes()==server_bytes" in PROGRAM
    assert 'user=1000,group=1000,extra_groups=[]' in PROGRAM
    assert 'run_cli' not in PROGRAM and 'auth.write' not in PROGRAM


def test_readiness_probe_is_a_real_bounded_public_test_patch(monkeypatch,tmp_path):
    import subprocess
    text=probe_patch('flask')
    subprocess.run(['git','apply','--check','-'],input=text.encode(),cwd=tmp_path,check=True,capture_output=True)
    subprocess.run(['git','apply','-'],input=text.encode(),cwd=tmp_path,check=True,capture_output=True)
    source=(tmp_path/PROBE_PATH).read_text()
    ast.parse(source,feature_version=(3,9))
    assert len(text.encode())<262144 and 'importlib.import_module' in source
