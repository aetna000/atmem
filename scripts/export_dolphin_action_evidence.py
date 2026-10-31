"""Publish action/check evidence by replaying saved upstream judgments offline.

No reader or judge requests are made. Saved grades are assertions to verify, not
inputs to a new score. Failure categories are transparent diagnostic annotations;
an omitted fact is not automatically proof of a retrieval failure.
"""
import argparse
import collections
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

READ = re.compile(r'^(list|get|read|search|find|lookup|check|view|fetch)_')
READ_EXCEPTIONS = {'vector_search', 'query_experiment_results', 'metrics_fetch_batch'}


def embedded_objects(value, depth=0):
    if depth > 10:
        return
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from embedded_objects(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            yield from embedded_objects(child, depth + 1)
    elif isinstance(value, str):
        for position in [0] + [i for i, c in enumerate(value) if c in '{['][:4]:
            try:
                parsed, _ = json.JSONDecoder().raw_decode(value[position:])
            except ValueError:
                continue
            yield from embedded_objects(parsed, depth + 1)
            return


def classification(action):
    """Conservative, inspectable post-hoc triage; never alter a verdict."""
    if action['passed']:
        return None, 'passed'
    if not action['call_indices']:
        return 'no_call', 'No recorded application call for the required tool.'
    failing = [e for c in action['checks'] for e in c['call_evaluations'] if not e['ok']]
    mechanical = [c for c in action['checks'] if c['kind'] == 'mechanical'
                  and c['call_evaluations'] and not any(e['ok'] for e in c['call_evaluations'])]
    if mechanical:
        return 'wrong_value', 'A mechanical requirement failed for every candidate call.'
    reason = ' '.join(e['reason'] for e in failing).lower()
    if re.search(r'\b(omits?|missing|does not (?:state|say|include|mention|name)|fails to (?:state|include|mention)|not (?:stated|included|mentioned|specified))\b', reason):
        return 'missing_required_fact', 'Saved judge reason describes required meaning absent from the action; memory delivery is assessed separately.'
    if re.search(r'\b(wording|explicit|precision|ambiguous|verbatim|exact|does not explicitly|not equivalent|rather than|instead of)\b', reason):
        return 'wording_or_precision', 'Saved judge reason flags specificity, wording, equivalence or ambiguity.'
    if re.search(r'\b(wrong|incorrect|contradict|different|inaccurate)\w*\b', reason):
        return 'wrong_value', 'Saved judge reason describes an incorrect or conflicting value.'
    return 'unresolved_content', 'Saved evidence does not support a more specific deterministic annotation.'


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--upstream', type=Path, required=True)
    parser.add_argument('--baseline-zip', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--annotations', type=Path, default=Path(__file__).resolve().parents[1] / 'docs/benchmarks/evidence/dolphin-routed4-20261101/action-annotations.json')
    args = parser.parse_args()
    sys.path.insert(0, str(args.upstream))
    from harness.submission import clean_message, read_release, record_settings, validate, write_zip
    from graders.judge_recording import replay_judge
    from graders.mechanical import grade_tool_trace
    from graders.explicit import _evaluate
    releases = read_release(args.upstream)
    annotations = json.loads(args.annotations.read_text())
    specs = {p + '/' + str(t['id']).zfill(3): t for p, v in releases.items() for t in v['tests']}
    run = args.run_dir
    grades = sorted(p for p in (run / 'grades').glob('*/*.json') if not p.name.startswith('._'))
    if {p.parent.name + '/' + p.stem for p in grades} != set(specs) or len(grades) != 600:
        raise ValueError('Exactly 600 unique original task IDs required')
    tasks, actions, checks_out, tests = [], [], [], []
    test_settings = judge_settings = None
    for path in grades:
        key = path.parent.name + '/' + path.stem
        grade = json.loads(path.read_text())
        execution = json.loads((run / 'tests' / (key + '.json')).read_text())
        row = copy.deepcopy(execution['row'])
        row['messages'] = [clean_message(m) for m in row['messages']]
        grading = [{**c, **({'messages': [clean_message(m) for m in c['messages']]} if 'messages' in c else {})} for c in grade['checks']]
        messages = [m for c in grading for m in c.get('messages', [])]
        config = copy.deepcopy(specs[key]['grade']['config'])
        config['raise_on_judge_error'] = True
        with replay_judge(messages, grade['settings']):
            evaluated = grade_tool_trace(row.get('app_calls', []), config, test_message=specs[key]['test'])
        if [c['passed'] for c in grading] != [c['ok'] for c in evaluated['details']]:
            raise ValueError('Offline replay differs from retained grades: ' + key)
        grouped = collections.OrderedDict()
        for detail in evaluated['details']:
            assertion = detail['assertion']
            action_id = assertion.get('action_id') or 'trace:' + detail['name']
            item = grouped.setdefault(action_id, {'task_id': key, 'action_id': action_id,
                'tool': assertion['tool'], 'kind': 'read' if READ.match(assertion['tool']) or assertion['tool'] in READ_EXCEPTIONS else 'write',
                'checks': [], 'trace_wide': not bool(assertion.get('action_id'))})
            check = {'task_id': key, 'action_id': action_id, 'check_id': detail['name'],
                     'kind': 'judged' if assertion['type'] == 'field_llm_judge' else 'mechanical',
                     'assertion': assertion, 'passed': detail['ok'], 'group_reason': detail['reason'],
                     'matched_call_index': detail['matched_call_index'],
                     'call_evaluations': detail['call_evaluations']}
            if not assertion.get('action_id') and assertion['type'] == 'field_equals_all_calls':
                check['call_evaluations'] = [dict(zip(('ok', 'reason', 'value'), _evaluate(assertion, c, specs[key]['test'], config.get('today', ''))), call_index=i)
                    for i, c in enumerate(row.get('app_calls', [])) if c['tool'] == assertion['tool']]
            item['checks'].append(check); checks_out.append(check)
        for item in grouped.values():
            item['passed'] = all(c['passed'] for c in item['checks'])
            candidates = [i for i, c in enumerate(row.get('app_calls', [])) if c['tool'] == item['tool']]
            item['call_indices'] = candidates
            eligible = [i for i in candidates if all(any(e['call_index'] == i and e['ok'] for e in c['call_evaluations']) for c in item['checks'])]
            item['eligible_call_indices'] = eligible
            item['single_call_satisfied_all_checks'] = bool(eligible) if not item['trace_wide'] else None
            item['matched_call_index'] = item['checks'][0]['matched_call_index']
            item['failure_class'], item['classification_basis'] = classification(item)
            item['classification_method'] = 'deterministic diagnostic rules; original upstream verdict unchanged'
            item['remembered_rule_not_in_write'] = None
            item['memory_delivery_status'] = 'requires source-linked review; not inferred from judge failure'
            if item['kind'] == 'write' and not item['passed'] and not item['trace_wide']:
                if key in annotations['overrides_by_task']:
                    item['failure_class'] = annotations['overrides_by_task'][key]
                    item['classification_method'] = 'Post-hoc review of saved judge reasons; original verdict unchanged'
                proof = annotations['delivered_rule_omissions'].get(key)
                if proof:
                    message = row['messages'][proof['message_index']]
                    source = next(s for s in releases[row['persona']]['sessions'] if s['id'] == proof['source_session'])
                    facts = [v for v in embedded_objects(message.get('content', '')) if v.get('quote') == proof['quote'] and v.get('session') == proof['source_session']]
                    if message['role'] != 'tool' or not facts or proof['quote'] not in '\n'.join(source['messages']):
                        raise ValueError('Source-linked delivery annotation not supported: ' + key)
                    if not any(c['kind'] == 'judged' and any(not e['ok'] for e in c['call_evaluations']) for c in item['checks']):
                        raise ValueError('Missing original failed judged criterion: ' + key)
                    call_positions = []
                    held_positions = []
                    for i, m in enumerate(row['messages']):
                        for call in m.get('tool_calls', []):
                            if not call.get('name', '').endswith('__' + item['tool']):
                                continue
                            replies = [v for v in row['messages'][i+1:] if v.get('role') == 'tool' and v.get('tool_call_id') == call['id']]
                            if len(replies) != 1:
                                raise ValueError('Ambiguous write outcome in delivery proof')
                            if 'Held once before an external write (nothing was sent).' in str(replies[0].get('content', '')):
                                held_positions.append(i)
                            else:
                                call_positions.append(i)
                    if not call_positions or proof['message_index'] >= min(call_positions):
                        raise ValueError('Delivery must precede the dispatched write')
                    item['memory_delivery_evidence'] = {**proof, 'write_message_index': min(call_positions), 'checkpoint_hold_message_indices': held_positions}
                    item['remembered_rule_not_in_write'] = True
                    item['memory_delivery_status'] = 'Source quote delivered before dispatched write; saved judge says required rule not fully carried into action'
                    item['failure_class'] = 'missing_remembered_fact'
                    item['classification_method'] = 'Source-linked post-hoc review, checked against reader-visible tool response, original source quote and saved failed judge criterion'
            actions.append(item)
        final = next((m.get('content', '') for m in reversed(row['messages']) if m['role'] == 'assistant' and m.get('content')), '')
        tasks.append({'task_id': key, 'persona': row['persona'], 'test_id': row['test_id'],
                      'request': specs[key]['test'], 'passed': evaluated['passed'],
                      'checks_passed': evaluated['passed_checks'], 'checks_total': evaluated['total_checks'],
                      'duration_ms': row['duration_ms'], 'final_response': final,
                      'action_ids': list(grouped), 'app_calls_json': json.dumps(row.get('app_calls', []), ensure_ascii=False),
                      'actions_json': json.dumps(list(grouped.values()), ensure_ascii=False),
                      'recovery_note': 'Original read-only disk-failed attempt preserved; owner-authorized retry.' if key == 'riley/017' else 'Offline evidence reconstruction, no app-action replay.' if key == 'morgan/020' else ''})
        row['grading'] = grading
        test_settings = record_settings(test_settings, execution['settings'], [row], 'test settings')
        effective_judge = {'max_completion_tokens': 8000, 'response_format': {'type': 'json_object'}, **grade['settings']}
        if judge_settings is not None and judge_settings != effective_judge:
            raise ValueError('Judge settings changed')
        judge_settings = effective_judge
        tests.append(row)
    with zipfile.ZipFile(args.baseline_zip) as archive:
        ingestion = json.loads(archive.read('ingestion.json'))
    document = {'settings': test_settings, 'judge_settings': judge_settings, 'tests': tests, 'total_cost_usd': 0}
    args.output.mkdir(parents=True, exist_ok=True)
    upstream_validation = validate(ingestion, document, releases)
    destination = args.output / 'submission.zip'
    if destination.exists():
        with zipfile.ZipFile(destination) as archive:
            if json.loads(archive.read('ingestion.json')) != ingestion or json.loads(archive.read('tests.json')) != document:
                raise ValueError('Existing submission differs; preserve it and choose a new output')
    else:
        write_zip(destination, ingestion, document, releases)
    write_json(args.output / 'validation.json', upstream_validation)
    write_json(args.output / 'actions.json', actions)
    write_json(args.output / 'checks.json', checks_out)
    for name, values in [('tasks', tasks), ('actions', actions), ('checks', checks_out)]:
        path = args.output / 'data' / (name + '.jsonl'); path.parent.mkdir(exist_ok=True)
        with path.open('w') as stream:
            for value in values:
                # Nested arrays of per-call diagnostics are JSON text in flat viewer configs.
                if name != 'tasks':
                    value = {k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in value.items()}
                stream.write(json.dumps(value, ensure_ascii=False) + '\n')
    required = [a for a in actions if not a['trace_wide']]
    trace = [a for a in actions if a['trace_wide']]
    classes = collections.Counter(a['failure_class'] for a in required if a['kind'] == 'write' and not a['passed'])
    summary = {'tasks': len(tasks), 'passed': sum(t['passed'] for t in tasks),
               'action_groups': len(required), 'trace_constraints': len(trace), 'checks': len(checks_out),
               'actions_by_kind': {kind: {'passed':sum(a['passed'] for a in required if a['kind']==kind), 'failed':sum(not a['passed'] for a in required if a['kind']==kind)} for kind in ['read','write']},
               'trace_constraints_passed': sum(a['passed'] for a in trace),
               'failed_writes_by_class': dict(classes),
               'remembered_rule_not_in_write': {'confirmed': sum(a['remembered_rule_not_in_write'] is True for a in required), 'not_established': sum(a['kind']=='write' and not a['passed'] and a['remembered_rule_not_in_write'] is None for a in required)},
               'validation': 'unchanged upstream offline judge replay; zero new model calls',
               'submission_sha256': hashlib.sha256((args.output / 'submission.zip').read_bytes()).hexdigest()}
    write_json(args.output / 'action-summary.json', summary)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
