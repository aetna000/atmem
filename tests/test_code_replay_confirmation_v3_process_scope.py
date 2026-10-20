import ast
import pytest
from benchmarks.code_replay.confirmation_v3_process_scope import ROOT,CHILD_BOOTSTRAP,group_path


@pytest.mark.parametrize('leaf',['control-v1','block-0-native','block-37-tools'])
def test_only_exact_case_groups(leaf):
    assert group_path(leaf).parent==ROOT


@pytest.mark.parametrize('leaf',['','..','/','../other','block-38-tools','block-0-other','control-v2'])
def test_broad_or_unplanned_group_refused(leaf):
    with pytest.raises(ValueError):group_path(leaf)


def test_group_entry_precedes_irreversible_privilege_drop_and_actor():
    ast.parse(CHILD_BOOTSTRAP,feature_version=(3,10))
    assert CHILD_BOOTSTRAP.index("(group/'cgroup.procs').write_text")<CHILD_BOOTSTRAP.index('os.setuid(1000)')
    assert CHILD_BOOTSTRAP.index('os.setuid(1000)')<CHILD_BOOTSTRAP.index("exec(job['program'])")
