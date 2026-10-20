"""Metadata-only export checks; fixtures are not benchmark observations."""
from copy import deepcopy
import importlib.util
from pathlib import Path


def load():
    path = Path(__file__).resolve().parents[2] / 'scripts/package_dolphin_actual_settings_20261021.py'
    spec = importlib.util.spec_from_file_location('provider_settings_export', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_only_unsupported_agent_cap_is_removed():
    module = load()
    value = {'settings': {'model': module.MODEL, 'reasoning_effort': 'medium', 'max_completion_tokens': 4096},
        'judge_settings': {'model': 'gpt-5.6-sol', 'max_completion_tokens': 8000},
        'tests': [{'messages': [{'role': 'assistant', 'content': 'unchanged',
            'usage': {'input_tokens': 17, 'output_tokens': 3},
            'settings': {'model': module.MODEL, 'max_tokens': 4096}}],
            'grading': [{'passed': False}]}]}
    original = deepcopy(value)
    actual, removed = module.normalize(value)
    assert value == original
    assert len(removed) == 2
    assert 'max_completion_tokens' not in actual['settings']
    assert actual['judge_settings'] == original['judge_settings']
    assert actual['tests'][0]['grading'] == original['tests'][0]['grading']
    assert actual['tests'][0]['messages'][0]['usage'] == original['tests'][0]['messages'][0]['usage']
    assert actual['tests'][0]['messages'][0]['content'] == 'unchanged'


def test_different_model_settings_are_not_modified():
    value = {'settings': {'model': 'other-model', 'max_tokens': 4096}, 'tests': []}
    actual, removed = load().normalize(value)
    assert actual == value and removed == []
