"""Recovery acceptance: real export/guards, no paid inference or app dispatch."""
from copy import deepcopy
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from types import SimpleNamespace

import pytest

from benchmarks.dolphinbench import pilot_recovery as recovery
from benchmarks.dolphinbench import readiness as gate
from benchmarks.dolphinbench.recording import BudgetLedger, fingerprint
from benchmarks.dolphinbench.tool_defaults import _same, normalize_effective_arguments
from tests.benchmarking.test_execution_readiness import condition, qualify, pilot_evidence


@pytest.mark.parametrize('a,b', [(1150, 1150.0), (725, 725.0),
    ({'nested': [0, {'n': 1150}]}, {'nested': [-0.0, {'n': 1150.0}]}),
    (2**100, float(2**100)), ([1, 2.0], [1.0, 2])])
def test_exact_numeric_equivalence(a, b):
    assert _same(a, b)


@pytest.mark.parametrize('a,b', [(1150, 1150.01), (2**53 + 1, float(2**53 + 1)),
    (True, 1), (False, 0.0), ('1150', 1150), ([1, 2], [2, 1]),
    ({'a': 1}, {'a': 1, 'b': 2}), ({'a': 1}, {'b': 1}),
    (float('nan'), float('nan')), (float('inf'), float('inf')),
    ({'x': [float('inf')]}, {'x': [float('inf')]}), ((1,), [1])])
def test_invalid_or_different_values(a, b):
    assert not _same(a, b)


def test_numeric_export_is_reversible_and_keeps_independent_matching(tmp_path):
    source = tmp_path / 'defaults.py'
    source.write_text('def book_flight(quote_id, max_price_usd, optional=None): pass\n')
    messages = [{'role': 'assistant', 'tool_calls': [{'id': '1', 'name': 'mcp__dolphinbench_apps__book_flight',
        'arguments': {'quote_id': 'flight', 'max_price_usd': 1150}}]}]
    backend = [{'tool': 'book_flight', 'args': {'quote_id': 'flight', 'max_price_usd': 1150.0, 'optional': None}}]
    raw = deepcopy(messages)
    normalized, receipt = normalize_effective_arguments(messages, backend, [source])
    assert messages == raw
    assert type(messages[0]['tool_calls'][0]['arguments']['max_price_usd']) is int
    assert type(normalized[0]['tool_calls'][0]['arguments']['max_price_usd']) is float
    assert receipt['changes'][0]['original'] == raw[0]['tool_calls'][0]
    assert receipt['explicit_arguments_changed'] is False
    assert receipt['changes'][0]['exact_finite_numeric_representation_only']
    for value in (1150.1, True, '1150', float('nan'), float('inf')):
        bad = deepcopy(backend); bad[0]['args']['max_price_usd'] = value
        with pytest.raises(ValueError): normalize_effective_arguments(messages, bad, [source])
    bad = deepcopy(backend); bad[0]['args']['quote_id'] = 'wrong-target'
    with pytest.raises(ValueError): normalize_effective_arguments(messages, bad, [source])
    bad = deepcopy(backend); del bad[0]['args']['max_price_usd']
    with pytest.raises(ValueError): normalize_effective_arguments(messages, bad, [source])
    two = deepcopy(messages); two[0]['tool_calls'].append({**deepcopy(two[0]['tool_calls'][0]),
        'id': '2', 'arguments': {'quote_id': 'other', 'max_price_usd': 725}})
    second = {'tool': 'book_flight', 'args': {'quote_id': 'other', 'max_price_usd': 725.0, 'optional': None}}
    with pytest.raises(ValueError): normalize_effective_arguments(two, [second, *backend], [source])
    with pytest.raises(ValueError): normalize_effective_arguments(two, backend, [source])


@pytest.fixture
def actual_harness():
    # Use the real independently maintained submission validator, not a stub gate.
    root = Path(os.environ.get('DOLPHINBENCH_UPSTREAM',
        '/Users/javadtaghia/gitlab/benchmark-sources/dolphinbench'))
    if not (root / 'harness/submission.py').exists():
        pytest.skip('requires pinned public DolphinBench checkout')
    sys.path.insert(0, str(root))
    yield root
    sys.path.remove(str(root))


@pytest.fixture
def capture(tmp_path, actual_harness):
    parent = tmp_path / 'parent'
    native = parent / 'native/tests/morgan/129'
    state = parent / 'apps/morgan/129/state.json'
    log = state.with_name('calls.jsonl')
    calls = []
    raw_calls = []
    for i, (tool, maximum) in enumerate([('book_flight', 1150), ('book_hotel', 725)]):
        args = {'quote_id': 'quote-' + str(i), 'max_price_usd': maximum}
        booking = {'id': 'booking-' + str(i), 'quote_id': args['quote_id'], 'status': 'booked'}
        calls.append({'tool': tool, 'args': {**args, 'max_price_usd': float(maximum)},
            'result': {'ok': True, 'booking': booking}})
        raw_calls.append({'id': 'call-' + str(i), 'type': 'function',
            'function': {'name': 'mcp__dolphinbench_apps__' + tool, 'arguments': json.dumps(args)}})
    gate.save(state, {'bookings': [c['result']['booking'] for c in calls]})
    log.write_text(''.join(json.dumps(c) + '\n' for c in calls))
    gate.save(native / 'app-evidence/intent.json', {'state': str(state), 'log': str(log)})
    for p in (state, log): recovery.copy_exact(p, native / 'app-evidence' / p.name)
    gate.save(native / 'app-evidence/outcome.json', {'completed': False,
        'unknown_actions_must_not_be_replayed': True,
        'artifacts': [gate.pin(native / 'app-evidence' / p.name) for p in (state, log)]})
    gate.save(native / 'context-delivery.json', {'mode': 'installed AtMem API to native ephemeral_system_prompt', 'actual_native_process_exit_code': 0})
    gate.save(native / 'process.json', {'exit_code': 0, 'stderr': '', 'stdout': json.dumps({
        'type': 'result', 'exit_code': 0, 'duration_ms': 12000, 'session_id': 'original-session'})})
    shutdown = tmp_path / 'shutdown-witness.jsonl'
    shutdown.write_text(json.dumps({'format': 'atmem-hermes-shutdown-observation-v1',
        'providers': [], 'drain': {'status': 'drained', 'abandoned_writes': 0, 'abandoned_prefetches': 0, 'active_tasks': 0}}) + '\n')
    spec = deepcopy(next(s for s in recovery._cached_release(str(actual_harness), gate.sha(actual_harness / 'manifest.json'))['morgan']['tests'] if str(s['id']).zfill(3) == '129'))
    history = [{'role': 'user', 'content': '[' + spec['narrative_anchor_date'] + '] ' + spec['test']}]
    response_message = {'role': 'assistant', 'content': None, 'tool_calls': raw_calls}
    second = history + [response_message] + [{'role': 'tool', 'tool_call_id': c['id'],
        'content': json.dumps(calls[i]['result'])} for i, c in enumerate(raw_calls)]
    campaign = {'fixture': 'same-science', 'cap_usd': 10}
    ledger = tmp_path / 'budget.db'
    book = BudgetLedger(ledger, cap_usd=10, identity=campaign)
    witnesses = []
    for i, (messages, answer) in enumerate([(history, response_message), (second, {'role': 'assistant', 'content': 'Done'})]):
        directory = native / 'calls/tests' / ('gateway-' + str(i))
        request = {'model': 'openai/gpt-5.6-luna', 'reasoning_effort': 'high', 'messages': messages,
            'tools': [{'type': 'function', 'function': {'name': 'mcp__dolphinbench_apps__' + name, 'parameters': {'type': 'object'}}} for name in ('book_flight', 'book_hotel')]}
        response = {'choices': [{'message': answer}], 'usage': {'prompt_tokens': 10, 'completion_tokens': 2, 'cost': 0}}
        gate.save(directory / 'request.json', request)
        gate.save(directory / 'transport.json', {'call_id': directory.name, 'phase': 'tests', 'started_ns': i + 1})
        gate.save(directory / 'response.json', {'response': response, 'elapsed_seconds': 1})
        book.reserve_subscription(directory.name, phase='tests', request=request)
        book.complete(directory.name, actual_usd=0, usage=response['usage'], response=response)
        witnesses += [{'event': 'pre_api_request', 'api_request_id': str(i),
            'session_id': 'original-session', 'messages_sha256': fingerprint(messages)},
            {'event': 'post_api_request', 'api_request_id': str(i), 'session_id': 'original-session'}]
    book.close()
    api = tmp_path / 'api-witness.jsonl'
    api.write_text(''.join(json.dumps(w) + '\n' for w in witnesses))
    proofs = {'api_witness': gate.pin(api), 'shutdown_witness': gate.pin(shutdown),
        'independent_state': gate.pin(state), 'independent_log': gate.pin(log)}
    source = tmp_path / 'repair_fixture.py'
    source.write_text('def book_flight(quote_id, max_price_usd): pass\ndef book_hotel(quote_id, max_price_usd): pass\n')
    return SimpleNamespace(parent=parent, native=native, proofs=proofs, ledger=ledger, spec=spec,
        sources=[source], campaign=campaign, state=state, api=api)


def test_offline_numeric_reconstruction_zero_network_or_app_calls(capture, monkeypatch):
    import urllib.request
    def forbidden(*a, **kw): raise AssertionError('Provider/app process/network dispatch')
    monkeypatch.setattr(urllib.request, 'urlopen', forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    before = recovery.inventory(capture.parent)
    evidence, receipt = recovery.reconstruct_129(capture.parent, capture.proofs, capture.ledger, capture.spec, capture.sources)
    from harness.submission import grading_calls
    assert len(grading_calls(evidence['row'], 'fixture')) == 2
    assert evidence['row']['duration_ms'] == 12000
    assert 'excludes controller overhead' in receipt['duration_basis']
    assert receipt['provider_calls'] == receipt['app_calls_dispatched'] == 0
    assert recovery.inventory(capture.parent) == before
    assert gate.read(capture.native / 'app-evidence/outcome.json')['completed'] is False


@pytest.mark.parametrize('mutation', ['process', 'state', 'witness', 'budget', 'boundary', 'duration', 'tamper'])
def test_incomplete_recovery_refuses_without_replay(capture, mutation):
    c = capture
    if mutation in ('process', 'duration'):
        path = c.native / 'process.json'; data = gate.read(path)
        if mutation == 'process': data['exit_code'] = 1
        else: data['stdout'] = json.dumps({'type': 'result', 'exit_code': 0})
        path.write_text(json.dumps(data))
    if mutation == 'state':
        c.state.write_text('{"bookings": []}'); c.proofs['independent_state'] = gate.pin(c.state)
    if mutation == 'witness':
        c.api.write_text('{}\n'); c.proofs['api_witness'] = gate.pin(c.api)
    if mutation == 'budget':
        with sqlite3.connect(c.ledger) as db: db.execute("UPDATE calls SET state='reserved'")
    if mutation == 'boundary': c.spec['test'] = 'changed boundary'
    if mutation == 'tamper': c.proofs['api_witness']['sha256'] = '0' * 64
    with pytest.raises((ValueError, KeyError)):
        recovery.reconstruct_129(c.parent, c.proofs, c.ledger, c.spec, c.sources)


def test_grades_are_preserved_byte_exact_and_saved_execution_never_runs_apps(tmp_path):
    gate.save(tmp_path / 'execution-condition.json', {'fixed': True})
    gate.save(tmp_path / 'tests/morgan/023.json', {'original': 'execution'})
    grade = tmp_path / 'grades/morgan/023.json'
    grade.parent.mkdir(parents=True)
    grade.write_bytes(b'{ "checks" : [{"check":0,"passed":true}], "raw":"unchanged" }\n')
    original = grade.read_bytes()
    class Runner:
        def _execute(self, *a): raise AssertionError('imported execution dispatched')
        def _grade(self, *a): raise AssertionError('completed grade regenerated')
    visits = []
    recovery.execute_once(Runner(), tmp_path, 'morgan', {'id': 23}, boundary=lambda: visits.append('guard'))
    assert grade.read_bytes() == original and visits == ['guard']


def test_crash_intents_cannot_duplicate_booking_or_unknown_judge(tmp_path):
    gate.save(tmp_path / 'execution-condition.json', {'fixed': True})
    actions = []
    class Runner:
        def _execute(self, *a):
            actions.append('booking accepted'); raise RuntimeError('crash after action')
    for expected in (RuntimeError, FileExistsError):
        with pytest.raises(expected):
            recovery.execute_once(Runner(), tmp_path, 'morgan', {'id': 129}, boundary=lambda: None)
    assert actions == ['booking accepted']
    # Even when execution is saved later, a crashed grade cannot be regenerated.
    gate.save(tmp_path / 'tests/morgan/129.json', {'row': 'retained'})
    class Grader:
        def _execute(self, *a): raise AssertionError('existing execution repeated')
        def _grade(self, *a): actions.append('judge sent'); raise RuntimeError('uncertain judge')
    for expected in (RuntimeError, FileExistsError):
        with pytest.raises(expected):
            recovery.execute_once(Grader(), tmp_path, 'morgan', {'id': 129}, boundary=lambda: None)
    assert actions == ['booking accepted', 'judge sent']


def test_lock_excludes_second_controller(tmp_path):
    with recovery.epoch_lock(tmp_path):
        with pytest.raises(ValueError, match='already running'):
            with recovery.epoch_lock(tmp_path): pytest.fail('second controller acquired lock')


def test_budget_copy_preserves_original_sidecars_and_cumulative_cap(tmp_path):
    campaign = {'fixed': True}
    source = tmp_path / 'parent.db'
    book = BudgetLedger(source, cap_usd=10, identity=campaign)
    book.reserve('old', phase='judge', request={}, maximum_usd=9)
    book.complete('old', actual_usd=9, usage={'prompt_tokens': 1, 'completion_tokens': 1}, response={})
    before = {p: p.read_bytes() for p in (source, Path(str(source) + '-wal'), Path(str(source) + '-shm'))}
    target = tmp_path / 'new.db'
    recovery.snapshot_budget(source, target, campaign)
    assert all(p.read_bytes() == value for p, value in before.items())
    resumed = BudgetLedger(target, cap_usd=10, identity=campaign)
    with pytest.raises(PermissionError): resumed.reserve('new', phase='judge', request={}, maximum_usd=2)
    resumed.close()
    book.reserve('uncertain', phase='judge', request={}, maximum_usd=.5)
    with pytest.raises(ValueError, match='Unresolved'):
        recovery.snapshot_budget(source, tmp_path / 'blocked.db', campaign)
    book.close()


def test_wal_budget_is_finalized_locally_before_exclusive_publication(tmp_path, monkeypatch):
    campaign = {'fixed': True}
    source = tmp_path / 'parent.db'
    target = tmp_path / 'destination' / 'budget.db'
    book = BudgetLedger(source, cap_usd=10, identity=campaign)
    try:
        book.reserve('paid', phase='judge', request={}, maximum_usd=9)
        book.complete('paid', actual_usd=9,
            usage={'prompt_tokens': 1, 'completion_tokens': 1}, response={})
        book.reserve('not-sent', phase='judge', request={}, maximum_usd=.5)
        book.cancel_unsent('not-sent', proven_unsent=True)
        rows = book.connection.execute('SELECT * FROM calls ORDER BY call_id').fetchall()
        assert book.connection.execute('PRAGMA journal_mode').fetchone() == ('wal',)
        originals = {p: p.read_bytes() for p in
            (source, Path(str(source) + '-wal'), Path(str(source) + '-shm'))}
        assert len(originals[Path(str(source) + '-wal')]) > 0
        connect, copy_exact = sqlite3.connect, recovery.copy_exact
        connections, published = [], []

        class TrackedConnection(sqlite3.Connection):
            closed = False
            def close(self):
                super().close()
                self.closed = True

        def local_connect(database, *args, **kwargs):
            path = Path(str(database).removeprefix('file:').split('?', 1)[0]).resolve()
            assert path != source.resolve(), 'original evidence opened by SQLite'
            assert not path.is_relative_to(target.parent.resolve()), 'destination opened by SQLite'
            connection = connect(database, *args, factory=TrackedConnection, **kwargs)
            connections.append(connection)
            return connection

        def publish(finalized, destination):
            if Path(destination) == target:
                assert connections and all(c.closed for c in connections)
                assert not target.exists()
                with connect(Path(finalized).as_uri() + '?mode=ro&immutable=1', uri=True) as db:
                    assert db.execute('PRAGMA integrity_check').fetchall() == [('ok',)]
                    assert db.execute('PRAGMA journal_mode').fetchone() == ('delete',)
                    assert db.execute('SELECT * FROM calls ORDER BY call_id').fetchall() == rows
                db.close()
                assert not any(Path(str(finalized) + suffix).exists() for suffix in ('-wal', '-shm'))
                published.append(Path(finalized))
            copy_exact(finalized, destination)

        monkeypatch.setattr(recovery.sqlite3, 'connect', local_connect)
        monkeypatch.setattr(recovery, 'copy_exact', publish)
        pins = recovery.snapshot_budget(source, target, campaign)
        assert len(published) == 1
        assert pins == [gate.pin(source), gate.pin(Path(str(source) + '-wal'))]
        assert all(p.read_bytes() == contents for p, contents in originals.items())
        with connect(target.as_uri() + '?mode=ro&immutable=1', uri=True) as db:
            assert db.execute('SELECT * FROM calls ORDER BY call_id').fetchall() == rows
        db.close()
        assert not any(Path(str(target) + suffix).exists() for suffix in ('-wal', '-shm'))
    finally:
        book.close()


def test_unsettled_budget_is_rejected_before_publication(tmp_path):
    campaign = {'fixed': True}
    source, target = tmp_path / 'parent.db', tmp_path / 'destination' / 'budget.db'
    book = BudgetLedger(source, cap_usd=10, identity=campaign)
    try:
        book.reserve('unknown', phase='judge', request={}, maximum_usd=1)
        with pytest.raises(ValueError, match='Unresolved'):
            recovery.snapshot_budget(source, target, campaign)
        assert not target.exists()
        assert not list(target.parent.glob('budget.db*'))
    finally:
        book.close()


@pytest.mark.parametrize('suffix', ['', '-wal', '-shm', '-journal'])
def test_budget_publication_preserves_existing_destination(tmp_path, suffix):
    campaign = {'fixed': True}
    source, target = tmp_path / 'parent.db', tmp_path / 'snapshot.db'
    book = BudgetLedger(source, cap_usd=10, identity=campaign)
    book.close()
    existing = Path(str(target) + suffix)
    existing.write_bytes(b'preserved failed epoch')
    with pytest.raises(FileExistsError):
        recovery.snapshot_budget(source, target, campaign)
    assert existing.read_bytes() == b'preserved failed epoch'
    assert sorted(tmp_path.glob('snapshot.db*')) == [existing]


def historical_bundle(tmp_path, condition):
    old = deepcopy(gate.read(condition))
    source = gate.read(old['inputs']['source_manifest']['path'])
    # Simulate retained *before*-repair bytes for the permitted exporter only.
    retained = tmp_path / 'before-exporter.py'; retained.write_text('# historical exporter\n')
    exporter = str(recovery.ROOT / 'benchmarks/dolphinbench/tool_defaults.py')
    for p in source:
        if p['path'] == exporter: p['sha256'] = gate.sha(retained)
    manifest = tmp_path / 'old-source.json'; gate.save(manifest, source)
    old['inputs']['source_manifest'] = gate.pin(manifest)
    old_path = tmp_path / 'old-condition.json'; gate.save(old_path, old)
    bundle = {'condition': gate.pin(old_path), 'source_manifest': gate.pin(manifest),
        'snapshots': []}
    for i, p in enumerate(source):
        snapshot = tmp_path / 'before-sources' / str(i)
        recovery.copy_exact(retained if p['path'] == exporter else p['path'], snapshot)
        bundle['snapshots'].append({'original': p, 'retained': gate.pin(snapshot)})
    path = tmp_path / 'bundle.json'; gate.save(path, bundle)
    return path


def test_historical_bytes_are_not_ordinary_admission(condition, tmp_path):
    path, _ = condition
    bundle = historical_bundle(tmp_path, path)
    old, changed = recovery.verify_transition(bundle, gate.load_condition(path))
    assert changed == [str(recovery.ROOT / 'benchmarks/dolphinbench/tool_defaults.py')]
    with pytest.raises(ValueError, match='Pinned artifact changed'):
        gate.load_condition(gate.read(bundle)['condition']['path'])
    assert recovery.historical_condition(bundle)[0] == old


@pytest.mark.parametrize('mutation', ['settings', 'selection', 'source', 'pins'])
def test_changed_science_source_and_pins_refused(condition, tmp_path, mutation):
    path, _ = condition
    bundle = historical_bundle(tmp_path, path)
    new = gate.load_condition(path)
    if mutation == 'settings': new['settings']['reader']['reasoning'] = 'medium'
    if mutation == 'selection': new['inputs']['selection'] = new['inputs']['options']
    if mutation == 'source':
        source = gate.read(new['inputs']['source_manifest']['path'])
        source.append({'path': str(tmp_path / 'grader.py'), 'sha256': '0' * 64})
        p = tmp_path / 'bad-source.json'; gate.save(p, source)
        new['inputs']['source_manifest'] = gate.pin(p)
    if mutation == 'pins':
        data = gate.read(bundle); data['snapshots'][0]['retained']['sha256'] = 'f' * 64
        bundle.write_text(json.dumps(data))
    with pytest.raises(ValueError): recovery.verify_transition(bundle, new)


def test_real_resume_entry_rejects_missing_receipts_before_output_or_private_file(condition, tmp_path):
    condition_path, receipts = condition
    output = tmp_path / 'never-created'
    command = [sys.executable, str(recovery.ROOT / 'scripts/launch_dolphin_readiness.py'),
        '--condition', str(condition_path), '--receipts', str(receipts), '--output', str(output),
        '--env-file', str(tmp_path / 'private-must-not-be-read'), '--resume-epoch']
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode != 0 and not output.exists()
    assert 'profile.json' in result.stderr


def test_stale_receipt_stops_prepare_before_creating_epoch(condition, tmp_path):
    path, receipts = condition
    qualify(condition)
    p = receipts / 'profile.json'; value = gate.read(p); value['created_at'] = 0; p.write_text(json.dumps(value))
    output = tmp_path / 'epoch'
    with pytest.raises(ValueError, match='stale'):
        recovery.prepare_epoch('missing-bundle', path, receipts, 'missing-parent', output, 'missing-proofs')
    assert not output.exists()


def test_original_60_selection_guard_not_relaxed(condition):
    path, _ = condition
    value = gate.read(path)
    value['inputs']['selection'] = gate.pin(recovery.ROOT / 'docs/benchmarks/evidence/dolphin-execution-audit-20261025/pilot-selection.json')
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='20'): gate.load_condition(path)
    assert gate.read(gate.PILOT_SELECTION)['tasks'] == 20
    assert gate.read(gate.PILOT_SELECTION.with_name('pilot-selection.json'))['tasks'] == 60


def test_completed_control_regression_retains_report_blocks_promotion(pilot_evidence):
    from benchmarks.dolphinbench.pilot_readiness import report
    path, output, _ids = pilot_evidence
    receipts = path.parent / "report-receipts"
    ledger = gate.read(gate.read(path)['inputs']['selection']['path'])
    historical = {r['id']: r for r in map(json.loads, (recovery.ROOT / 'docs/benchmarks/evidence/dolphin-execution-audit-20261025/task-ledger.jsonl').read_text().splitlines())}
    control = next(k for group in ledger['groups'].values() for k in group if historical[k]['passed'])
    grade = output / 'grades' / (control + '.json'); data = gate.read(grade)
    data['checks'][0]['passed'] = False; grade.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='Regressed'): report(path, output, receipt_output=receipts / 'pilot.json')
    assert control in gate.read(output / 'pilot-report.json')['regressions']
    assert not (receipts / 'pilot.json').exists()


def test_supervisor_scope_is_bounded_and_contract_retry_is_inspect_only():
    from benchmarks.dolphinbench.recovery_supervisor import check_scope
    check_scope(['benchmarks/dolphinbench/tool_defaults.py', 'tests/benchmarking/test_dolphin_pilot_recovery.py'])
    for path in ['benchmarks/dolphinbench/judge.py', 'benchmarks/dolphinbench/adapter.py',
        'fixtures/answer.json', '../outside', '/tmp/arbitrary', 'src/atmem/memory.py',
        'specs/048-dolphin-execution-readiness/review/old.json']:
        with pytest.raises(ValueError): check_scope([path])
    contract = gate.read(recovery.ROOT / 'specs/048-dolphin-execution-readiness/atsys/recovery-task-template.json')
    assert contract['allowRepair'] is True and contract['maxRetries'] == 2
    assert 'handoff' in contract['resumeArgv'] and '--resume-epoch' not in contract['resumeArgv']


@pytest.fixture
def epoch(tmp_path, condition, capture, actual_harness):
    path, receipts = condition
    cfg = gate.read(path)
    options_path = Path(cfg['inputs']['options']['path'])
    options_path.write_text(json.dumps({'campaign_identity': capture.campaign}))
    cfg['inputs']['options'] = gate.pin(options_path)
    cfg['bindings']['upstream_root'] = str(actual_harness)
    cfg['inputs']['upstream_manifest'] = gate.pin(actual_harness / 'manifest.json')
    synthetic_source = tmp_path / 'bounded-harness-source.py'
    synthetic_source.write_text('# harness revision one\n')
    source = gate.read(cfg['inputs']['source_manifest']['path'])
    source.append(gate.pin(synthetic_source))
    source_path = tmp_path / 'epoch-source.json'; gate.save(source_path, source)
    cfg['inputs']['source_manifest'] = gate.pin(source_path)
    path.write_text(json.dumps(cfg))
    bundle = historical_bundle(tmp_path, path)
    old = recovery.historical_condition(bundle)[0]
    gate.save(capture.parent / 'execution-condition.json', old)
    release = recovery._release(cfg)
    for key in recovery.IMPORTED:
        persona, item = key.split('/')
        spec = next(s for s in release[persona]['tests'] if str(s['id']).zfill(3) == item)
        gate.save(capture.parent / 'tests' / (key + '.json'), {'row': {'app_calls': []},
            'attempts': [{'gate_blocked': True}]})
        gate.save(capture.parent / 'grades' / (key + '.json'), {'checks': [
            {'check': i, 'passed': True} for i in range(len(spec['grade']['config']['assertions']))]})
        native = capture.parent / 'native/tests' / key
        gate.save(native / 'pre-action-ruling.json', {'reason': 'policy-refused'})
        gate.save(native / 'app-evidence/state.json', {})
        gate.save(native / 'app-evidence/log.jsonl', {})
        gate.save(native / 'app-evidence/outcome.json', {'completed': True,
            'artifacts': [gate.pin(native / 'app-evidence' / n) for n in ('state.json', 'log.jsonl')]})
    gate.save(capture.parent / 'tests/morgan/129.inflight', {'original': 'intent'})
    recovery.copy_exact(capture.ledger, capture.parent / 'budget.db')
    proofs = tmp_path / 'proofs.json'; gate.save(proofs, capture.proofs)
    qualify((path, receipts))
    output = tmp_path / 'recovery-epoch'
    before = recovery.inventory(capture.parent)
    recovery.prepare_epoch(bundle, path, receipts, capture.parent, output, proofs)
    assert before == recovery.inventory(capture.parent)
    return SimpleNamespace(path=path, receipts=receipts, output=output, parent=capture.parent, bundle=bundle)


def test_real_epoch_preparation_preserves_grades_old_condition_and_incomplete_outcome(epoch):
    e = epoch
    value = recovery.verify_epoch(e.output, e.path)
    assert value['not_single_harness_revision'] is True
    assert value['old_condition_sha256'] != value['new_condition_sha256']
    assert value['imported_ids'] == ['morgan/023', 'morgan/085']
    assert gate.read(e.output / 'native/tests/morgan/129/app-evidence/outcome.json')['completed'] is False
    for key in recovery.IMPORTED:
        assert (e.parent / 'grades' / (key + '.json')).read_bytes() == (e.output / 'grades' / (key + '.json')).read_bytes()
    assert not (e.output / 'tests/morgan/129.inflight').exists()
    for stale in ('run.json', 'launch-admission.json', 'subscription/listener.json', 'apps'):
        assert not (e.output / stale).exists()
    recovery.preflight_resume(e.output, gate.read(e.path))
    with pytest.raises(FileExistsError):
        recovery.prepare_epoch(e.bundle, e.path, e.receipts, e.parent, e.output, e.path.parent / 'proofs.json')


@pytest.mark.parametrize('mutation', ['copied-grade', 'original-snapshot', 'recovery-receipt', 'new-condition'])
def test_inherited_tamper_blocks_real_epoch_before_dispatch(epoch, mutation):
    e = epoch
    if mutation == 'copied-grade': (e.output / 'grades/morgan/023.json').write_text('{}')
    if mutation == 'original-snapshot': (e.parent / 'native/tests/morgan/129/app-evidence/state.json').write_text('{}')
    if mutation == 'recovery-receipt':
        path = e.output / 'recovery-129.json'; data = gate.read(path); data['export_sha256'] = '0' * 64
        path.write_text(json.dumps(data))
    if mutation == 'new-condition':
        data = gate.read(e.path); data['settings']['reader']['reasoning'] = 'medium'; e.path.write_text(json.dumps(data))
    with pytest.raises(ValueError): recovery.verify_epoch(e.output, e.path)


@pytest.mark.parametrize('uncertainty', ['dispatch', 'grade', 'inflight', 'workspace'])
def test_uncertain_epoch_is_refused_before_provider_startup(epoch, uncertainty):
    e = epoch
    selected = {k for group in gate.read(gate.read(e.path)['inputs']['selection']['path'])['groups'].values() for k in group}
    key = next(k for k in sorted(selected) if k not in recovery.IMPORTED | {recovery.RECOVERED})
    if uncertainty == 'dispatch': gate.save(e.output / 'dispatch-intents' / (key + '.json'), {'uncertain': True})
    if uncertainty == 'grade': gate.save(e.output / 'grade-intents' / (key + '.json'), {'uncertain': True})
    if uncertainty == 'inflight': gate.save(e.output / 'tests' / (key + '.inflight'), {'uncertain': True})
    if uncertainty == 'workspace': gate.save(e.output / 'apps' / key / 'state.json', {'uncertain': True})
    with pytest.raises(ValueError, match='Uncertain'): recovery.preflight_resume(e.output, gate.read(e.path))


def test_inherited_charge_cannot_be_removed_even_if_total_stays_under_cap(tmp_path):
    campaign = {'unchanged': True}
    parent = tmp_path / 'parent.db'
    book = BudgetLedger(parent, cap_usd=10, identity=campaign)
    book.reserve('old-paid', phase='judge', request={}, maximum_usd=2)
    book.complete('old-paid', actual_usd=1, usage={'prompt_tokens': 1, 'completion_tokens': 1}, response={})
    book.close()
    current = tmp_path / 'new.db'
    recovery.snapshot_budget(parent, current, campaign)
    with sqlite3.connect(current) as db: db.execute("DELETE FROM calls WHERE call_id='old-paid'")
    with pytest.raises(ValueError, match='modified or removed'):
        recovery.verify_inherited_budget(parent, current, campaign)


def test_native_result_matching_rejects_changed_result_not_just_arguments(capture):
    directory = capture.native / 'calls/tests/gateway-1'
    path = directory / 'request.json'
    request = gate.read(path)
    request['messages'][2]['content'] = json.dumps({'ok': True, 'booking': {'id': 'wrong-booking'}})
    path.write_text(json.dumps(request))
    # Rebind transport/lifecycle evidence to that request to isolate result proof.
    with sqlite3.connect(capture.ledger) as db:
        db.execute('UPDATE calls SET request_sha256=? WHERE call_id=?', (fingerprint(request), directory.name))
    db.close()
    events = [json.loads(line) for line in capture.api.read_text().splitlines()]
    events[2]['messages_sha256'] = fingerprint(request['messages'])
    capture.api.write_text(''.join(json.dumps(e) + '\n' for e in events))
    capture.proofs['api_witness'] = gate.pin(capture.api)
    with pytest.raises(ValueError, match='results disagree'):
        recovery.reconstruct_129(capture.parent, capture.proofs, capture.ledger, capture.spec, capture.sources)


def test_second_repair_epoch_imports_new_completed_case_without_action_replay(epoch, tmp_path, monkeypatch):
    e = epoch
    old = gate.read(e.path)
    selected = {k for group in gate.read(old['inputs']['selection']['path'])['groups'].values() for k in group}
    key = next(k for k in sorted(selected) if k not in recovery.IMPORTED | {recovery.RECOVERED})
    persona, item = key.split('/')
    spec = next(s for s in recovery._release(old)[persona]['tests'] if str(s['id']).zfill(3) == item)
    gate.save(e.output / 'tests' / (key + '.json'), {'row': {'app_calls': []}, 'attempts': [{'gate_blocked': True}]})
    gate.save(e.output / 'grades' / (key + '.json'), {'checks': [
        {'check': i, 'passed': True} for i in range(len(spec['grade']['config']['assertions']))]})
    gate.save(e.output / 'native/tests' / key / 'pre-action-ruling.json', {'reason': 'policy-refused'})
    old_condition = tmp_path / 'before-second-condition.json'; recovery.copy_exact(e.path, old_condition)
    old_manifest = tmp_path / 'before-second-manifest.json'
    recovery.copy_exact(old['inputs']['source_manifest']['path'], old_manifest)
    snapshots = []
    for i, source in enumerate(gate.read(old_manifest)):
        retained = tmp_path / 'before-second-source' / str(i)
        recovery.copy_exact(source['path'], retained)
        snapshots.append({'original': source, 'retained': gate.pin(retained)})
    bundle = tmp_path / 'second-bundle.json'
    gate.save(bundle, {'condition': gate.pin(old_condition), 'source_manifest': gate.pin(old_manifest), 'snapshots': snapshots})
    source_path = tmp_path / 'bounded-harness-source.py'
    source_path.write_text('# harness revision two\n')
    monkeypatch.setattr(recovery, 'REPAIR_SOURCES', recovery.REPAIR_SOURCES | {str(source_path)})
    sources = [gate.pin(p['path']) for p in gate.read(old_manifest)]
    new_manifest = tmp_path / 'second-source.json'; gate.save(new_manifest, sources)
    new = deepcopy(old); new['inputs']['source_manifest'] = gate.pin(new_manifest)
    path = tmp_path / 'second-freeze/condition.json'; gate.save(path, new)
    receipts = tmp_path / 'second-receipts'; qualify((path, receipts))
    output = tmp_path / 'second-epoch'
    transition = recovery.prepare_epoch(bundle, path, receipts, e.output, output, tmp_path / 'proofs.json')
    assert transition['harness_revisions'] == 3
    assert key in transition['imported_ids'] and key in transition['imported_grade_ids']
    assert transition['execution_conditions'][key] == gate.identity(old)
    assert transition['execution_conditions']['morgan/129'] == gate.read(e.output / 'recovery-129.json')['original_condition_sha256']
    for task in recovery.IMPORTED | {key}:
        assert (output / 'grades' / (task + '.json')).read_bytes() == (e.output / 'grades' / (task + '.json')).read_bytes()
    assert recovery.verify_epoch(output, path)['lineage'].startswith('Partial 20 results span three')
    class NeverDispatch:
        def _execute(self, *a): raise AssertionError('imported booking/task dispatched')
        def _grade(self, *a): raise AssertionError('imported completed grade regenerated')
    recovery.execute_once(NeverDispatch(), output, persona, spec, boundary=lambda: recovery.verify_epoch(output, path))


def test_recovered_false_outcome_report_is_complete_and_control_regression_blocks_promotion(epoch, monkeypatch):
    from benchmarks.dolphinbench.pilot_readiness import run_pilot
    from benchmarks.dolphinbench.adapter import AtMemAdapter
    e = epoch
    cfg = gate.read(e.path)
    selected = {k for group in gate.read(cfg['inputs']['selection']['path'])['groups'].values() for k in group}
    historical = {r['id']: r for r in map(json.loads, (recovery.ROOT / 'docs/benchmarks/evidence/dolphin-execution-audit-20261025/task-ledger.jsonl').read_text().splitlines())}
    control = next(k for k in sorted(selected - recovery.IMPORTED - {recovery.RECOVERED}) if historical[k]['passed'])
    for key in selected - recovery.IMPORTED:
        if key != recovery.RECOVERED:
            gate.save(e.output / 'tests' / (key + '.json'), {'row': {'app_calls': []}, 'attempts': [{'gate_blocked': True}]})
            gate.save(e.output / 'native/tests' / key / 'pre-action-ruling.json', {'reason': 'policy-refused'})
        gate.save(e.output / 'grades' / (key + '.json'), {'checks': [
            {'check': i, 'passed': key != control} for i in range(historical[key]['checks_total'])]})
    gate.save(e.output / 'subscription/calls/synthetic/attempt-0/provider-request.json', {
        'url': 'https://chatgpt.com/backend-api/codex/responses',
        'body': {'model': 'gpt-5.6-luna', 'reasoning': {'effort': 'high'}}})
    gate.save(e.output / 'pilot-accounting.json', {'condition_sha256': gate.identity(cfg),
        'complete': True, 'uncertain_usd': 0, 'actual_usd': 0})
    def no_start(*a, **kw): raise AssertionError('Completed epoch started product/app/provider')
    monkeypatch.setattr(AtMemAdapter, '__init__', no_start)
    # The real entry takes its complete-report branch before product/provider startup.
    with pytest.raises(ValueError, match='Regressed'):
        run_pilot(e.path, e.receipts, cfg['inputs']['options']['path'], e.output,
            e.path.parent / 'private-never-read', resume_epoch=True)
    report = gate.read(e.output / 'pilot-report.json')
    assert report['tasks'] == 20 and control in report['regressions']
    assert report['epoch_lineage']['harness_revisions'] == 2
    assert report['original_score_unchanged'] == '390/600'
    assert report['full_600_score'] is None
    assert not gate.read(e.output / 'native/tests/morgan/129/app-evidence/outcome.json')['completed']
    assert not (e.receipts / 'pilot.json').exists()


def test_api_context_mode_proves_no_provider_shutdown_hook_instead_of_inventing_witness(capture):
    proofs = deepcopy(capture.proofs)
    del proofs['shutdown_witness']
    proofs['context_delivery'] = gate.pin(capture.native / 'context-delivery.json')
    evidence, receipt = recovery.reconstruct_129(capture.parent, proofs, capture.ledger, capture.spec, capture.sources)
    assert evidence['row']['duration_ms'] == 12000
    assert 'no provider shutdown hook applies' in receipt['shutdown_basis']
    del proofs['context_delivery']
    with pytest.raises(ValueError, match='Original context-delivery proof'):
        recovery.reconstruct_129(capture.parent, proofs, capture.ledger, capture.spec, capture.sources)


def test_native_provider_uncertain_shutdown_never_uses_context_fallback(capture):
    path = Path(capture.proofs['shutdown_witness']['path'])
    path.write_text(json.dumps({'format': 'atmem-hermes-shutdown-observation-v1',
        'providers': [{'name': 'atmem', 'pending_writes': 1, 'write_errors': 0}],
        'drain': {'status': 'timed_out', 'active_tasks': 1, 'abandoned_writes': 0, 'abandoned_prefetches': 0}}) + '\n')
    capture.proofs['shutdown_witness'] = gate.pin(path)
    with pytest.raises(ValueError, match='Uncertain native shutdown'):
        recovery.reconstruct_129(capture.parent, capture.proofs, capture.ledger, capture.spec, capture.sources)


def test_standard_mcp_metadata_is_preserved_without_inventing_app_logs(tmp_path):
    messages = [{'role': 'assistant', 'tool_calls': [{'id': 'meta',
        'name': 'mcp__dolphinbench_apps__list_resources', 'arguments': {}}]}]
    normalized, receipt = normalize_effective_arguments(messages, [], [])
    assert normalized == messages and not receipt['changes']
    messages[0]['tool_calls'][0]['name'] = 'mcp__dolphinbench_apps__book_flight'
    with pytest.raises(ValueError, match='missing calls'):
        normalize_effective_arguments(messages, [], [])


def test_actual_retained_023_085_129_exports_offline_when_owner_bundle_is_present(actual_harness, monkeypatch):
    map_path = recovery.ROOT / 'specs/048-dolphin-execution-readiness/recovery-inputs.json'
    if not map_path.exists():
        pytest.skip('owner retained evidence bundle is not part of a generic checkout')
    inputs = gate.read(map_path)
    if not Path(inputs['historical_bundle']).exists():
        pytest.skip('owner retained evidence bundle is unavailable')
    old, source = recovery.historical_condition(inputs['historical_bundle'])
    root = Path(old['bindings']['upstream_root'])
    release = recovery._cached_release(str(root), old['inputs']['upstream_manifest']['sha256'])
    parent = Path('/Volumes/MEM/atmem-dolphinbench-20261020/readiness-pilot20-atsys-20261026-v2')
    import urllib.request
    def forbidden(*a, **kw): raise AssertionError('retained offline test dispatched process/provider/app')
    monkeypatch.setattr(urllib.request, 'urlopen', forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    spec = next(s for s in release['morgan']['tests'] if str(s['id']).zfill(3) == '129')
    sources = sorted((root / 'mock_mcp').glob('repair*.py'))
    evidence, proof = recovery.reconstruct_129(parent, gate.read(inputs['proofs_129']),
        Path(inputs['budget_backup']), spec, sources)
    assert source and proof['provider_calls'] == proof['app_calls_dispatched'] == 0
    assert evidence['row']['duration_ms'] == inputs['native129_process_result_duration_ms']
    assert not gate.read(parent / 'native/tests/morgan/129/app-evidence/outcome.json')['completed']
    from benchmarks.dolphinbench.export import export_interaction
    for item in ('023', '085'):
        grade = parent / 'grades/morgan' / (item + '.json'); before = grade.read_bytes()
        native = parent / 'native/tests/morgan' / item
        calls = gate.read(parent / 'tests/morgan' / (item + '.json'))['row'].get('app_calls', [])
        result = export_interaction(native / 'calls', native / 'api-witness.jsonl',
            app_calls=calls, default_source_paths=sources)
        assert result['messages'] and grade.read_bytes() == before


@pytest.mark.parametrize('mutation', ['unknown-effect', 'third-retry', 'grader-path', 'test-source', 'not-real-qualification'])
def test_supervisor_handoff_denies_unsafe_or_unqualified_requests_without_dispatch(epoch, tmp_path, mutation, monkeypatch):
    from benchmarks.dolphinbench import recovery_supervisor as supervisor
    receipt = tmp_path / 'test-receipt.json'
    source = supervisor.test_sources()
    if mutation == 'test-source': source = []
    gate.save(receipt, {'argv': supervisor.TEST_ARGV, 'exit_code': 0, 'source': source})
    request = {'attempt': 3 if mutation == 'third-retry' else 1,
        'changed_paths': ['benchmarks/dolphinbench/judge.py'] if mutation == 'grader-path' else ['benchmarks/dolphinbench/tool_defaults.py'],
        'unknown_side_effect_or_charge': mutation == 'unknown-effect', 'tests': gate.pin(receipt),
        'condition': str(epoch.path), 'receipts': str(epoch.receipts), 'output': str(epoch.output),
        'env_file_path': str(tmp_path / 'private-not-read')}
    path = tmp_path / 'request.json'; gate.save(path, request)
    def no_dispatch(*a, **kw): raise AssertionError('supervisor dispatched an external process')
    monkeypatch.setattr(subprocess, 'Popen', no_dispatch)
    output = tmp_path / 'handoffs'
    with pytest.raises(ValueError):
        supervisor.retry_handoff(recovery.ROOT / 'specs/048-dolphin-execution-readiness/atsys/recovery-task-template.json', path, output)
    assert not output.exists()


def test_current_launch_reservations_allowed_only_inside_live_request_gate(tmp_path):
    import time
    campaign = {'same': True}
    path = tmp_path / 'live.db'
    book = BudgetLedger(path, cap_usd=10, identity=campaign)
    launched = time.time() - 1
    book.reserve('current-request', phase='judge', request={}, maximum_usd=1)
    with pytest.raises(ValueError, match='Unresolved'): recovery.budget_status(path, campaign)
    assert recovery.budget_status(path, campaign, inflight_since=launched) == 0
    with pytest.raises(ValueError, match='Unresolved'):
        recovery.budget_status(path, campaign, inflight_since=time.time() + 1)
    book.connection.execute("UPDATE calls SET reserved=11000000 WHERE call_id='current-request'")
    with pytest.raises(ValueError, match='budget exceeded'):
        recovery.budget_status(path, campaign, inflight_since=launched)
    book.close()


def test_budget_backup_is_standalone_and_hot_journal_is_refused(tmp_path):
    path = tmp_path / 'parent.db'; campaign = {'same': True}
    book = BudgetLedger(path, cap_usd=10, identity=campaign); book.close()
    output = tmp_path / 'snapshot.db'
    recovery.snapshot_budget(path, output, campaign)
    with sqlite3.connect(output) as db: assert db.execute('PRAGMA journal_mode').fetchone() == ('delete',)
    db.close()
    assert not Path(str(output) + '-wal').exists()
    Path(str(path) + '-journal').write_bytes(b'unknown rollback journal')
    with pytest.raises(ValueError, match='rollback journal'):
        recovery.snapshot_budget(path, tmp_path / 'blocked.db', campaign)
    assert not (tmp_path / 'blocked.db').exists()


@pytest.mark.parametrize('mutation', ['missing-gateway', 'extra-ledger'])
def test_recovery_requires_complete_ledger_gateway_bijection(capture, mutation):
    if mutation == 'missing-gateway':
        (capture.native / 'calls/tests/gateway-0/transport.json').unlink()
    else:
        book = BudgetLedger(capture.ledger, cap_usd=10, identity=capture.campaign)
        request = {'model': 'openai/gpt-5.6-luna'}
        book.reserve_subscription('untraced-request', phase='tests', request=request)
        book.complete('untraced-request', actual_usd=0, usage={'prompt_tokens': 1, 'completion_tokens': 1}, response={})
        book.close()
    with pytest.raises(ValueError, match='bijection'):
        recovery.reconstruct_129(capture.parent, capture.proofs, capture.ledger, capture.spec, capture.sources)


def test_returned_execution_is_preserved_before_grading_even_when_runner_did_not_save(tmp_path):
    gate.save(tmp_path / 'execution-condition.json', {'fixed': True})
    calls = []
    class Runner:
        def _execute(self, *a): calls.append('execute'); return {'row': {'raw': 'returned evidence'}}
        def _grade(self, spec, evidence):
            assert gate.read(tmp_path / 'tests/morgan/129.json') == evidence
            calls.append('grade'); return {'checks': []}
    for _ in range(2):
        recovery.execute_once(Runner(), tmp_path, 'morgan', {'id': 129}, boundary=lambda: None)
    assert calls == ['execute', 'grade']
