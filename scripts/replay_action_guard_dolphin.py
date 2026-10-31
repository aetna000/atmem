"""Offline replay of the AtMem action guard over recorded DolphinBench transcripts.

Counterfactual-free accounting only: for each recorded conversation it reports
the first call the router would have refused and the completion verdict the
guard would have reported. It makes no model, application or grading calls and
does not claim that a refused detour would have become a passing task.

    python scripts/replay_action_guard_dolphin.py --tests tests.json \
        --ledger docs/benchmarks/evidence/dolphin-execution-audit-20261025/task-ledger.jsonl \
        --output replay.json
"""
import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from atmem.action_guard import ActionGuard, unwrap, is_connected  # noqa: E402

APP = 'mcp__dolphinbench_apps__'
MEMORY = ('mcp__atmem_discovery__memory_search', 'mcp__atmem_discovery__memory_inspect')


def replay(test, ledger_row):
    guard = ActionGuard(checkpoint=False)
    messages = test['messages']
    request = next((m['content'] for m in messages if m.get('role') == 'user'), '')
    visible = {APP + n for n in ledger_row.get('advertised_app_tools', [])} | set(MEMORY)
    for message in messages:
        for call in message.get('tool_calls') or []:
            for name, _ in unwrap(call['name'], call.get('arguments')):
                if is_connected(name):
                    visible.add(name)
    guard.begin_turn('s', request, visible)
    first_block = None
    results = [m for m in messages if m.get('role') == 'tool']
    position = 0
    for message in messages:
        for call in message.get('tool_calls') or []:
            decision = guard.before_call('s', call['name'], call.get('arguments') or {})
            result = results[position]['content'] if position < len(results) else ''
            position += 1
            if decision.action == 'block' and first_block is None:
                first_block = {'tool': call['name'], 'route': decision.route,
                               'routed_tools': list(decision.routed_tools)}
            guard.after_call('s', call['name'], call.get('arguments') or {}, result)
    record = guard.record('s')
    return {'id': ledger_row['id'], 'intent': record['intent'], 'first_block': first_block,
            'verdict': record['verdict']['status'], 'accepted_writes': record['accepted_writes']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tests', required=True)
    parser.add_argument('--ledger', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    tests = json.loads(Path(args.tests).read_text())['tests']
    ledger = {r['id']: r for r in map(json.loads, Path(args.ledger).read_text().splitlines())}
    rows = []
    for test in tests:
        key = f"{test['persona']}/{test['test_id']}"
        rows.append({**replay(test, ledger[key]), 'ledger': ledger[key]})

    def cohort(row):
        led = row['ledger']
        if led['passed']:
            return 'pass'
        if not led['independent_app_trace']:
            return 'untraced_zero' if led['checks_passed'] == 0 else 'untraced_partial'
        return 'traced_zero' if led['checks_passed'] == 0 else 'traced_partial'

    summary = collections.defaultdict(collections.Counter)
    routes = collections.Counter()
    for row in rows:
        group = cohort(row)
        led = row['ledger']
        summary[group]['tasks'] += 1
        summary[group]['detour_blocked'] += bool(row['first_block'])
        summary[group]['action_intent'] += row['intent']['action']
        summary[group]['flagged_not_completed'] += row['verdict'] == 'not_completed'
        if led['memo_notes_and_os_error']:
            summary[group]['notes_error_tasks'] += 1
            summary[group]['notes_error_blocked'] += bool(row['first_block'])
        if led['github_runtime_unauthenticated']:
            summary[group]['github_auth_tasks'] += 1
            summary[group]['github_auth_blocked'] += bool(row['first_block'])
        if led['starts_create']:
            summary[group]['starts_create'] += 1
            summary[group]['starts_create_intent'] += row['intent']['action']
        if row['first_block']:
            routes[(group, row['first_block']['route'])] += 1
    output = {'format': 'atmem-action-guard-dolphin-replay-v1', 'tasks': len(rows),
              'cohorts': {k: dict(v) for k, v in sorted(summary.items())},
              'first_block_routes': [{'cohort': g, 'route': r, 'tasks': n} for (g, r), n in routes.most_common()],
              'passing_tasks_with_block': [{'id': r['id'], 'first_block': r['first_block']}
                                           for r in rows if r['ledger']['passed'] and r['first_block']],
              'passing_tasks_flagged_not_completed': [r['id'] for r in rows
                                                      if r['ledger']['passed'] and r['verdict'] == 'not_completed'],
              'rows': [{k: v for k, v in r.items() if k != 'ledger'} for r in rows]}
    Path(args.output).write_text(json.dumps(output, indent=1, sort_keys=True))
    print(json.dumps({k: output[k] for k in ('tasks', 'cohorts')}, indent=1))
    print('first-block routes:', output['first_block_routes'][:20])
    print('passing tasks with a block:', len(output['passing_tasks_with_block']))
    print('passing tasks flagged not completed:', len(output['passing_tasks_flagged_not_completed']))


if __name__ == '__main__':
    main()
