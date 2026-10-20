import importlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))
export = importlib.import_module('benchmarks.dolphinbench.export')


def test_streamed_tool_arguments_and_usage_are_not_estimated():
    result, usage = export.assistant_response([
        {'choices': [{'index': 0, 'delta': {'tool_calls': [{'index': 0, 'id': 'call-1',
            'function': {'name': 'tool_call', 'arguments': '{"calls":'}}]}}]},
        {'choices': [{'index': 0, 'delta': {'tool_calls': [{'index': 0,
            'function': {'arguments': '[]}'}}]}}]},
        {'choices': [], 'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'cost': 0.001}}])
    assert result['tool_calls'][0]['function'] == {'name': 'tool_call', 'arguments': '{"calls":[]}'}
    assert usage['cost'] == 0.001


def test_stream_without_usage_is_not_zero():
    with pytest.raises(ValueError, match='no API usage'):
        export.assistant_response([{'choices': [{'delta': {'content': 'hello'}}]}])


def test_multiple_response_choices_are_rejected():
    with pytest.raises(ValueError, match='Multiple response'):
        export.assistant_response([{'choices': [{'index': 1, 'delta': {}}]}])
