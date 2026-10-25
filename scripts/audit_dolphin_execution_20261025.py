"""Offline evaluator-only audit of the recorded 2.3.10b1 campaign.

Never imports the agent, runs app tools, calls a model, or changes submissions.
Required-tool labels are evaluator inputs and must not enter agent prompts.
Run with a Python environment containing PyYAML.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile

import yaml


ZIP_SHA = '78788ad3455d04407c037706d3ff129d56eafff89beaac101f2a461cb58d7538'
UPSTREAM = '81cb6f8405b40a9e76089cef650806a80af06ea2'
APP_PREFIX = 'mcp__dolphinbench_apps__'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def function(call):
    return call.get('function', call)


def arguments(call):
    value = function(call).get('arguments', {})
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return {'unparsed': value}
    return value


def observed_app_tools(messages, default_settings):
    """Names actually shown to the model, including the deferred catalog."""
    for message in messages:
        if message.get('role') != 'assistant':
            continue
        tools = message.get('settings', default_settings).get('tools', [])
        if not tools:
            continue
        names = set()
        for tool in tools:
            fn = function(tool)
            if fn.get('name', '').startswith(APP_PREFIX):
                names.add(fn['name'][len(APP_PREFIX):])
            if fn.get('name') == 'tool_search':
                names.update(re.findall(r'- ' + APP_PREFIX + r'([A-Za-z0-9_]+):', fn.get('description', '')))
        return sorted(names)
    return []


def runtime_outputs(messages):
    for message in messages:
        if message.get('role') != 'tool':
            continue
        content = message.get('content', '')
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except ValueError:
                continue
        # Exclude read_file content: source code mentioning an error is not one.
        if isinstance(content, dict) and isinstance(content.get('output'), str):
            yield content['output']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--submission', required=True, type=Path)
    parser.add_argument('--rows', required=True, type=Path)
    parser.add_argument('--upstream', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    assert digest(args.submission) == ZIP_SHA, 'Unexpected submission bytes'
    revision = subprocess.check_output(['git', '-C', str(args.upstream), 'rev-parse', 'HEAD'], text=True).strip()
    assert revision == UPSTREAM
    manifest = json.loads((args.upstream / 'manifest.json').read_text())

    def authenticated(relative):
        path = args.upstream / relative
        assert digest(path) == manifest['files'][relative], relative
        return path.read_text()

    with zipfile.ZipFile(args.submission) as archive:
        package = json.loads(archive.read('tests.json'))
        recorded = package['tests']
    index = {r['id']: r for r in json.loads(args.rows.read_text())}
    assert len(recorded) == len(index) == 600
    assert {r['persona'] + '/' + r['test_id'] for r in recorded} == set(index)
    runtimes = {p: json.loads(authenticated(f'mock_mcp/runtime/{p}.json'))
                for p in ('morgan', 'alex', 'riley')}
    ledger = []
    for task in recorded:
        persona, tid = task['persona'], task['test_id']
        key = persona + '/' + tid
        public = index[key]
        spec = yaml.safe_load(authenticated(f'tests/{persona}/{tid}.yaml'))
        messages = task['messages']
        shown = observed_app_tools(messages, package['settings'])
        calls = [function(c) for m in messages for c in m.get('tool_calls', []) or []]
        terminal = [arguments(c).get('command', '') for c in calls if c.get('name') == 'terminal']
        outputs = list(runtime_outputs(messages))
        memo = any(re.search(r'\bmemo\s+notes\b', cmd) for cmd in terminal)
        osascript = any('osascript' in out and ('Operation not permitted' in out or 'PermissionError' in out)
                       for out in outputs)
        gh = any('not logged into any GitHub hosts' in out for out in outputs)
        expected = spec.get('expected_tool_calls', [])
        grade_tools = sorted({a['tool'] for a in spec['grade']['config']['assertions'] if a.get('tool')})
        active = runtimes[persona]['tests'][tid]['tool_config']['active_tools']
        trace = bool(task.get('app_calls'))
        assert trace == public['independent_app_trace'], key
        assert all(g['passed'] for g in task['grading']) == public['passed'], key
        assert sum(g['passed'] for g in task['grading']) == public['checks_passed'], key
        skills = [arguments(c).get('name') for c in calls if c.get('name') == 'skill_view']
        searches = [arguments(c).get('queries', []) for c in calls if c.get('name') == 'tool_search']
        ledger.append({
            'id': key, 'passed': public['passed'], 'independent_app_trace': trace,
            'checks_passed': public['checks_passed'], 'checks_total': public['checks_total'],
            'starts_create': re.sub(r'^\[[^]]*\]\s*', '', public['request']).startswith('Create '),
            'advertised_app_tools': shown, 'declared_active_tools': active,
            'evaluator_expected_tools': expected, 'evaluator_graded_tools': grade_tools,
            'expected_tools_not_advertised': sorted(set(expected) - set(shown)),
            'graded_tools_not_advertised': sorted(set(grade_tools) - set(shown)),
            'memo_notes_terminal_attempt': memo, 'osascript_runtime_permission_error': osascript,
            'memo_notes_and_os_error': memo and osascript, 'github_runtime_unauthenticated': gh,
            'loaded_skills': skills, 'tool_search_queries': searches,
            'workflow_guidance_present': any('Connected application workflow:' in str(m.get('content', ''))
                                             for m in messages if m.get('role') in ('system', 'developer')),
            'judge_response_recorded': any(g.get('messages') for g in task['grading']),
            'recovery_note': public['recovery_note'],
        })

    def group(items):
        return {'tasks': len(items), 'passed': sum(r['passed'] for r in items),
                'memo_notes_and_os_error': sum(r['memo_notes_and_os_error'] for r in items),
                'github_runtime_unauthenticated': sum(r['github_runtime_unauthenticated'] for r in items)}

    no_trace = [r for r in ledger if not r['independent_app_trace']]
    other_no_trace = [r for r in no_trace if not r['memo_notes_and_os_error'] and not r['github_runtime_unauthenticated']]
    summary = {
        'schema': 'atmem-dolphin-execution-audit-v1', 'submission_sha256': ZIP_SHA,
        'upstream_commit': revision, 'rows_sha256': digest(args.rows),
        'all': group(ledger), 'without_trace': group(no_trace),
        'with_trace': group([r for r in ledger if r['independent_app_trace']]),
        'traced_zero_check_failures': group([r for r in ledger if r['independent_app_trace'] and not r['passed'] and r['checks_passed'] == 0]),
        'traced_partial_check_failures': group([r for r in ledger if r['independent_app_trace'] and not r['passed'] and r['checks_passed'] > 0]),
        'failed_tasks_zero_checks': sum(not r['passed'] and r['checks_passed'] == 0 for r in ledger),
        'traced_failures_one_check_short': sum(r['independent_app_trace'] and not r['passed'] and r['checks_total'] - r['checks_passed'] == 1 for r in ledger),
        'without_trace_create_requests': sum(r['starts_create'] for r in no_trace),
        'without_trace_zero_checks': sum(r['checks_passed'] == 0 for r in no_trace),
        'without_trace_judge_response_recorded': sum(r['judge_response_recorded'] for r in no_trace),
        'other_no_trace_tasks': len(other_no_trace),
        'other_no_trace_with_create_doc_advertised': sum('create_doc' in r['advertised_app_tools'] for r in other_no_trace),
        'other_no_trace_create_requests_without_loaded_skills': sum(r['starts_create'] and not r['loaded_skills'] for r in other_no_trace),
        'workflow_guidance_present_tasks': sum(r['workflow_guidance_present'] for r in ledger),
        'expected_tools_not_advertised': [{k: r[k] for k in ('id', 'expected_tools_not_advertised', 'advertised_app_tools')}
                                         for r in ledger if r['expected_tools_not_advertised']],
        'graded_tools_not_advertised': [{k: r[k] for k in ('id', 'graded_tools_not_advertised', 'advertised_app_tools')}
                                       for r in ledger if r['graded_tools_not_advertised']],
        'no_trace_memo_errors_with_create_doc_advertised': sum(r['memo_notes_and_os_error'] and 'create_doc' in r['advertised_app_tools'] for r in no_trace),
        'no_trace_gh_errors_with_all_expected_advertised': sum(r['github_runtime_unauthenticated'] and not r['expected_tools_not_advertised'] for r in no_trace),
        'memo_error_task_ids_that_passed': [r['id'] for r in ledger if r['memo_notes_and_os_error'] and r['passed']],
        'github_error_task_ids_that_passed': [r['id'] for r in ledger if r['github_runtime_unauthenticated'] and r['passed']],
        'traced_failures_with_github_error': [r['id'] for r in ledger if r['independent_app_trace'] and not r['passed'] and r['github_runtime_unauthenticated']],
        'no_trace_skill_frequencies': dict(collections.Counter(s for r in no_trace for s in r['loaded_skills'])),
        'interpretation': 'Post hoc execution evidence only; no causal recovery estimate and no score changes.',
        'model_calls': 0, 'app_calls_executed': 0,
    }
    reference = {}
    reference_hashes = {}
    for persona in ('morgan', 'alex', 'riley'):
        relative = f'results/hermes/gpt-5.6-luna/mem0/{persona}/tests.json'
        raw = subprocess.check_output(['git', '-C', str(args.upstream), 'show', f'{UPSTREAM}:{relative}'])
        reference_hashes[relative] = hashlib.sha256(raw).hexdigest()
        for row in json.loads(raw)['tests']:
            reference[persona + '/' + str(row['id']).zfill(3)] = row
    assert len(reference) == 600 and sum(r['passed'] for r in reference.values()) == 424
    assert all(re.sub(r'^\[[^]]*\]\s*', '', index[k]['request']) == r['request']
               for k, r in reference.items())
    summary['published_reference_descriptive_only'] = {
        'source_commit': UPSTREAM, 'file_sha256': reference_hashes,
        'all_600_request_texts_match_after_date_prefix_removal': True,
        'reference_passed': 424,
        'reference_passes_on_our_83_no_trace_tasks': sum(reference[r['id']]['passed'] for r in no_trace),
        'reference_passes_on_our_35_no_trace_memo_errors': sum(reference[r['id']]['passed'] for r in no_trace if r['memo_notes_and_os_error']),
        'reference_passes_on_our_6_no_trace_github_errors': sum(reference[r['id']]['passed'] for r in no_trace if r['github_runtime_unauthenticated']),
        'reference_outcomes_on_two_fixture_mismatches': {k: reference[k]['passed'] for k in ('morgan/085', 'morgan/130')},
        'matched_runtime_or_memory_only_causal_comparison': False,
    }
    pilot_groups = {
        'failed_notes_route_35': sorted(r['id'] for r in no_trace if r['memo_notes_and_os_error']),
        'failed_github_route_6': sorted(r['id'] for r in no_trace if r['github_runtime_unauthenticated']),
        'fixture_negative_controls_2': ['morgan/085', 'morgan/130'],
        'already_recovered_notes_passes_5': summary['memo_error_task_ids_that_passed'],
    }
    selected = {key for group_ids in pilot_groups.values() for key in group_ids}
    def pilot_order(row):
        return hashlib.sha256(('dolphin-execution-pilot-20261025:' + row['id']).encode()).hexdigest()
    draft_controls = sorted((r for r in other_no_trace if r['starts_create'] and not r['loaded_skills']), key=pilot_order)[:2]
    google_control = sorted((r for r in other_no_trace if 'google-workspace' in r['loaded_skills']), key=pilot_order)[:1]
    pilot_groups['other_no_trace_controls_4'] = [r['id'] for r in draft_controls + google_control] + ['morgan/129']
    selected.update(pilot_groups['other_no_trace_controls_4'])
    for name, passed, zero, size in [('other_traced_zero_check_failures_2', False, True, 2),
                                     ('other_traced_partial_failures_2', False, False, 2),
                                     ('other_passes_4', True, None, 4)]:
        candidates = sorted((r for r in ledger if r['id'] not in selected
                             and r['independent_app_trace'] and r['passed'] == passed
                             and (zero is None or (r['checks_passed'] == 0) == zero)), key=pilot_order)
        pilot_groups[name] = [r['id'] for r in candidates[:size]]
        selected.update(pilot_groups[name])
    assert len(selected) == sum(map(len, pilot_groups.values())) == 60
    pilot = {'schema': 'dolphin-execution-diagnostic-pilot-v1', 'selection_revision': 2,
             'revision_date': '2026-10-26', 'revision_reason': 'Separate traced zero-check and partial-check failures before any pilot model calls.',
             'groups': pilot_groups,
             'selection_seed': 'dolphin-execution-pilot-20261025',
             'tasks': 60, 'submission_sha256': ZIP_SHA, 'upstream_commit': UPSTREAM,
             'post_hoc_diagnostic_not_holdout': True,
             'actor_must_not_receive_evaluator_labels_or_group_membership': True}
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    (args.output / 'task-ledger.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in ledger))
    (args.output / 'pilot-selection.json').write_text(json.dumps(pilot, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
