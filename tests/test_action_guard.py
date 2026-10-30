import importlib.util
import json
import stat
import sys

import pytest

from atmem import action_guard as g

APP = 'mcp__dolphinbench_apps__'
MEMORY = 'mcp__atmem_discovery__memory_search'
NOTES_REQUEST = ('[2026-09-14] Create an archive note recording the March 27, 2026 board review\'s '
                 'decision on first-half fundraising and the operating priorities it set for Q2.')


def guard(request, tools=(), **options):
    value = g.ActionGuard(**{'checkpoint': False, **options})
    value.begin_turn('s', request, set(tools))
    return value


@pytest.mark.parametrize('text', [
    NOTES_REQUEST,
    '[2026-09-14] Text Jamie at +14155550142 back.',
    '[2026-09-14] On scaffold/mercury#3474, correct the launch-retro entry with the launch date.',
    '[2028-01-01] Inspect lantern#1602 and review its customer-visible chronology changes.',
    '[2026-09-14] Check the company travel policy and, if compliant, book flight quote flight_129.',
    'Please check my calendar for Saturday and, if 11:00 a.m. is open, add brunch to my calendar.',
    'Email vendorops@northwind.example a scheduling reply to their non-urgent call request.',
])
def test_action_requests_are_detected_from_request_text_only(text):
    assert g.classify(text).action


def test_domains_ignore_board_reviews_and_issue_numbers():
    assert g.classify(NOTES_REQUEST).domains == {'docs'}
    assert g.classify('Inspect lantern#1602 and review it').domains == {'code_review'}
    assert g.classify('Post in Slack channel #support-rotation: hi').domains == {'chat'}


def test_questions_are_not_actions_and_explicit_local_requests_are_recognised():
    assert not g.classify('What did the board decide about Q2 priorities?').action
    assert g.classify('Create a note in Apple Notes about Q2').explicit_local


def test_wrappers_are_unwrapped():
    assert g.unwrap('tool_call', {'name': APP + 'create_doc', 'arguments': {'title': 't'}}) == [
        (APP + 'create_doc', {'title': 't'})]
    assert [n for n, _ in g.unwrap('tool_call', {'calls': [{'name': 'a'}, {'name': 'b', 'arguments': {}}]})] == ['a', 'b']
    assert g.unwrap('terminal', {'command': 'ls'}) == [('terminal', {'command': 'ls'})]


def test_notes_detour_is_refused_and_redirected_to_the_connected_document_tool():
    value = guard(NOTES_REQUEST, {APP + 'create_doc', APP + 'list_docs', MEMORY, 'terminal', 'skill_view'})
    for name, arguments in (('skill_view', {'name': 'apple/apple-notes'}),
                            ('terminal', {'command': 'EDITOR=true memo notes -a'}),
                            ('terminal', {'command': 'osascript -e \'tell application "Notes" to make new note\''})):
        decision = value.before_call('s', name, arguments)
        assert decision.action == 'block' and decision.routed_tools == (APP + 'create_doc',)
        assert APP + 'create_doc' in decision.message
    assert value.before_call('s', 'tool_call', {'name': APP + 'create_doc', 'arguments': {}}).action == 'allow'
    assert 'create_doc' in value.turn_context('s')


def test_detours_are_allowed_without_a_matching_connected_tool_or_when_requested_explicitly():
    assert guard(NOTES_REQUEST, {APP + 'send_email', 'terminal'}).before_call(
        's', 'terminal', {'command': 'memo notes -a'}).action == 'allow'
    assert guard('Create a note in Apple Notes about Q2', {APP + 'create_doc'}).before_call(
        's', 'skill_view', {'name': 'apple-notes'}).action == 'allow'
    assert guard(NOTES_REQUEST, {APP + 'create_doc'}).before_call('s', 'terminal', {'command': 'ls -la'}).action == 'allow'


def test_github_skill_and_cli_are_redirected_to_connected_review_tools():
    value = guard('[2028-01-01] Inspect lantern#1602 and review its chronology changes.',
                  {APP + 'get_pr', APP + 'review_pr', APP + 'list_open_prs'})
    assert value.before_call('s', 'skill_view', {'name': 'software-development/github'}).routed_tools == (APP + 'review_pr',)
    assert value.before_call('s', 'terminal', {'command': 'gh pr view 1602'}).action == 'block'


def test_local_file_is_only_a_detour_for_a_document_request():
    tools = {APP + 'create_doc'}
    assert guard(NOTES_REQUEST, tools).before_call('s', 'write_file', {'path': 'n.md'}).action == 'block'
    assert guard('Summarise the Q2 plan for me', tools).before_call('s', 'write_file', {'path': 'n.md'}).action == 'allow'


def test_completion_verdict_needs_an_accepted_connected_write():
    value = guard(NOTES_REQUEST, {APP + 'create_doc', APP + 'list_docs'})
    value.before_call('s', APP + 'list_docs', {})
    value.after_call('s', APP + 'list_docs', {}, '{"result": "[]"}')
    assert value.verdict('s')['status'] == 'not_completed'
    assert 'NOT COMPLETED' in value.completion_notice('s')
    # Host-wrapped success whose body mentions "sandbox" is still a success.
    envelope = ('<untrusted_tool_result source="x">DATA\n{"result": "{\\"ok\\": true, \\"id\\": \\"d1\\", '
                '\\"body\\": \\"no Salesforce sandbox caveat\\"}"}\n</untrusted_tool_result>')
    value.before_call('s', 'tool_call', {'name': APP + 'create_doc', 'arguments': {'title': 'x'}})
    value.after_call('s', 'tool_call', {'name': APP + 'create_doc', 'arguments': {'title': 'x'}}, envelope)
    assert value.verdict('s') == {'status': 'completed', 'accepted': [APP + 'create_doc']}
    assert value.completion_notice('s') == ''


def test_rejected_write_and_question_turns():
    value = guard(NOTES_REQUEST, {APP + 'create_doc'})
    value.before_call('s', APP + 'create_doc', {})
    value.after_call('s', APP + 'create_doc', {}, {'isError': True, 'content': [{'type': 'text', 'text': 'bad'}]})
    assert value.verdict('s')['status'] == 'not_completed' and value.record('s')['failed_writes'] == [APP + 'create_doc']
    assert guard('What is on my calendar?', {APP + 'create_doc'}).verdict('s')['status'] == 'no_action_requested'


def test_verified_route_failure_is_remembered_across_sessions(tmp_path):
    path = tmp_path / 'routes.json'
    first = guard('Create a note about Q2', {'terminal'}, route_memory=g.RouteMemory(path))
    command = {'command': 'EDITOR=true memo notes -a'}
    assert first.before_call('s', 'terminal', command).action == 'allow'
    first.after_call('s', 'terminal', command, {'output': "xcrun: error: unable to load libxcrun (file system "
                                               "sandbox blocked open())", 'exit_code': 1})
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    later = guard('Create a note about Q3', {'terminal'}, route_memory=g.RouteMemory(path))
    decision = later.before_call('s', 'terminal', command)
    assert decision.action == 'block' and 'xcrun: error' in decision.message
    # A successful local command is never recorded as a failure.
    other = g.RouteMemory(tmp_path / 'other.json')
    guard('x', route_memory=other).after_call('s', 'terminal', {'command': 'gh pr list'}, {'output': 'ok', 'exit_code': 0})
    assert other.entries == {}


def test_commit_checkpoint_holds_each_write_tool_once_with_an_action_specific_recall_query():
    value = guard('Please check my calendar for Saturday, January 8, 2028 and, if open, add brunch to my calendar.',
                  {APP + 'create_calendar_event', MEMORY}, checkpoint=True)
    arguments = {'title': 'Brunch', 'start': '2028-01-08T11:00:00-06:00', 'end': '2028-01-08T12:30:00-06:00'}
    assert 'Held once' in value.turn_context('s')
    held = value.before_call('s', APP + 'create_calendar_event', arguments)
    assert held.action == 'block' and 'nothing was sent' in held.message
    assert 'Brunch' in held.message and 'Saturday' in held.message and 'T11' not in held.message
    assert value.before_call('s', APP + 'create_calendar_event', arguments).action == 'allow'
    email = g.recall_query(APP + 'send_email', {'to': 'vendorops@northwind.example', 'subject': 'Re: Scheduling',
                                               'body': 'Friday, September 18 at 2:00 PM works'})
    assert 'vendorops@northwind.example' in email and 'Friday' in email


def test_checkpoint_needs_visible_memory_and_block_budget_prevents_loops():
    assert guard(NOTES_REQUEST, {APP + 'create_doc'}, checkpoint=True).before_call('s', APP + 'create_doc', {}).action == 'allow'
    value = guard(NOTES_REQUEST, {APP + 'create_doc'}, max_blocks=2)
    outcomes = [value.before_call('s', 'terminal', {'command': 'memo notes -a'}).action for _ in range(3)]
    assert outcomes == ['block', 'block', 'allow']


class FakeContext:
    def __init__(self):
        self.hooks = {}

    def register_hook(self, name, callback):
        self.hooks[name] = callback


def load_staged(directory):
    spec = importlib.util.spec_from_file_location('atmem_action_guard_staged', directory / '__init__.py',
                                                  submodule_search_locations=[str(directory)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_staged_hermes_plugin_enforces_the_hook_sequence(tmp_path, monkeypatch):
    from atmem.adapters.hermes.action_guard_plugin import PLUGIN, stage
    home = tmp_path / 'home'
    directory = stage(home)
    assert (directory / 'plugin.yaml').read_text().startswith('name: ' + PLUGIN)
    with pytest.raises(FileExistsError):
        stage(home)
    monkeypatch.setenv('HERMES_HOME', str(home))
    module = load_staged(directory)
    monkeypatch.setattr(module, '_visible_tool_names', lambda: {APP + 'create_doc', MEMORY, 'terminal', 'skill_view'})
    ctx = FakeContext()
    binding = module.register(ctx)
    assert binding.policy.__file__.startswith(str(directory))  # host needs no AtMem import
    hooks = ctx.hooks
    assert set(hooks) == {'pre_llm_call', 'pre_tool_call', 'post_tool_call', 'transform_llm_output'}
    assert 'create_doc' in hooks['pre_llm_call'](session_id='a', user_message=NOTES_REQUEST)['context']
    blocked = hooks['pre_tool_call'](tool_name='skill_view', args={'name': 'apple/apple-notes'}, session_id='a')
    assert blocked['action'] == 'block' and APP + 'create_doc' in blocked['message']
    final = hooks['transform_llm_output'](response_text='Here is a ready-to-paste note.', session_id='a', turn_id='t1')
    assert final.endswith('Nothing above should be read as a confirmed application action.]')
    # Second session: checkpoint once, then the confirmed write completes the turn.
    hooks['pre_llm_call'](session_id='b', user_message=NOTES_REQUEST)
    call = {'name': APP + 'create_doc', 'arguments': {'title': 'Board review', 'body': 'x'}}
    assert hooks['pre_tool_call'](tool_name='tool_call', args=call, session_id='b')['action'] == 'block'
    assert hooks['pre_tool_call'](tool_name='tool_call', args=call, session_id='b') is None
    hooks['post_tool_call'](tool_name='tool_call', args=call, result='{"result": "{\\"ok\\": true}"}', session_id='b')
    assert hooks['transform_llm_output'](response_text='Created.', session_id='b', turn_id='t2') is None
    records = [json.loads(line) for line in (home / '.atmem/action-guard/outcomes.jsonl').read_text().splitlines()]
    assert [r['verdict']['status'] for r in records] == ['not_completed', 'completed']
    assert records[0]['decisions'][0]['route'] == 'skill:apple-notes'
    assert stat.S_IMODE((home / '.atmem/action-guard/outcomes.jsonl').stat().st_mode) == 0o600
