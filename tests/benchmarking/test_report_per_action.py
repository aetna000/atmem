import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('per_action', Path(__file__).parents[2] / 'scripts/report_dolphin_per_action.py')
per_action = importlib.util.module_from_spec(spec)
spec.loader.exec_module(per_action)

TASK = {'request': 'Email ops and post a PR comment.', 'today': '2026-09-14', 'assertions': [
    {'type': 'field_equals', 'tool': 'list_open_prs', 'path': 'result.ok', 'value': True, 'check_id': 'c0', 'action_id': 'read'},
    {'type': 'field_equals', 'tool': 'send_email', 'path': 'result.ok', 'value': True, 'check_id': 'c1', 'action_id': 'mail'},
    {'type': 'field_equals', 'tool': 'send_email', 'path': 'result.to', 'value': 'ops@x', 'check_id': 'c2', 'action_id': 'mail'},
    {'type': 'field_llm_judge', 'tool': 'send_email', 'path': 'result.body', 'criterion': 'declines', 'check_id': 'c3', 'action_id': 'mail'},
    {'type': 'field_equals', 'tool': 'post_pr_comment', 'path': 'result.ok', 'value': True, 'check_id': 'c4', 'action_id': 'comment'}]}


def fake_evaluate(check, call, request, today):
    node = call
    for part in check['path'].split('.'):
        node = node.get(part) if isinstance(node, dict) else None
    return (node == check.get('value'), '', node)


def test_actions_are_grouped_split_by_kind_and_classified():
    checks = [{'check': 0, 'passed': True}, {'check': 1, 'passed': False}, {'check': 2, 'passed': False},
              {'check': 3, 'passed': False, 'messages': [{'role': 'assistant', 'content': '{"passed": false, "reason": "accepts instead"}'}]},
              {'check': 4, 'passed': False}]
    calls = [{'tool': 'send_email', 'result': {'ok': True, 'to': 'ops@x', 'body': 'works for me'}}]
    rows = per_action.report({'p/001': TASK}, [('p/001', checks, calls)], fake_evaluate)
    actions = {a['action_id']: a for a in rows[0]['actions']}
    assert actions['read']['kind'] == 'read' and actions['read']['passed']
    assert actions['mail']['failure_class'] == 'judged_content' and actions['mail']['judge_reasons'] == ['accepts instead']
    assert actions['comment']['failure_class'] == 'no_call'
    wrong = [{'tool': 'send_email', 'result': {'ok': True, 'to': 'other@x'}}]
    rows = per_action.report({'p/001': TASK}, [('p/001', checks, wrong)], fake_evaluate)
    assert {a['action_id']: a for a in rows[0]['actions']}['mail']['failure_class'] == 'wrong_value'
    assert per_action.summarize(rows)['actions_by_kind'] == {'read_passed': 1, 'write_failed': 2}
