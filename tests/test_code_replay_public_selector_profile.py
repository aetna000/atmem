import ast
import re
from pathlib import PurePosixPath

import pytest

from benchmarks.code_replay.public_selector_profile import validators, corrected_program, program_modules


def fixture_program(role, validator):
    name = 'atmem_public_test_helpers' if role == 'server' else 'atmem_public_validation'
    modules = [('unchanged', 'ORIGINAL = "do not change"\n'), (name, 'import re\nfrom pathlib import PurePosixPath\n'+validator+'\n')]
    return 'import types\nfor name,source in '+repr(modules)+':\n pass\n# exact outer bytes\n'


@pytest.mark.parametrize('role', ['server', 'worker'])
def test_only_registered_directory_ancestry_changes_in_each_public_role(role):
    old, new = validators()
    original = fixture_program(role, old)
    corrected = corrected_program(original, role=role)
    _, modules = program_modules(corrected)
    assert modules[0] == ('unchanged', 'ORIGINAL = "do not change"\n')
    assert corrected.endswith('# exact outer bytes\n')
    namespace = {'PINNED_TEST_PATHS': ('package/checks', 'test_exact.py')}
    exec(modules[1][1], namespace)
    args = lambda path: {'paths': [path], 'keyword': None, 'max_failures': 0}
    assert namespace['pytest_arguments'](args('package/checks/unit/test_one.py'))[-1] == 'package/checks/unit/test_one.py'
    assert namespace['pytest_arguments'](args('test_exact.py::test_one'))[-1] == 'test_exact.py::test_one'
    for path in ('package/checks_other/test_one.py', 'package/checks/../../private.py', 'test_exact.py/nested.py', 'source.py'):
        with pytest.raises(ValueError):
            namespace['pytest_arguments'](args(path))
    with pytest.raises(ValueError):
        corrected_program(corrected, role=role)


def test_unknown_roles_or_other_budget_mutations_are_not_accepted():
    old, new = validators()
    with pytest.raises(ValueError):
        corrected_program(fixture_program('server', old), role='private-grader')
    with pytest.raises(ValueError):
        corrected_program(fixture_program('server', old.replace('0 <= maximum <= 10', '0 <= maximum <= 100')), role='server')
    with pytest.raises(ValueError):
        corrected_program('print("unknown wrapper")', role='worker')
    with pytest.raises(ValueError):
        corrected_program(fixture_program('server', old), role='server',
                          validator_pair=(old, new.replace('0 <= maximum <= 10', '0 <= maximum <= 100')))
    assert corrected_program(fixture_program('server', old), role='server', validator_pair=(old, new))
