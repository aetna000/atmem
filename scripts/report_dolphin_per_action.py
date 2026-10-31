"""Per-action DolphinBench report: one row per required action, reads and writes separated.

The upstream grader (graders/explicit.py) groups checks by ``action_id`` and accepts
an action only when one distinct call satisfies every check in that group; otherwise
every check in the group is recorded as failed. Saved per-check flags therefore do
not show which check broke. This report regroups checks by action, re-evaluates the
mechanical checks against the recorded application calls with the grader's own
``_evaluate`` (no model call), and takes judged-check reasons from the saved judge
responses. Each failed action gets a class:

- ``no_call``: the action's tool was never called;
- ``call_failed``: called, but no call returned ``result.ok`` true;
- ``wrong_value``: a call succeeded but a mechanical field check fails on every call;
- ``judged_content``: mechanical checks pass on some call, a judged criterion failed;
- ``unknown``: none of the above could be established.

Inputs: the published submission ``tests.json`` or an AtMem run directory.

    python scripts/report_dolphin_per_action.py --upstream DOLPHINBENCH --submission tests.json --output report.json
    python scripts/report_dolphin_per_action.py --upstream DOLPHINBENCH --run-dir RUN --output report.json
"""
import argparse
import collections
import json
import re
import sys
from pathlib import Path

READ_TOOL = re.compile(r'^(list|get|read|search|find|lookup|check|view|fetch)_')


def load_tasks(upstream):
    import yaml
    tasks = {}
    for path in sorted(Path(upstream, 'tests').glob('*/*.yaml')):
        value = yaml.safe_load(path.read_text())
        config = value['grade']['config']
        tasks[f'{path.parent.name}/{str(value["id"]).zfill(3)}'] = {
            'request': value.get('test', ''), 'today': config.get('today', ''), 'assertions': config['assertions']}
    return tasks


def submission_records(path):
    for test in json.loads(Path(path).read_text())['tests']:
        grading = test['grading']
        checks = grading['checks'] if isinstance(grading, dict) else grading
        yield f"{test['persona']}/{str(test['test_id']).zfill(3)}", checks, test.get('app_calls', [])


def run_records(run_dir):
    run_dir = Path(run_dir)
    for grade in sorted(run_dir.glob('grades/*/*.json')):
        if grade.name.startswith('._'):
            continue
        key = f'{grade.parent.name}/{grade.stem}'
        log = run_dir / 'apps' / key / 'calls.jsonl'
        calls = [json.loads(line) for line in log.read_text().splitlines() if line.strip()] if log.exists() else []
        yield key, json.loads(grade.read_text())['checks'], calls


def judge_reason(check):
    """The saved judge verdict reason for a judged check, when present."""
    for message in reversed(check.get('messages') or []):
        if message.get('role') == 'assistant':
            try:
                value = json.loads(message.get('content') or '{}')
            except ValueError:
                return str(message.get('content'))[:300]
            if isinstance(value.get('results'), list):
                return '; '.join(str(r.get('reason', '')) for r in value['results'])[:400]
            return str(value.get('reason', ''))[:400]
    return ''


def classify(group, calls, evaluate, today, request):
    tool = group['tool']
    tool_calls = [c for c in calls if c.get('tool') == tool]
    if not tool_calls:
        return 'no_call', []
    if not any(isinstance(c.get('result'), dict) and c['result'].get('ok') is not False for c in tool_calls):
        return 'call_failed', []
    mechanical = [a for a in group['assertions'] if a['type'] != 'field_llm_judge'
                  and a['type'] not in {'tool_called', 'tool_success_count', 'tool_call_count', 'field_equals_all_calls'}]
    failing_everywhere = []
    for assertion in mechanical:
        if not any(evaluate(assertion, call, request, today)[0] for call in tool_calls):
            failing_everywhere.append(assertion['check_id'])
    if failing_everywhere:
        return 'wrong_value', failing_everywhere
    if any(a['type'] == 'field_llm_judge' for a in group['assertions']):
        return 'judged_content', [a['check_id'] for a in group['assertions'] if a['type'] == 'field_llm_judge']
    return 'unknown', []


def report(tasks, records, evaluate):
    rows = []
    for key, checks, calls in records:
        task = tasks[key]
        passed_flags = {c['check']: bool(c.get('passed')) for c in checks}
        by_index = {c['check']: c for c in checks}
        groups = collections.OrderedDict()
        for index, assertion in enumerate(task['assertions']):
            action = assertion.get('action_id') or f"{key}:{assertion['tool']}"
            group = groups.setdefault(action, {'action_id': action, 'tool': assertion['tool'], 'indexes': [],
                                               'assertions': []})
            group['indexes'].append(index)
            group['assertions'].append(assertion)
        actions = []
        for action, group in groups.items():
            passed = all(passed_flags.get(i, False) for i in group['indexes'])
            row = {'action_id': action, 'tool': group['tool'],
                   'kind': 'read' if READ_TOOL.match(group['tool']) else 'write',
                   'checks': len(group['indexes']), 'passed': passed}
            if not passed:
                row['failure_class'], row['failing_checks'] = classify(group, calls, evaluate, task['today'],
                                                                       task['request'])
                reasons = [judge_reason(by_index.get(i, {})) for i, a in zip(group['indexes'], group['assertions'])
                           if a['type'] == 'field_llm_judge']
                row['judge_reasons'] = [r for r in reasons if r]
            actions.append(row)
        rows.append({'id': key, 'passed': all(a['passed'] for a in actions), 'actions': actions})
    return rows


def summarize(rows):
    actions = [a for r in rows for a in r['actions']]
    by = collections.Counter((a['kind'], a['passed']) for a in actions)
    classes = collections.Counter((a['kind'], a.get('failure_class')) for a in actions if not a['passed'])
    return {'tasks': len(rows), 'tasks_passed': sum(r['passed'] for r in rows), 'actions': len(actions),
            'actions_by_kind': {f'{k}_{"passed" if p else "failed"}': n for (k, p), n in sorted(by.items())},
            'failed_actions_by_class': {f'{k}:{c}': n for (k, c), n in sorted(classes.items())}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream', type=Path, required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--submission', type=Path)
    source.add_argument('--run-dir', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.upstream))
    from graders.explicit import _evaluate
    records = submission_records(args.submission) if args.submission else run_records(args.run_dir)
    rows = report(load_tasks(args.upstream), records, _evaluate)
    value = {'format': 'atmem-dolphin-per-action-report-v1', 'summary': summarize(rows), 'rows': rows}
    args.output.write_text(json.dumps(value, indent=1))
    print(json.dumps(value['summary'], indent=1))


if __name__ == '__main__':
    main()
