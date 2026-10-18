import stat
from types import SimpleNamespace

import pytest

from benchmarks.code_replay.confirmation_runtime_access import validate_directory


def test_only_exact_root_private_directory_is_accepted():
    validate_directory(SimpleNamespace(st_mode=stat.S_IFDIR|0o700,st_uid=0,st_gid=0))


@pytest.mark.parametrize('kind,mode,uid,gid',[
    (stat.S_IFLNK,0o700,0,0),(stat.S_IFREG,0o700,0,0),
    (stat.S_IFDIR,0o755,0,0),(stat.S_IFDIR,0o710,0,1000),
    (stat.S_IFDIR,0o700,1000,0),(stat.S_IFDIR,0o700,0,1000),
])
def test_unexpected_owner_mode_or_file_type_rejected(kind,mode,uid,gid):
    with pytest.raises(ValueError):
        validate_directory(SimpleNamespace(st_mode=kind|mode,st_uid=uid,st_gid=gid))


def test_code_resume_reuses_exact_original_phase_without_public_execution():
    import ast
    from benchmarks.code_replay.confirmation_code_readiness import code_only_program,RECOVER_PUBLIC
    source=code_only_program()
    ast.parse(source,feature_version=(3,10))
    ast.parse(RECOVER_PUBLIC,feature_version=(3,10))
    assert 'user=1000,group=1000,extra_groups=[]' in source
    assert "'name':'code_source'" in source
    assert 'run_public_tests' not in source+RECOVER_PUBLIC
    assert 'subprocess' not in RECOVER_PUBLIC
    assert 'vault.inspect(principal' in RECOVER_PUBLIC
