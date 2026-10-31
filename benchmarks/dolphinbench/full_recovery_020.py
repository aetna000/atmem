"""Offline reconstruction of the interrupted task; never dispatch an action."""
from __future__ import annotations

import json
import math
import copy
import os
from pathlib import Path
import sqlite3
import tempfile
import time
from contextlib import closing

from .export import export_interaction
from .pilot_recovery import _decode_json, _jsonl, _same, _state_contains, copy_exact, inventory
from .readiness import admit, identity, load_condition, pin, read, save, sha, verify_pin
from .recording import fingerprint, micros

TASK = 'morgan/020'
APP_TOOL = 'mcp__dolphinbench_apps__create_doc'
CHECKPOINT_PREFIX = 'Held once before an external write (nothing was sent).'
ROOT = Path(__file__).resolve().parents[2]
SCHEMA = 'dolphin-full020-recovery-epoch-v1'
ALLOWED = frozenset({'benchmarks/dolphinbench/export.py',
    'benchmarks/dolphinbench/full_recovery_020.py',
    'benchmarks/dolphinbench/pilot_readiness.py', 'benchmarks/dolphinbench/readiness.py',
    'scripts/launch_dolphin_readiness.py', 'tests/benchmarking/test_dolphinbench_export.py',
    'tests/benchmarking/test_dolphin_full_recovery_020.py'})


def _tool_result(message, name):
    content = message.get('content')
    prefix = '<untrusted_tool_result source="' + name + '">\n'
    if not isinstance(content, str) or not content.startswith(prefix) or not content.endswith('\n</untrusted_tool_result>'):
        raise ValueError('Expected original native tool-result wrapper')
    return _decode_json(content.split('\n\n', 1)[1].removesuffix('\n</untrusted_tool_result>'))


def reconstruct(parent, witness_path, spec, default_sources):
    """Rebuild only observed task 020; verify native, app and format evidence.

    Caller verifies the frozen source, task inventory and ledger separately.
    Nothing is written, graded, executed or dispatched here.
    """
    from harness.submission import check_settings, check_messages, grading_calls
    from graders.mechanical import load_tool_calls

    parent, witness_path = Path(parent).resolve(), Path(witness_path).resolve(strict=True)
    native = parent / 'native/tests' / TASK
    process_path = native / 'process.json'
    process = read(process_path)
    results = [_decode_json(line) for line in process['stdout'].splitlines() if line.startswith('{')]
    results = [r for r in results if r.get('type') == 'result']
    if process.get('exit_code') != 0 or len(results) != 1 or results[0].get('exit_code') != 0:
        raise ValueError('Unique successful native process result required')
    duration, session = results[0].get('duration_ms'), results[0].get('session_id')
    if type(duration) not in (int, float) or not math.isfinite(duration) or duration <= 0 or not session:
        raise ValueError('Original native duration and session required')
    events = _jsonl(witness_path)
    if not events or any(e.get('session_id') != session for e in events):
        raise ValueError('Native lifecycle witness differs from process session')
    context_path = native / 'context-delivery.json'
    context = read(context_path)
    if (context.get('mode') != 'installed AtMem API to native ephemeral_system_prompt'
            or context.get('actual_native_process_exit_code') != 0):
        raise ValueError('Original product-context delivery proof required')
    intent_path, outcome_path = native / 'app-evidence/intent.json', native / 'app-evidence/outcome.json'
    intent, outcome = read(intent_path), read(outcome_path)
    if outcome.get('completed') is not False or len(outcome.get('artifacts', [])) != 2:
        raise ValueError('Expected original incomplete journal and two app snapshots')
    snapshots = {verify_pin(a).name: verify_pin(a) for a in outcome['artifacts']}
    if set(snapshots) != {'state.json', 'calls.jsonl'}:
        raise ValueError('App state and log snapshots required')
    state, log = Path(intent['state']).resolve(strict=True), Path(intent['log']).resolve(strict=True)
    if (not state.is_relative_to(parent) or not log.is_relative_to(parent)
            or sha(state) != sha(snapshots['state.json']) or sha(log) != sha(snapshots['calls.jsonl'])):
        raise ValueError('App state/log differ from their original snapshots')
    raw_calls = load_tool_calls(log)
    if len(raw_calls) != 1 or raw_calls[0].get('tool') != 'create_doc':
        raise ValueError('Exactly one persisted create_doc action required')
    calls = [{k: c[k] for k in ('tool', 'args', 'result')} for c in raw_calls]
    result = calls[0]['result']
    if result.get('ok') is not True or not _state_contains(read(state), result.get('document')):
        raise ValueError('Successful document must exist in saved app state')
    sources = sorted(map(Path, default_sources))
    if not sources:
        raise ValueError('Pinned app signature sources required')
    exported = export_interaction(native / 'calls', witness_path, app_calls=raw_calls,
                                  default_source_paths=sources)
    if len(exported['witnessed_duplicate_inspection_suppression']) != 1:
        raise ValueError('Exactly one independently witnessed duplicate suppression required')
    messages = exported['messages']
    app_requests = [c for m in messages for c in m.get('tool_calls', []) if c['name'] == APP_TOOL]
    if len(app_requests) != 2:
        raise ValueError('Expected one checkpoint hold and one app action')
    replies = []
    for call in app_requests:
        found = [m for m in messages if m.get('role') == 'tool' and m.get('tool_call_id') == call['id']]
        if len(found) != 1:
            raise ValueError('One retained response per app request required')
        replies.append(_tool_result(found[0], APP_TOOL))
    if (set(replies[0]) != {'error'} or not isinstance(replies[0]['error'], str)
            or not replies[0]['error'].startswith(CHECKPOINT_PREFIX)):
        raise ValueError('Original checkpoint hold is not established')
    delivered = replies[1].get('result')
    if isinstance(delivered, str):
        delivered = _decode_json(delivered)
    structured = replies[1].get('structuredContent', {}).get('result')
    if isinstance(structured, str):
        structured = _decode_json(structured)
    if (not _same(delivered, result) or not _same(structured, result)
            or not _same(app_requests[1]['arguments'], calls[0]['args'])):
        raise ValueError('Native app result or effective arguments disagree with saved app log')
    if [m.get('content') for m in messages if m.get('role') == 'user'] != [
            '[' + spec['narrative_anchor_date'] + '] ' + spec['test']]:
        raise ValueError('Original dated user request changed')
    check_settings(exported['settings'], TASK)
    check_messages(messages, TASK)
    row = {'persona': 'morgan', 'test_id': '020', 'messages': messages,
           'duration_ms': duration, 'app_calls': calls}
    grading_calls(row, TASK)
    evidence = {'settings': exported['settings'], 'row': row,
                'attempts': [{'auxiliary_calls': exported['auxiliary_calls']}]}
    proof = {'schema': 'dolphin-full-task-reconstruction-v1', 'task': TASK,
             'parent': str(parent), 'api_witness': pin(witness_path),
             'process': pin(process_path), 'context_delivery': pin(context_path),
             'app_intent': pin(intent_path), 'app_outcome': pin(outcome_path),
             'state': pin(state), 'log': pin(log),
             'snapshots': [pin(snapshots[n]) for n in sorted(snapshots)],
             'normalization': exported['witnessed_duplicate_inspection_suppression'],
             'execution_sha256': fingerprint(evidence), 'model_or_app_replay': False,
             'duration_basis': 'native process duration; excludes adapter overhead'}
    return evidence, proof


def source_transition(old, new):
    """Verify identical scientific inputs and only allow listed controller changes."""
    a, b = copy.deepcopy(old), copy.deepcopy(new)
    a['inputs'].pop('source_manifest'); b['inputs'].pop('source_manifest')
    if a != b:
        raise ValueError('Recovery must preserve all frozen scientific inputs and settings')
    old_sources = read(verify_pin(old['inputs']['source_manifest']))
    new_sources = read(verify_pin(new['inputs']['source_manifest']))
    for entry in old_sources + new_sources:
        verify_pin(entry)
    suffix = '/benchmarks/dolphinbench/export.py'
    paths = [p['path'] for p in old_sources if p['path'].endswith(suffix)]
    if len(paths) != 1:
        raise ValueError('Original source root is ambiguous')
    old_root = Path(paths[0][:-len(suffix)])
    def mapping(entries, root):
        result = {}
        for entry in entries:
            path = Path(entry['path'])
            key = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
            if key in result:
                raise ValueError('Duplicate source identity')
            result[key] = entry['sha256']
        return result
    before, after = mapping(old_sources, old_root), mapping(new_sources, ROOT)
    changed = sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))
    required_tests = {'tests/benchmarking/test_dolphinbench_export.py',
                      'tests/benchmarking/test_dolphin_full_recovery_020.py'}
    if (not changed or set(before) - set(after) or not set(changed) <= ALLOWED
            or not required_tests <= set(after)):
        raise ValueError('Unexpected source removal or change outside bounded recovery')
    return [{'path': k, 'old_sha256': before.get(k), 'new_sha256': after.get(k)} for k in changed]


def check_budget(path, campaign, *, inherited=None, inflight_since=None):
    """Enforce the original cumulative cap and retain every inherited row."""
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)) as db:
        if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise ValueError('Budget integrity failed')
        if db.execute('SELECT cap,identity FROM campaign WHERE singleton=1').fetchone() != (
                micros(campaign['cap_usd']), fingerprint(campaign)):
            raise ValueError('Budget identity or cap changed')
        rows = db.execute('SELECT * FROM calls').fetchall()
        columns = [c[1] for c in db.execute('PRAGMA table_info(calls)')]
    entries = [dict(zip(columns, row)) for row in rows]
    total = 0
    for row in entries:
        state = row['state']
        if state == 'completed':
            if type(row['actual']) is not int or not 0 <= row['actual'] <= row['reserved']:
                raise ValueError('Invalid settled charge')
            total += row['actual']
        elif state == 'reserved':
            if (inflight_since is None or type(row['created']) not in (int, float)
                    or not inflight_since <= row['created'] <= time.time() + 5
                    or type(row['reserved']) is not int or row['reserved'] < 0
                    or row['actual'] is not None):
                raise ValueError('Unresolved inherited or unproved reservation')
            total += row['reserved']
        elif state != 'unsent':
            raise ValueError('Unknown budget call state')
    if total > micros(campaign['cap_usd']):
        raise ValueError('Cumulative campaign budget exceeded')
    if inherited:
        with closing(sqlite3.connect(Path(inherited).resolve().as_uri() + '?mode=ro&immutable=1', uri=True)) as db:
            prior = db.execute('SELECT * FROM calls').fetchall()
        index = {row[0]: row for row in rows}
        if any(index.get(row[0]) != row for row in prior):
            raise ValueError('Inherited charge or call changed')
    return total


def _snapshot_budget(source, destination, campaign):
    files = [source] + ([Path(str(source) + '-wal')] if Path(str(source) + '-wal').exists() else [])
    original = [pin(p) for p in files]
    with tempfile.TemporaryDirectory(prefix='dolphin-full020-budget-') as temp:
        staged, standalone = Path(temp) / 'budget.db', Path(temp) / 'standalone.db'
        for p in files:
            copy_exact(p, Path(str(staged) + str(p)[len(str(source)):]))
        with closing(sqlite3.connect(staged)) as db, closing(sqlite3.connect(standalone)) as out:
            db.backup(out)
            if out.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                raise ValueError('Budget snapshot integrity failed')
            out.execute('PRAGMA journal_mode=DELETE')
        check_budget(standalone, campaign)
        for entry in original:
            verify_pin(entry)
        copy_exact(standalone, destination)
    return original


def _task_paths(parent, folder, suffix='.json'):
    return {p.parent.name + '/' + p.stem: p for p in (parent / folder).glob('*/*' + suffix)
            if not p.name.startswith('._')}


def _verify_original_gateway_coverage(parent):
    """Every saved transport must have one completed ledger row and matching bytes."""
    transports = [p for pattern in ('native/tests/*/*/calls/tests/*/transport.json',
                                   'judge-calls/judge/*/transport.json')
                  for p in parent.glob(pattern) if not p.name.startswith('._')]
    with closing(sqlite3.connect((parent / 'budget.db').resolve().as_uri() + '?mode=ro', uri=True)) as db:
        rows = {r[0]: r[1:] for r in db.execute(
            'SELECT call_id,phase,state,request_sha256,response_sha256 FROM calls')}
    if len(transports) != len(rows) or {p.parent.name for p in transports} != set(rows):
        raise ValueError('Original ledger and gateway calls are not a bijection')
    for path in transports:
        meta, request, response = read(path), read(path.parent / 'request.json'), read(path.parent / 'response.json')
        call_id = path.parent.name
        if (meta.get('call_id') != call_id or rows[call_id] !=
                (meta.get('phase'), 'completed', fingerprint(request), fingerprint(response['response']))):
            raise ValueError('Original gateway/ledger evidence differs: ' + call_id)


def prepare(parent, output, condition_path, receipts, witness_path):
    """Create a distinct immutable recovery epoch; no reader, judge or app calls."""
    from harness.submission import read_release
    from harness.runner import digest
    parent, output = Path(parent).resolve(strict=True), Path(output).absolute()
    if output.exists() or output == parent or output.is_relative_to(parent) or parent.is_relative_to(output):
        raise ValueError('A new independent recovery directory is required')
    condition = admit(condition_path, receipts, 'full')
    old = read(parent / 'execution-condition.json')
    changes = source_transition(old, condition)
    original_admission = read(parent / 'launch-admission.json')
    started = original_admission.get('created_at')
    if (original_admission.get('stage') != 'full' or original_admission.get('condition_sha256') != identity(old)
            or type(started) not in (int, float) or not math.isfinite(started)):
        raise ValueError('Original full launch and its deadline must be witnessed')
    deadline_at = started + 86400
    if time.time() >= deadline_at:
        raise ValueError('Original 24-hour campaign deadline expired')
    for entry in old['inputs'].values():
        verify_pin(entry)
    release = read_release(Path(condition['bindings']['upstream_root']))
    expected = {p + '/' + str(s['id']).zfill(3): s for p, v in release.items() for s in v['tests']}
    if len(expected) != 600:
        raise ValueError('Original release must contain exactly 600 unique tasks')
    executions, grades = _task_paths(parent, 'tests'), _task_paths(parent, 'grades')
    dispatch, grade_intents = _task_paths(parent, 'dispatch-intents'), _task_paths(parent, 'grade-intents')
    inflight = _task_paths(parent, 'tests', '.inflight')
    if (len(executions) != 19 or set(grades) != set(executions)
            or set(dispatch) != set(executions) | {TASK} or set(grade_intents) != set(executions)
            or set(inflight) != {TASK} or not set(executions) | {TASK} <= set(expected)):
        raise ValueError('Unexpected completed, intent or inflight task inventory')
    if (read(inflight[TASK]).get('source_sha256') != digest(expected[TASK])
            or read(dispatch[TASK]).get('condition') != pin(parent / 'execution-condition.json')):
        raise ValueError('Interrupted task intent does not match the frozen task and condition')
    for key, grade in grades.items():
        checks = read(grade)['checks']
        if (len(checks) != len(expected[key]['grade']['config']['assertions'])
                or any(type(c.get('passed')) is not bool or c.get('check') != i for i, c in enumerate(checks))
                or read(grade_intents[key]).get('execution') != pin(executions[key])):
            raise ValueError('Inherited grade or intent is incomplete: ' + key)
        journal = read(parent / 'native/tests' / key / 'app-evidence/outcome.json')
        if journal.get('completed') is not True or len(journal.get('artifacts', [])) != 2:
            raise ValueError('Inherited app journal incomplete: ' + key)
        for artifact in journal['artifacts']:
            verify_pin(artifact)
    for key in set(expected) - set(executions) - {TASK}:
        workspace = parent / 'apps' / key
        if workspace.exists() and any(workspace.iterdir()):
            raise ValueError('Untouched task has an existing app workspace: ' + key)
    upstream = Path(condition['bindings']['upstream_root'])
    evidence, proof = reconstruct(parent, witness_path, expected[TASK], (upstream / 'mock_mcp').glob('repair*.py'))
    campaign = {**read(condition['inputs']['options']['path'])['campaign_identity'],
                'cap_usd': condition['budget']['caps_usd']['full']}
    check_budget(parent / 'budget.db', campaign)
    _verify_original_gateway_coverage(parent)
    parent_pins = inventory(parent)
    output.mkdir(parents=True, mode=0o700)
    save(output / 'recovery-intent.json', {'schema': SCHEMA, 'parent': str(parent),
         'condition': pin(condition_path), 'no_action_replay': True})
    originals = _snapshot_budget(parent / 'budget.db', output / 'budget.db', campaign)
    copy_exact(output / 'budget.db', output / 'inherited-budget.db')
    copies = []
    for folder in ('tests', 'grades', 'native', 'judge-calls', 'subscription/calls',
                   'apps', 'dispatch-intents', 'grade-intents', 'checkpoints'):
        for path in sorted((parent / folder).rglob('*')):
            if path.is_symlink():
                raise ValueError('Evidence symlink refused')
            if not path.is_file() or path.name.startswith('._') or path.suffix == '.inflight':
                continue
            source = pin(path); target = output / path.relative_to(parent)
            copy_exact(path, target)
            verify_pin(source)
            copies.append({'source': source, 'copy': pin(target)})
    save(output / 'tests' / (TASK + '.json'), evidence)
    proof['evidence'] = pin(output / 'tests' / (TASK + '.json'))
    save(output / 'recovery-020.json', proof)
    save(output / 'execution-condition.json', condition)
    for entry in parent_pins + originals:
        verify_pin(entry)
    transition = {'schema': SCHEMA, 'parent': str(parent), 'condition': pin(condition_path),
        'old_condition_sha256': identity(old), 'new_condition_sha256': identity(condition),
        'source_changes': changes, 'inherited': parent_pins + originals,
        'copies': copies, 'inherited_budget': pin(output / 'inherited-budget.db'),
        'recovery': pin(output / 'recovery-020.json'), 'reconstructed_id': TASK,
        'imported_ids': sorted(executions), 'imported_grade_ids': sorted(grades),
        'execution_conditions': {k: identity(old) for k in set(executions) | {TASK}},
        'grade_conditions': {k: identity(old) for k in grades},
        'deadline_at': deadline_at,
        'lineage': 'Full campaign continued after a source-bound exporter repair; original evidence retained.',
        'no_action_replay': True}
    save(output / 'epoch-transition.json', transition)
    verify_epoch(output, condition_path)
    return transition


def verify_epoch(output, condition_path, *, inflight_since=None):
    output = Path(output).resolve(strict=True)
    transition = read(output / 'epoch-transition.json')
    condition = load_condition(condition_path)
    if (transition.get('schema') != SCHEMA or transition.get('condition') != pin(condition_path)
            or transition.get('new_condition_sha256') != identity(condition)
            or read(output / 'execution-condition.json') != condition):
        raise ValueError('Full recovery epoch identity differs')
    parent = Path(transition['parent']).resolve(strict=True)
    old = read(parent / 'execution-condition.json')
    original_admission = read(parent / 'launch-admission.json')
    if (identity(old) != transition['old_condition_sha256']
            or source_transition(old, condition) != transition['source_changes']
            or transition.get('deadline_at') != original_admission.get('created_at', 0) + 86400):
        raise ValueError('Original scientific or source transition changed')
    for entry in transition['inherited']:
        verify_pin(entry)
    inherited_by_path = {entry['path']: entry for entry in transition['inherited']}
    if any(inherited_by_path.get(entry['path']) != entry for entry in inventory(parent)):
        raise ValueError('Original evidence inventory changed')
    for pair in transition['copies']:
        verify_pin(pair['source']); verify_pin(pair['copy'])
        if pair['source']['sha256'] != pair['copy']['sha256']:
            raise ValueError('Inherited evidence copy changed')
    wanted_copies = set()
    for folder in ('tests', 'grades', 'native', 'judge-calls', 'subscription/calls',
                   'apps', 'dispatch-intents', 'grade-intents', 'checkpoints'):
        for path in (parent / folder).rglob('*'):
            if path.is_symlink():
                raise ValueError('Evidence symlink refused')
            if path.is_file() and not path.name.startswith('._') and path.suffix != '.inflight':
                wanted_copies.add(str(path.resolve()))
    actual_copies = {pair['source']['path'] for pair in transition['copies']}
    if (actual_copies != wanted_copies or len(actual_copies) != len(transition['copies'])
            or any(Path(pair['copy']['path']) != output / Path(pair['source']['path']).relative_to(parent)
                   for pair in transition['copies'])):
        raise ValueError('Inherited evidence copy inventory differs')
    proof = read(verify_pin(transition['recovery']))
    if (proof.get('task') != TASK or proof.get('model_or_app_replay') is not False
            or pin(output / 'tests' / (TASK + '.json')) != proof.get('evidence')
            or fingerprint(read(proof['evidence']['path'])) != proof.get('execution_sha256')):
        raise ValueError('Reconstructed task proof changed')
    for name in ('api_witness', 'process', 'context_delivery', 'app_intent', 'app_outcome', 'state', 'log'):
        verify_pin(proof[name])
    for entry in proof['snapshots']:
        verify_pin(entry)
    inherited = verify_pin(transition['inherited_budget'])
    campaign = {**read(condition['inputs']['options']['path'])['campaign_identity'],
                'cap_usd': condition['budget']['caps_usd']['full']}
    if inflight_since is None:
        with closing(sqlite3.connect((output / 'budget.db').resolve().as_uri() + '?mode=ro', uri=True)) as db:
            unsettled = db.execute("SELECT COUNT(*) FROM calls WHERE state NOT IN ('completed','unsent')").fetchone()[0]
        if unsettled:
            from .recording import verify_transient_reservations
            verify_transient_reservations(output / 'budget.db', output / 'judge-calls',
                                          cap_usd=campaign['cap_usd'], identity=campaign)
            inflight_since = 0  # The exact saved transient errors were verified above.
    check_budget(output / 'budget.db', campaign, inherited=inherited, inflight_since=inflight_since)
    if (len(transition['imported_ids']) != 19 or set(transition['imported_ids']) != set(transition['imported_grade_ids'])
            or set(transition['execution_conditions']) != set(transition['imported_ids']) | {TASK}
            or set(transition['grade_conditions']) != set(transition['imported_grade_ids'])):
        raise ValueError('Inherited task provenance differs')
    return transition


def require_deadline(transition):
    if type(transition.get('deadline_at')) not in (int, float) or time.time() >= transition['deadline_at']:
        raise ValueError('Original 24-hour campaign deadline expired; no dispatch permitted')


def preflight_resume(output):
    """Refuse uncertain interactions or grading before any provider starts."""
    output = Path(output)
    ledger = ROOT / 'docs/benchmarks/evidence/dolphin-execution-audit-20261025/task-ledger.jsonl'
    expected = {row['id'] for row in _jsonl(ledger)}
    if len(expected) != 600:
        raise ValueError('Full task ledger must contain 600 distinct tasks')
    for folder, suffix in (('tests', '.inflight'), ('tests', '.returned')):
        for path in (output / folder).glob('*/*' + suffix):
            if path.name.startswith('._'):
                continue
            if suffix == '.inflight' or not path.with_suffix('.json').exists():
                raise ValueError('Uncertain saved interaction requires reconciliation: ' + str(path))
    for folder, target in (('dispatch-intents', 'tests'), ('grade-intents', 'grades')):
        for path in (output / folder).glob('*/*.json'):
            if path.name.startswith('._'):
                continue
            key = path.parent.name + '/' + path.stem
            if key not in expected or not (output / target / (key + '.json')).exists():
                raise ValueError('Uncertain ' + folder + ': ' + key)
    for key in expected:
        workspace = output / 'apps' / key
        if not (output / 'tests' / (key + '.json')).exists() and workspace.exists() and any(workspace.iterdir()):
            raise ValueError('Uncertain app workspace cannot be reset: ' + key)


def progress(output):
    passed = failed = 0
    for path in (Path(output) / 'grades').glob('*/*.json'):
        if path.name.startswith('._'):
            continue
        checks = read(path).get('checks')
        if (not isinstance(checks, list) or not checks
                or any(type(check.get('passed')) is not bool for check in checks)):
            raise ValueError('Cannot report an incomplete grade: ' + str(path))
        if all(check['passed'] for check in checks):
            passed += 1
        else:
            failed += 1
    return {'graded': passed + failed, 'total': 600, 'passed': passed, 'failed': failed}


def initialize_run_identity(output, condition_path, release, configuration):
    from harness.runner import digest
    transition = verify_epoch(output, condition_path)
    require_deadline(transition)
    preflight_resume(output)
    condition = load_condition(condition_path)
    original = read(verify_pin(transition['recovery']))
    spec = next(s for s in release['morgan']['tests'] if str(s['id']).zfill(3) == '020')
    upstream = Path(condition['bindings']['upstream_root'])
    rebuilt, proof = reconstruct(transition['parent'], original['api_witness']['path'], spec,
                                 (upstream / 'mock_mcp').glob('repair*.py'))
    proof['evidence'] = original['evidence']
    if proof != original or rebuilt != read(original['evidence']['path']):
        raise ValueError('Offline task reconstruction does not reproduce its saved evidence')
    path = Path(output) / 'run.json'
    value = {'version': 1, 'release': digest(release), 'configuration': configuration}
    if path.is_symlink():
        raise ValueError('Recovery run identity must be a regular file')
    if path.exists():
        if read(path) != value:
            raise ValueError('Recovery runner inputs changed')
    else:
        save(path, value)
