"""No-network guards against dropping native developer instructions."""
from copy import deepcopy
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from benchmarks.dolphinbench.subscription_service import preserve_instructions
from benchmarks.dolphinbench.subscription_service import subscription_reader_model


@pytest.mark.parametrize('family',['luna','sol'])
def test_reader_family_is_explicit_and_not_upgraded(family):
    assert subscription_reader_model('openai/gpt-5.6-'+family)=='gpt-5.6-'+family


@pytest.mark.parametrize('model',['gpt-5.6-sol','openai/gpt-5.6','openai/unknown',None])
def test_reader_alias_or_unknown_family_fails_without_fallback(model):
    with pytest.raises(ValueError):subscription_reader_model(model)


def test_developer_instruction_bytes_and_user_boundary_are_preserved():
    messages = [{'role': 'developer', 'content': 'Authorized context 中文\nexact bytes'},
                {'role': 'user', 'content': '[date] original question'}]
    original = deepcopy(messages)
    mapped, expected = preserve_instructions(messages)
    assert mapped[0] == {'role': 'system', 'content': messages[0]['content']}
    assert expected == messages[0]['content']
    assert mapped[1:] == messages[1:] and messages == original


def test_mixed_instruction_priorities_fail_instead_of_silent_flattening():
    with pytest.raises(ValueError, match='Mixed'):
        preserve_instructions([{'role': 'system', 'content': 'a'}, {'role': 'developer', 'content': 'b'}])


def test_missing_prologue_does_not_invent_instructions():
    messages = [{'role': 'user', 'content': 'unaltered'}]
    assert preserve_instructions(messages) == (messages, None)
