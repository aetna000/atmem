import ast
import base64
from copy import deepcopy
import json
from pathlib import Path

import pytest

from benchmarks.code_replay import literal_anchor_controls as controls


def test_fresh_real_source_controls_keep_authority_and_pin_new_build():
    source = controls.qualification_source(Path('benchmarks/code_replay/compatibility_qualification.py').read_text())
    ast.parse(source, feature_version=(3, 10))
    namespace = {'__name__': 'literal_controls_test'}
    exec(compile(source, '<literal-controls-test>', 'exec'), namespace)
    assert namespace['RUN'] == controls.QUALIFY
    assert len(namespace['IDENTITIES']) == 5
    assert controls.preview.CANDIDATE in namespace['PROGRAM']
    assert controls.WHEEL in source
    assert 'foreign_scope_denied' in namespace['PROGRAM']
    assert 'encrypted bundle lost original generation data' in namespace['PROGRAM']
    assert 'user=1000,group=1000' in namespace['PROGRAM']
    assert controls.ROOT in source
    assert 'owned-state-continuation' not in source


def test_replay_uses_actual_installed_package_before_operator_and_same_all_case_gates():
    source = controls.replay_source()
    assert source.index('from atmem.knowledge.code import packing') < source.index('sys.path[:0]')
    assert controls.preview.DIAGNOSTIC in source
    assert 'external.literal_anchors_completed' in source
    assert 'len(stages) != 19' in source
    assert "actual == reference['candidate_pack']" in source


def test_successful_build_cannot_be_replaced_with_an_old_or_failed_preview():
    proof = {'qualified': True, 'wheel_sha256': controls.WHEEL, 'python': controls.PYTHON,
             'candidate_packing_sha256': controls.preview.CANDIDATE, 'dependencies_equal': True,
             'ordinary_user_exit': 0,
             'ordinary_stdout_base64': base64.b64encode(json.dumps({'literal_anchor_import': True}).encode()).decode()}
    def rows(value):
        return [{'envelope': {'event_type': 'external.literal_anchor_build_submission_result',
                 'payload': {'exit_code': 0, 'stdout_base64': base64.b64encode(json.dumps(value).encode()).decode()}}}]
    assert controls.verified_build(rows(proof)) == proof
    for field, wrong in [('wheel_sha256', 'old'), ('candidate_packing_sha256', 'old'),
                         ('python', '/unexpected/python'), ('dependencies_equal', False)]:
        bad = deepcopy(proof); bad[field] = wrong
        with pytest.raises(ValueError):
            controls.verified_build(rows(bad))
