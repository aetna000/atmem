"""Recording-only envelope compatibility with the unmodified public validator."""
import copy
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, '/Volumes/AtMemDolphin/upstream')

from benchmarks.dolphinbench.export import normalize_dispatch_envelopes
from harness.submission import grading_calls


def conversation(entries):
    return [{'role': 'user', 'content': 'unchanged original question'},
            {'role': 'assistant', 'content': 'native text',
             'usage': {'prompt_tokens': 12, 'completion_tokens': 3},
             'tool_calls': [{'id': 'native-id', 'name': 'tool_call', 'arguments': {'calls': entries}}]},
            {'role': 'tool', 'tool_call_id': 'native-id', 'content': 'exact native untrusted result'},
            {'role': 'assistant', 'content': 'finished',
             'usage': {'prompt_tokens': 24, 'completion_tokens': 5}}]


def test_unary_reversible_normalization_matches_independent_backend():
    args = {'folder': 'inbox'}
    original = conversation([{'name': 'mcp__dolphinbench_apps__list_inbox', 'arguments': args}])
    unchanged = copy.deepcopy(original)
    messages, receipt = normalize_dispatch_envelopes(original)
    backend = [{'tool': 'list_inbox', 'args': args, 'result': {'actual': True}}]
    assert grading_calls({'messages': messages, 'app_calls': backend}, 'fixture') == backend
    assert original == unchanged
    restored = copy.deepcopy(messages)
    for change in receipt['changes']:
        restored[change['message_position']]['tool_calls'][change['tool_call_position']] = change['original']
    assert restored == original
    assert messages[0] == original[0]
    assert messages[2:] == original[2:]
    assert messages[1]['usage'] == original[1]['usage']
    assert messages[1]['content'] == original[1]['content']
    assert normalize_dispatch_envelopes(messages)[0] == messages


def test_native_rejected_local_multi_batch_is_not_fabricated_as_execution():
    original = conversation([{'name': 'mcp__dolphinbench_apps__list_inbox', 'arguments': {}},
                             {'name': 'mcp__dolphinbench_apps__send_email', 'arguments': {}}])
    original[2]['content'] = 'Local tools cannot be batched.'
    messages, receipt = normalize_dispatch_envelopes(original)
    assert messages == original
    assert not receipt['changes']
    assert grading_calls({'messages': messages, 'app_calls': []}, 'rejected batch') == []


def test_malformed_entries_are_retained_not_guessed():
    original = conversation([{'name': 'missing arguments'}])
    assert normalize_dispatch_envelopes(original)[0] == original
