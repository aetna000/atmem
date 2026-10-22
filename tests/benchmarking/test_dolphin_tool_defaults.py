"""Effective-argument serialization fixtures, never training data."""
import copy
from pathlib import Path
import sys
import os

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, os.environ.get('DOLPHINBENCH_UPSTREAM', '/Volumes/AtMemDolphin/upstream'))
from benchmarks.dolphinbench.tool_defaults import normalize_effective_arguments
grading_calls = pytest.importorskip('harness.submission', reason='requires the separately pinned public DolphinBench harness').grading_calls


def test_only_proven_omitted_defaults_are_expanded_reversibly(tmp_path):
    source = tmp_path / 'repair_fixture.py'
    source.write_text('def send_email(to, subject, body, cc=None):\n    raise RuntimeError("never executed")\n')
    args = {'to': 'fixture@example.org', 'subject': 'fixture', 'body': 'unchanged'}
    original = [{'role': 'user', 'content': 'original'},
        {'role': 'assistant', 'usage': {'prompt_tokens': 2, 'completion_tokens': 1},
         'tool_calls': [{'id': 'same-id', 'name': 'tool_call', 'arguments': {
             'name': 'mcp__dolphinbench_apps__send_email', 'arguments': args}}]},
        {'role': 'tool', 'tool_call_id': 'same-id', 'content': 'exact native result'},
        {'role': 'assistant', 'content': 'done', 'usage': {'prompt_tokens': 4, 'completion_tokens': 2}}]
    raw = copy.deepcopy(original)
    backend = [{'tool': 'send_email', 'args': {**args, 'cc': None}, 'result': {'actual': True}}]
    messages, receipt = normalize_effective_arguments(original, backend, [source])
    assert grading_calls({'messages': messages, 'app_calls': backend}, 'fixture') == backend
    assert original == raw
    restored = copy.deepcopy(messages)
    for change in receipt['changes']:
        restored[change['message_position']]['tool_calls'][change['tool_call_position']] = change['original']
        assert change['default_provenance']['cc'][0]['source_file'] == source.name
    assert restored == original
    assert normalize_effective_arguments(messages, backend, [source])[0] == messages
    for bad_args in ({**args, 'to': 'wrong@example.org', 'cc': None}, {**args, 'required_secret': 'invented'}):
        with pytest.raises(ValueError, match='beyond proven'):
            normalize_effective_arguments(original, [{'tool': 'send_email', 'args': bad_args}], [source])


def test_conflicting_signature_defaults_are_not_guessed(tmp_path):
    source = tmp_path / 'repair_fixture.py'
    source.write_text('class A:\n def action(self, option=None): pass\nclass B:\n def action(self, option=False): pass\n')
    messages = [{'role': 'assistant', 'tool_calls': [{'id': 'a', 'name': 'action', 'arguments': {}}]}]
    with pytest.raises(ValueError, match='beyond proven'):
        normalize_effective_arguments(messages, [{'tool': 'action', 'args': {'option': None}}], [source])
