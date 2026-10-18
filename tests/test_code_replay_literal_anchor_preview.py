import ast
from copy import deepcopy
import inspect
from pathlib import Path

import pytest

from benchmarks.code_replay import literal_anchor_preview as preview
from benchmarks.code_replay import query_nomination_preview as previous
from tests.test_code_replay_literal_anchor_diagnostic import previous_source


def proofs():
    candidate = Path('atmem/knowledge/code/packing.py').read_text()
    baseline = previous_source(candidate)
    def event(kind, payload):
        return {'envelope': {'event_type': kind, 'payload': payload}}
    rows = [event('external.literal_anchors_planned', {
        'baseline_source': baseline, 'baseline_sha256': preview.BASELINE}),
        event('external.literal_anchors_started', {'candidate_source': candidate, 'candidate_sha256': preview.CANDIDATE}),
        event('external.literal_anchors_completed', {
            'summary': {'identities': 19, 'all_original_packs_reproduced': True,
                        'source_vault_opened': False, 'models_repeated': 0, 'private_grades_repeated': 0},
            'cases': [{'identity': str(i), 'original_pack_reproduced': True, 'candidate_pack': 'bounded'} for i in range(19)]})]
    return candidate, {preview.DIAGNOSTIC: rows}


def test_local_and_actual_derived_build_gate_agree_on_complete_static_proof():
    candidate, reports = proofs()
    assert preview.static_ready(reports, candidate)
    source = preview.build_driver(inspect.getsource(previous))
    ast.parse(source, feature_version=(3, 10))
    namespace = {'__name__': 'literal_build_test'}
    exec(compile(source, '<literal-build-test>', 'exec'), namespace)
    assert namespace['RUN'] == preview.RUN
    assert namespace['CANDIDATE'] == preview.CANDIDATE
    assert namespace['static_ready'](reports, candidate)
    assert namespace['PRIOR'] == previous.PRIOR
    assert namespace['BASE_WHEEL'] == previous.BASE_WHEEL
    build = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == 'build')
    ordinary, = [n.value.value for n in build.body if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == 'program' for t in n.targets)
                 and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)
                 and '_query_literal_targets' in n.value.value]
    exec(ordinary, {})


def test_missing_over_budget_or_replayed_static_data_cannot_start_build():
    candidate, reports = proofs()
    for field, value in [('models_repeated', 1), ('source_vault_opened', True)]:
        bad = deepcopy(reports); bad[preview.DIAGNOSTIC][2]['envelope']['payload']['summary'][field] = value
        with pytest.raises(ValueError):
            preview.static_ready(bad, candidate)
    bad = deepcopy(reports); bad[preview.DIAGNOSTIC][2]['envelope']['payload']['cases'].pop()
    with pytest.raises(ValueError):
        preview.static_ready(bad, candidate)
    bad = deepcopy(reports); bad[preview.DIAGNOSTIC][2]['envelope']['payload']['cases'][0]['candidate_pack'] = 'x'*4097
    with pytest.raises(ValueError):
        preview.static_ready(bad, candidate)
    with pytest.raises(ValueError):
        preview.build_driver('unrecognized original builder')
