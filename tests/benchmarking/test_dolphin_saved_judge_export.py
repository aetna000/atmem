"""Export-only mechanics; fixtures are not benchmark or training observations."""
import copy
import importlib.util
from pathlib import Path
import sys
from types import ModuleType

import pytest


@pytest.fixture
def normalize(monkeypatch):
    module = ModuleType('harness.submission')
    module.MESSAGE_FIELDS = {'role', 'content', 'usage', 'duration_ms', 'settings', 'tool_calls', 'tool_call_id'}
    module.clean_message = lambda m: {k: copy.deepcopy(v) for k, v in m.items()
        if k in module.MESSAGE_FIELDS and v is not None}
    monkeypatch.setitem(sys.modules, 'harness.submission', module)
    path = Path(__file__).resolve().parents[2] / 'scripts/package_dolphin_saved_judges_20261021.py'
    spec = importlib.util.spec_from_file_location('saved_judge_export_fixture', path)
    implementation = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(implementation)
    return implementation.normalize_grade


def grade():
    return {'settings': {'model': 'gpt-5.6-sol', 'reasoning_effort': 'medium'},
        'checks': [{'check': 0, 'passed': False, 'messages': [
            {'role': 'user', 'content': 'fixture prompt'},
            {'role': 'assistant', 'content': '{"passed":false}', 'refusal': None,
             'reasoning': 'opaque fixture metadata', 'reasoning_details': [{'type': 'fixture'}],
             'usage': {'prompt_tokens': 10, 'completion_tokens': 2}, 'duration_ms': 12.0}]}]}


def test_judge_export_keeps_verdict_and_reversible_metadata(normalize):
    original = grade()
    before = copy.deepcopy(original)
    revised, receipt = normalize(original)
    assert original == before
    assert revised['checks'][0]['passed'] is False
    assert revised['settings'] == original['settings']
    answer = revised['checks'][0]['messages'][-1]
    for key in ('content', 'usage', 'duration_ms'):
        assert answer[key] == original['checks'][0]['messages'][-1][key]
    assert receipt[0]['removed_fields'] == {'refusal': None,
        'reasoning': 'opaque fixture metadata', 'reasoning_details': [{'type': 'fixture'}]}


@pytest.mark.parametrize('extra', [{'arbitrary': 'unknown'}, {'refusal': 'not null'}])
def test_unreviewed_metadata_and_actual_refusals_are_rejected(normalize, extra):
    original = grade()
    original['checks'][0]['messages'][-1].update(extra)
    with pytest.raises(ValueError):
        normalize(original)
