"""Measurement unit tests, not autonomous agent performance evidence."""
from copy import deepcopy

import pytest

from benchmarks.agent_continuity.retail_live_fault import resumed_observations


def event(call_id='first', *, before='a', after='b', error=False):
    return {'call': {'id': call_id, 'name': 'exchange', 'arguments': {'item': 'keyboard'}},
            'before': before, 'after': after, 'response': {'error': error}}


def test_rejected_repeat_is_not_counted_as_another_effect():
    before = {'journal': [event()]}
    after = {'journal': [event(), event('second', before='b', after='b', error=True)]}
    result = resumed_observations(before, after)
    assert result['new_invocations_after_restart'] == 1
    assert result['same_name_and_arguments_after_restart'] == 1
    assert result['new_state_changes_after_restart'] == 0
    assert result['native_error_replies_after_restart'] == 1


def test_safe_stop_has_no_extra_requests_but_is_not_scored_as_completion():
    before = {'journal': [event()]}
    result = resumed_observations(before, deepcopy(before))
    assert result['new_invocations_after_restart'] == 0
    assert 'completion' not in result and 'reward' not in result


def test_changed_history_is_not_accepted_as_clean_resume():
    before = {'journal': [event()]}
    with pytest.raises(ValueError, match='history changed'):
        resumed_observations(before, {'journal': [event('replacement')]})


def test_different_valid_work_is_not_labelled_repeat():
    later = event('second', before='b', after='c')
    later['call']['arguments']['item'] = 'mouse'
    result = resumed_observations({'journal': [event()]}, {'journal': [event(), later]})
    assert result['new_state_changes_after_restart'] == 1
    assert result['same_name_and_arguments_after_restart'] == 0
