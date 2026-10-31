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
        assert decision.action == 'block' and decision.routed_tools == (APP + 'create_doc', APP + 'list_docs')
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
    assert value.before_call('s', 'skill_view', {'name': 'software-development/github'}).routed_tools == (
        APP + 'review_pr', APP + 'get_pr', APP + 'list_open_prs')
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
    assert 'vendorops' not in email and 'Friday' in email and 'Scheduling' in email  # general rule search


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
    assert set(hooks) == {'pre_llm_call', 'pre_tool_call', 'post_tool_call', 'transform_tool_result', 'transform_llm_output'}
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


@pytest.mark.parametrize('result, status', [
    ({'ok': False, 'error': 'quota'}, g.FAILED),
    (None, g.UNCONFIRMED),
    ('Local tools cannot be batched.', g.FAILED),
    ('done', g.UNCONFIRMED),
    ({'content': [{'type': 'text', 'text': '{"ok": true, "id": "d1"}'}]}, g.ACCEPTED),
    ('{"result": "{\\"id\\": \\"evt_1\\", \\"title\\": \\"Brunch\\"}"}', g.ACCEPTED),
    ({'content': [{'type': 'text', 'text': 'saved'}]}, g.UNCONFIRMED),
    ({'output': 'ok', 'exit_code': 0}, g.ACCEPTED),
])
def test_acceptance_needs_an_affirmative_marker(result, status):
    assert g.result_status(result) == status


def test_wrapper_with_several_writes_and_one_result_is_unconfirmed():
    value = guard(NOTES_REQUEST, {APP + 'create_doc', APP + 'post_doc_comment'})
    call = {'calls': [{'name': APP + 'create_doc', 'arguments': {}}, {'name': APP + 'post_doc_comment', 'arguments': {}}]}
    value.before_call('s', 'tool_call', call)
    value.after_call('s', 'tool_call', call, '{"result": "{\\"ok\\": true}"}')
    assert value.record('s')['accepted_writes'] == [] and value.verdict('s')['status'] == 'not_completed'
    itemised = guard(NOTES_REQUEST, {APP + 'create_doc', APP + 'post_doc_comment'})
    itemised.after_call('s', 'tool_call', call, {'results': [{'ok': True}, {'ok': False}]})
    assert itemised.record('s')['accepted_writes'] == [APP + 'create_doc']


def test_unrelated_accepted_write_does_not_complete_and_mixed_outcomes_are_partial():
    tools = {APP + 'create_doc', APP + 'send_email'}
    value = guard('Send this email to ops@example.com about the outage.', tools)
    value.after_call('s', APP + 'create_doc', {}, {'ok': True})
    value.after_call('s', APP + 'send_email', {}, {'ok': False})
    assert value.verdict('s')['status'] == 'not_completed' and 'did not match' in value.verdict('s')['reason']
    both = guard('Create a doc for the outage and email ops@example.com the link.', tools)
    both.after_call('s', APP + 'create_doc', {}, {'ok': True})
    both.after_call('s', APP + 'send_email', {}, 'Local tools cannot be batched.')
    assert both.verdict('s')['status'] == 'partial' and 'PARTIALLY COMPLETED' in both.completion_notice('s')
    both.after_call('s', APP + 'send_email', {}, {'ok': True, 'id': 'm1'})  # a successful retry clears it
    assert both.verdict('s')['status'] == 'completed'


def test_successful_explicit_local_action_gets_no_false_warning():
    value = guard('Create a note in Apple Notes about Q2', {APP + 'create_doc', 'terminal'})
    command = {'command': 'memo notes -a'}
    assert value.before_call('s', 'terminal', command).action == 'allow'
    value.after_call('s', 'terminal', command, {'output': 'Note added', 'exit_code': 0})
    assert value.verdict('s')['status'] == 'completed_local' and value.completion_notice('s') == ''
    assert guard('Create a note in Apple Notes about Q2', {APP + 'create_doc'}).completion_notice('s') == ''


def test_reads_and_unrelated_skills_are_not_redirected_to_write_tools():
    review = {APP + 'review_pr', APP + 'get_pr', APP + 'send_email'}
    assert guard('List my open GitHub PRs', review).before_call('s', 'terminal', {'command': 'gh pr list'}).action == 'allow'
    assert guard('Create a note about the Q2 plan', review).before_call(
        's', 'skill_view', {'name': 'google-workspace'}).action == 'allow'
    redirected = guard('Inspect lantern#1602 and review it', review).before_call('s', 'terminal', {'command': 'gh pr view 1602'})
    assert redirected.routed_tools == (APP + 'get_pr', APP + 'review_pr')


def test_finished_and_abandoned_sessions_are_released():
    value = g.ActionGuard(checkpoint=False, max_sessions=3)
    for index in range(5):
        value.begin_turn(f's{index}', NOTES_REQUEST, {APP + 'create_doc'})
    assert list(value.turns) == ['s2', 's3', 's4']
    assert value.finish('s4')['verdict']['status'] == 'not_completed' and 's4' not in value.turns


def test_success_to_one_recipient_does_not_clear_a_failure_to_another():
    value = guard('Email Alice and Bob the update.', {APP + 'send_email'})
    value.after_call('s', APP + 'send_email', {'to': 'alice@example.com', 'body': 'x'}, {'ok': True, 'id': 'm1'})
    value.after_call('s', APP + 'send_email', {'to': 'bob@example.com', 'body': 'x'}, {'ok': False})
    assert value.verdict('s')['status'] == 'partial'
    value.after_call('s', APP + 'send_email', {'to': 'bob@example.com', 'body': 'fixed'}, {'ok': True, 'id': 'm2'})
    assert value.verdict('s')['status'] == 'completed'  # retry to the same target clears it


@pytest.mark.parametrize('text', ['Could you email Alice the update?', 'Please send this to ops@example.com',
                                  '[2026-09-14] Can you please email the vendor a reply?'])
def test_polite_phrasing_keeps_explicit_destinations(text):
    value = guard(text, {APP + 'create_doc', APP + 'send_email'})
    assert 'email' in g.classify(text).destinations
    value.after_call('s', APP + 'create_doc', {}, {'ok': True, 'id': 'd1'})
    assert value.verdict('s')['status'] == 'not_completed'


def test_prerequisite_reads_need_a_connected_read_replacement():
    only_writer = guard('Inspect repo#12 and review its changes', {APP + 'review_pr'})
    assert only_writer.before_call('s', 'terminal', {'command': 'gh pr diff 12'}).action == 'allow'
    assert only_writer.before_call('s', 'skill_view', {'name': 'github'}).action == 'block'
    with_reader = guard('Inspect repo#12 and review its changes', {APP + 'review_pr', APP + 'get_pr'})
    assert with_reader.before_call('s', 'terminal', {'command': 'gh pr diff 12'}).routed_tools[0] == APP + 'get_pr'
    assert g.is_read_route('terminal', {'command': 'memo notes'}) and not g.is_read_route('terminal', {'command': 'memo notes -a'})
    assert not g.is_read_route('terminal', {'command': 'gh api repos/o/r/pulls/1/reviews -X POST'})


def test_single_call_batch_with_itemised_result_is_accepted():
    value = guard(NOTES_REQUEST, {APP + 'create_doc'})
    call = {'calls': [{'name': APP + 'create_doc', 'arguments': {'title': 't'}}]}
    value.after_call('s', 'tool_call', call, {'results': [{'ok': True, 'id': 'd1'}]})
    assert value.verdict('s')['status'] == 'completed'


def test_distinct_created_items_keep_separate_outcomes():
    value = guard('Create notes for Alice and Bob.', {APP + 'create_doc'})
    value.after_call('s', APP + 'create_doc', {'title': 'Alice', 'body': 'a'}, {'ok': False})
    value.after_call('s', APP + 'create_doc', {'title': 'Bob', 'body': 'b'}, {'ok': True, 'id': 'd2'})
    assert value.verdict('s')['status'] == 'partial'
    value.after_call('s', APP + 'create_doc', {'title': 'Alice', 'body': 'revised'}, {'ok': True, 'id': 'd3'})
    assert value.verdict('s')['status'] == 'completed'
    targetless = guard('Create two notes.', {APP + 'create_doc'})
    targetless.after_call('s', APP + 'create_doc', {'body': 'one'}, {'ok': False})
    targetless.after_call('s', APP + 'create_doc', {'body': 'two'}, {'ok': True, 'id': 'd4'})
    assert targetless.verdict('s')['status'] == 'partial'


@pytest.mark.parametrize('command, read', [
    ('gh pr diff 12', True), ('cd repo && gh pr diff 12', True),
    ('gh pr diff 12 && gh pr review 12 --approve', False), ('gh pr view 12; gh pr merge 12', False),
    ('gh pr view $(gh pr merge 12)', False), ('memo notes | cat', True), ('pwd', False),
    ('gh pr diff 12 & gh pr merge 12', False),
])
def test_read_exemption_requires_every_command_component_to_read(command, read):
    assert g.is_read_route('terminal', {'command': command}) is read


def test_compound_local_write_is_redirected_to_the_connected_writer():
    value = guard('Inspect repo#12 and review its changes', {APP + 'review_pr'})
    decision = value.before_call('s', 'terminal', {'command': 'gh pr diff 12 && gh pr review 12 --approve'})
    assert decision.action == 'block' and decision.routed_tools == (APP + 'review_pr',)


def test_host_rejected_wrapper_is_undispatched_not_a_failed_operation():
    assert g.result_status({"error": "tool_call calls[0] requires a 'name'"}) == g.UNDISPATCHED
    assert g.result_status({"error": "MCP server 'apps' is not connected"}) == g.FAILED
    value = guard(NOTES_REQUEST, {APP + 'create_doc'})
    bad = {'calls': [{'arguments': {'title': 'x'}, 'name': APP + 'create_doc'}, {'name': APP + 'create_doc'}]}
    value.after_call('s', 'tool_call', bad, '{"error": "tool_call takes exactly one entry for local tools; you sent 2."}')
    assert value.verdict('s')['reason'] == 'the host rejected the write call before dispatch'
    value.after_call('s', APP + 'create_doc', {'title': 'Board review'}, {'ok': True, 'id': 'd1'})
    assert value.verdict('s')['status'] == 'completed'


def test_update_retry_with_corrected_title_matches_the_same_record():
    value = guard('Update the launch doc title.', {APP + 'update_doc'})
    value.after_call('s', APP + 'update_doc', {'doc_id': 'd1', 'title': 'Rejected title'}, {'ok': False})
    value.after_call('s', APP + 'update_doc', {'doc_id': 'd1', 'title': 'Corrected title'}, {'ok': True, 'id': 'd1'})
    assert value.verdict('s')['status'] == 'completed'


def test_two_creates_in_one_destination_stay_distinct_and_send_retries_match():
    value = guard('Create issues for the login and logout bugs in org/app.', {APP + 'create_issue'})
    value.after_call('s', APP + 'create_issue', {'repo': 'org/app', 'title': 'Fix login'}, {'ok': False})
    value.after_call('s', APP + 'create_issue', {'repo': 'org/app', 'title': 'Fix logout'}, {'ok': True, 'id': 'i2'})
    assert value.verdict('s')['status'] == 'partial'
    send = guard('Email Bob the update.', {APP + 'send_email'})
    send.after_call('s', APP + 'send_email', {'to': 'bob@example.com', 'subject': 'Draft'}, {'ok': False})
    send.after_call('s', APP + 'send_email', {'to': 'bob@example.com', 'subject': 'Update'}, {'ok': True, 'id': 'm1'})
    assert send.verdict('s')['status'] == 'completed'


def test_record_numbers_are_repo_scoped_and_parent_ids_keep_creations_distinct():
    value = guard('Update issue 12 in both repos.', {APP + 'update_issue'})
    value.after_call('s', APP + 'update_issue', {'repo': 'org/one', 'issue_number': 12, 'title': 'a'}, {'ok': False})
    value.after_call('s', APP + 'update_issue', {'repo': 'org/two', 'issue_number': 12, 'title': 'a'}, {'ok': True, 'id': 12})
    assert value.verdict('s')['status'] == 'partial'
    slides = guard('Add intro and results slides to the deck.', {APP + 'add_slide'})
    slides.after_call('s', APP + 'add_slide', {'deck_id': 'd1', 'title': 'Intro'}, {'ok': False})
    slides.after_call('s', APP + 'add_slide', {'deck_id': 'd1', 'title': 'Results'}, {'ok': True, 'id': 's2'})
    assert slides.verdict('s')['status'] == 'partial'


def test_benchmark_settings_leave_the_user_turn_and_final_answer_untouched(tmp_path, monkeypatch):
    from atmem.adapters.hermes.action_guard_plugin import stage
    from benchmarks.dolphinbench.execution_profile import ROUTED_SETTINGS
    home = tmp_path / 'home'
    directory = stage(home, settings=ROUTED_SETTINGS)
    monkeypatch.setenv('HERMES_HOME', str(home))
    module = load_staged(directory)
    monkeypatch.setattr(module, '_visible_tool_names', lambda: {APP + 'create_doc', 'terminal', 'skill_view'})
    ctx = FakeContext()
    module.register(ctx)
    assert ctx.hooks['pre_llm_call'](session_id='a', user_message=NOTES_REQUEST) is None
    assert ctx.hooks['pre_tool_call'](tool_name='skill_view', args={'name': 'apple-notes'}, session_id='a')['action'] == 'block'
    assert ctx.hooks['transform_llm_output'](response_text='Draft only.', session_id='a', turn_id='t') is None
    record = json.loads((home / '.atmem/action-guard/outcomes.jsonl').read_text())
    assert record['verdict']['status'] == 'not_completed'  # still recorded for the report


def test_travel_bookings_have_a_destination():
    value = guard('[2026-09-14] Check the company travel policy and, if compliant, book flight quote flight_129 and hotel quote hotel_129.',
                  {APP + 'book_flight', APP + 'book_hotel'})
    assert 'travel' in g.classify('book the flight and hotel').domains
    assert value.routed_tools(value.turns['s']) == (APP + 'book_flight', APP + 'book_hotel')


def test_pending_reminder_follows_reads_until_the_write_is_accepted():
    value = guard('[2028-01-01] Inspect metrics-router#1318 and review its queue-control changes.',
                  {APP + 'get_pr', APP + 'review_pr', MEMORY})
    note = value.pending_reminder('s', APP + 'get_pr', {'pr_id': 'metrics-router#1318'})
    assert 'still pending' in note and APP + 'review_pr' in note
    assert value.pending_reminder('s', 'terminal', {'command': 'ls'}) == ''       # not a read of the app or memory
    assert value.pending_reminder('s', MEMORY, {'query': 'x'})
    value.after_call('s', APP + 'review_pr', {'pr_id': 'metrics-router#1318'}, {'ok': True, 'id': 'r1'})
    assert value.pending_reminder('s', APP + 'get_pr', {}) == ''                 # completed: no more reminders
    bounded = guard('Inspect repo#1 and review it.', {APP + 'get_pr', APP + 'review_pr'})
    assert [bool(bounded.pending_reminder('s', APP + 'get_pr', {})) for _ in range(4)] == [True, True, True, False]
    assert guard('What did repo#1 change?', {APP + 'get_pr', APP + 'review_pr'}).pending_reminder('s', APP + 'get_pr', {}) == ''
