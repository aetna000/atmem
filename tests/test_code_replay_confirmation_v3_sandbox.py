import ast
import pytest
from benchmarks.code_replay.windows_cohort import model_program
from benchmarks.code_replay.confirmation_v3_sandbox import PROGRAM,model_prefix,hidden_view_program,hidden_canary_failure


def test_exact_model_policy_prefix_stops_before_credentials_and_inference():
    original=model_program();prefix=model_prefix(original)
    ast.parse(prefix,feature_version=(3,10));ast.parse(PROGRAM,feature_version=(3,10))
    assert original.startswith(prefix)
    assert 'def permission_arguments' in prefix
    assert 'auth.write_bytes(' not in prefix and 'run_cli(session,' not in prefix
    assert 'permission_arguments()' in PROGRAM
    assert "'credentials_copied':False" in PROGRAM and "'model_calls':0" in PROGRAM
    assert "'UNRESTRICTED_CANARY_OK'" in PROGRAM
    assert "'V3_SANDBOX_BOUNDARIES_OK'" in PROGRAM


def test_changed_model_prefix_refused():
    with pytest.raises(ValueError):model_prefix('no frozen auth boundary')


def test_hidden_view_correction_changes_only_the_denial_expectation():
    changed=hidden_view_program();ast.parse(changed,feature_version=(3,10))
    before="except PermissionError:\\n pass\\nelse:\\n raise RuntimeError('owned private canary readable inside sandbox')"
    after=before.replace('except PermissionError:','except (PermissionError,FileNotFoundError):')
    assert changed.replace(after,before)==PROGRAM


def test_repair_guard_requires_positive_control_and_exact_hidden_canary():
    import base64,json
    def encoded(value):return base64.b64encode(value).decode()
    worker={'qualified':False,'uid':1000,'model_calls':0,'credentials_copied':False,'host_listener_connections':1,
        'canary_path':'/private/canary','unrestricted':{'exit_code':0,'stdout_base64':encoded(b'UNRESTRICTED_CANARY_OK\n'),
        'command':['python',"assert Path('/private/canary').read_bytes()==b'nonce'"]},
        'sandbox':{'exit_code':1,'stdout_base64':'','stderr_base64':encoded(b"FileNotFoundError: [Errno 2] No such file or directory: '/private/canary'\n")}}
    def row():return {'exit_code':0,'stdout_base64':encoded(json.dumps(worker).encode())}
    assert hidden_canary_failure(row())
    worker['unrestricted']['exit_code']=1
    assert not hidden_canary_failure(row())
    worker['unrestricted']['exit_code']=0;worker['sandbox']['stderr_base64']=encoded(b'Other failure\n')
    assert not hidden_canary_failure(row())
