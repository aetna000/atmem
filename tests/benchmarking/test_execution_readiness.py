"""Readiness must stop calls at the real boundary, including old entry points."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import time
import sys

import pytest

from benchmarks.dolphinbench.execution_profile import PROFILE, isolated_profile, validate_request
from benchmarks.dolphinbench import readiness as gate
from benchmarks.dolphinbench.adapter import AtMemAdapter
from benchmarks.dolphinbench.safe_runner import InteractionJournal, protected_runner_class


@pytest.fixture
def condition(tmp_path):
    root = Path(__file__).parents[2]
    for name in ['wheel', 'morgan', 'alex', 'riley', 'options']:
        (tmp_path / name).write_text('{}')
    (tmp_path / 'manifest.json').write_text('{"files":{}}')
    source = [* (root / 'benchmarks/dolphinbench').glob('*.py'), root / 'research/retrieval_2310/dolphin_stage.py',
              root / 'specs/048-dolphin-execution-readiness/routes.json',
              root / 'scripts/openrouter_azure_sol.py', root / 'scripts/launch_dolphin_readiness.py',
              root / 'specs/048-dolphin-execution-readiness/runbook.md',
              root / 'specs/048-dolphin-execution-readiness/atsys/run_pilot.py',
              root / 'specs/048-dolphin-execution-readiness/atsys/validate_pilot.py',
              root / '.atsys/tasks/dolphin-readiness-pilot-20.json', Path(sys.executable).resolve(),
              root / 'docs/benchmarks/evidence/dolphin-execution-audit-20261025/task-ledger.jsonl',
              root / 'docs/benchmarks/evidence/dolphin-execution-audit-20261025/pilot-selection.json',
              root / 'docs/benchmarks/evidence/dolphin-execution-audit-20261025/pilot-selection-20-20261026.json']
    gate.save(tmp_path / 'source.json', [gate.pin(p) for p in source])
    inputs = {'wheel': gate.pin(tmp_path / 'wheel'),
              'options': gate.pin(tmp_path / 'options'),
              'upstream_manifest': gate.pin(tmp_path / 'manifest.json'),
              'source_manifest': gate.pin(tmp_path / 'source.json'),
              'selection': gate.pin(root / 'docs/benchmarks/evidence/dolphin-execution-audit-20261025/pilot-selection-20-20261026.json'),
              **{'memory:' + p: gate.pin(tmp_path / p) for p in ['morgan', 'alex', 'riley']}}
    cfg = {'schema': gate.SCHEMA, 'profile': PROFILE, 'inputs': inputs,
           'routes': gate.read(root / 'specs/048-dolphin-execution-readiness/routes.json'),
           'settings': {'reader': {'model': 'openai/gpt-5.6-luna', 'reasoning': 'high', 'max_turns': 60,
                                    'context_length': 1050000},
                        'judge': {'model': 'gpt-5.6-sol', 'reasoning': 'medium', 'output_cap': 8000}},
           'memory_options': gate.MEMORY_OPTIONS,
           'budget': {'caps_usd': {'pilot': 10, 'full': 20}, 'uncertain_charges': 'reserve_until_reconciled'},
           'fixture_disposition': 'retain_original_two_unavailable_cases_in_denominator',
           'bindings': {n: str(tmp_path) for n in ['upstream_root', 'runtime_root', 'memory_root', 'atmem_home', 'controller_site']}}
    cfg['bindings'].update({n: str(Path(sys.executable).resolve()) for n in
                            ['subscription_python', 'product_python', 'app_python']})
    path = tmp_path / 'condition.json'
    gate.save(path, cfg)
    return path, tmp_path / 'receipts'


def qualify(condition):
    path, receipts = condition
    raw = path.parent / 'raw.json'
    gate.save(raw, {'synthetic_raw': True})
    for kind in ['profile', 'apps', 'recovery']:
        gate.receipt(path, kind, {k: True for k in gate.CHECKS[kind]}, [raw], receipts / (kind + '.json'))


def body(name='mcp__dolphinbench_apps__create_doc'):
    return {'tools': [{'type': 'function', 'function': {'name': name, 'parameters': {'type': 'object'}}}],
            'messages': [{'role': 'developer', 'content': 'Synthetic qualification'}]}


@pytest.mark.parametrize('name', ['terminal', 'skill_view', 'execute_code', 'tool_call', 'tool_search',
                                 'mcp__real_github__post_comment', 'mcp__atmem_discovery__forget'])
def test_actual_request_rejects_unsupported_tools(name):
    with pytest.raises(ValueError):
        validate_request(body(name))


def test_supported_config_and_actual_surface_are_distinct():
    original = {'toolsets': ['hermes-cli', 'dolphinbench-apps', 'atmem-discovery']}
    safe = isolated_profile(original)
    assert original['toolsets'][0] == 'hermes-cli'
    assert safe['tools']['tool_search']['enabled'] == 'off'
    assert 'terminal' in safe['agent']['disabled_toolsets']
    assert validate_request(body()) == ['mcp__dolphinbench_apps__create_doc']
    bad = body()
    bad['messages'][0]['content'] += '<available_skills>apple-notes: memo CLI</available_skills>'
    with pytest.raises(ValueError, match='skill catalog'):
        validate_request(bad)


def test_no_receipts_never_admit(condition):
    with pytest.raises(FileNotFoundError):
        gate.admit(*condition, 'pilot')


def test_pilot_admission_and_full_requires_complete_pilot(condition):
    qualify(condition)
    assert gate.admit(*condition, 'pilot')['profile'] == PROFILE
    with pytest.raises(FileNotFoundError):
        gate.admit(*condition, 'full')


@pytest.mark.parametrize('mutation', ['expired', 'future', 'failed', 'different', 'artifact', 'checkpoint'])
def test_bad_receipt_or_input_blocks(condition, mutation):
    qualify(condition)
    path, receipts = condition
    p = receipts / 'profile.json'
    value = gate.read(p)
    if mutation == 'expired': value['created_at'] = time.time() - gate.MAX_AGE - 1
    if mutation == 'future': value['created_at'] = time.time() + 60
    if mutation == 'failed': value['checks']['mcp_only'] = False
    if mutation == 'different': value['condition_sha256'] = 'f' * 64
    if mutation == 'artifact': Path(value['artifacts'][0]['path']).write_text('changed')
    if mutation == 'checkpoint': (path.parent / 'morgan').write_text('changed memory')
    p.write_text(json.dumps(value))
    with pytest.raises(ValueError): gate.admit(path, receipts, 'pilot')


def test_partial_pilot_cannot_be_promoted_with_true_check_flags(condition):
    qualify(condition)
    path, receipts = condition
    selected = gate.read(gate.read(path)['inputs']['selection']['path'])
    ids = [i for group in selected['groups'].values() for i in group]
    raw = path.parent / 'pilot.json'
    gate.save(raw, {'schema': 'dolphin-fixed-pilot-report-v1', 'tasks': 20,
                   'condition_sha256': gate.identity(gate.read(path)), 'regressions': [],
                   'rows': [{'id': i, 'passed': True} for i in ids[:-1]], 'accounting': {'uncertain_usd': 0}})
    gate.receipt(path, 'pilot', {k: True for k in gate.CHECKS['pilot']}, [raw], receipts / 'pilot.json')
    with pytest.raises(ValueError, match='Partial'):
        gate.admit(path, receipts, 'full')


def test_legacy_adapter_stops_before_host_or_provider():
    adapter = AtMemAdapter.__new__(AtMemAdapter)
    adapter.options = {}
    with pytest.raises((ValueError, OSError)):
        adapter.run_interaction(SimpleNamespace(phase='tests'))
    assert not hasattr(adapter, 'hosts')


def test_existing_evidence_is_not_reset(tmp_path):
    class Base:
        def _apps(self, *_args):
            raise AssertionError('Destructive setup was reached')
    runner = protected_runner_class(Base)()
    runner.directory = tmp_path
    workspace = tmp_path / 'apps/person/001'
    workspace.mkdir(parents=True)
    log = workspace / 'calls.jsonl'
    log.write_text('original successful action')
    with pytest.raises(ValueError): runner._apps('tests', 'person', '001', {})
    assert log.read_text() == 'original successful action'


def test_uncertain_journal_refuses_replay_and_preserves_bytes(tmp_path):
    state, log = tmp_path / 'state.json', tmp_path / 'calls.jsonl'
    state.write_text('{"completed":1}')
    log.write_text('one action\n')
    apps = {'env': {'DOLPHINBENCH_STATE_PATH': str(state), 'DOLPHINBENCH_LOG_PATH': str(log)}}
    journal = InteractionJournal(tmp_path / 'journal', apps)
    journal.snapshot(completed=False)
    with pytest.raises(FileExistsError): InteractionJournal(tmp_path / 'journal', apps)
    assert state.read_text() == '{"completed":1}' and log.read_text() == 'one action\n'
    assert not gate.read(tmp_path / 'journal/outcome.json')['completed']

@pytest.mark.parametrize('mutation', ['local_route', 'reader', 'judge', 'memory', 'budget', 'upstream'])
def test_frozen_role_and_settings_drift_blocks(condition, mutation):
    path, receipts = condition
    cfg = gate.read(path)
    if mutation == 'local_route': cfg['routes']['retrieval']['paid_reranker'] = True
    if mutation == 'reader': cfg['settings']['reader']['model'] = 'openai/gpt-5.6-sol'
    if mutation == 'judge': cfg['settings']['judge']['reasoning'] = 'high'
    if mutation == 'memory': cfg['memory_options'] = {**cfg['memory_options'], 'source_bundles': True}
    if mutation == 'budget': cfg['budget']['caps_usd']['pilot'] = float('inf')
    if mutation == 'upstream':
        payload = path.parent / 'task.txt'; payload.write_text('modified')
        (path.parent / 'manifest.json').write_text(json.dumps({'files': {'task.txt': '0' * 64}}))
        cfg['inputs']['upstream_manifest'] = gate.pin(path.parent / 'manifest.json')
    path.write_text(json.dumps(cfg))
    with pytest.raises(ValueError): gate.load_condition(path)


@pytest.fixture
def pilot_evidence(condition):
    path, _ = condition
    cfg = gate.read(path)
    directory = path.parent / 'pilot'
    gate.save(directory / 'execution-condition.json', cfg)
    historical = Path(__file__).parents[2] / 'docs/benchmarks/evidence/dolphin-execution-audit-20261025/task-ledger.jsonl'
    original = {r['id']: r for r in map(json.loads, historical.read_text().splitlines())}
    ids = [i for group in gate.read(cfg['inputs']['selection']['path'])['groups'].values() for i in group]
    for key in ids:
        n = original[key]['checks_total']
        gate.save(directory / 'tests' / (key + '.json'), {'row': {'app_calls': []}, 'attempts': [{'gate_blocked': True}]})
        gate.save(directory / 'grades' / (key + '.json'), {'checks': [{'check': i, 'passed': True} for i in range(n)]})
        gate.save(directory / 'native/tests' / key / 'pre-action-ruling.json', {'reason': 'policy-refused'})
    gate.save(directory / 'native/tests' / ids[0] / 'calls/tests/000/request.json', body())
    gate.save(directory / 'subscription/calls/000/attempt-00/provider-request.json',
        {'url':'https://chatgpt.com/backend-api/codex/responses',
         'body':{'model':'gpt-5.6-luna','reasoning':{'effort':'high'}}})
    gate.save(directory / 'pilot-accounting.json', {'condition_sha256': gate.identity(cfg),
        'complete': True, 'uncertain_usd': 0, 'actual_usd': .5})
    return path, directory, ids


def test_complete_pilot_and_cohorts(pilot_evidence):
    from benchmarks.dolphinbench.pilot_readiness import report
    path, directory, ids = pilot_evidence
    result = report(path, directory)
    assert result['tasks'] == 20 and result['full_600_score'] is None
    assert {r['original_cohort'] for r in result['rows']} == {'pass', 'untraced_zero', 'traced_zero', 'traced_partial'}


@pytest.mark.parametrize('mutation', ['19', 'wrong_id', 'inflight', 'cost', 'journal', 'request'])
def test_pilot_missing_evidence_blocks(pilot_evidence, mutation):
    from benchmarks.dolphinbench.pilot_readiness import report
    path, directory, ids = pilot_evidence
    task = directory / 'tests' / (ids[0] + '.json')
    if mutation == '19': task.unlink()
    if mutation == 'wrong_id': task.rename(task.with_name('999.json'))
    if mutation == 'inflight': task.with_suffix('.inflight').touch()
    if mutation == 'cost':
        p = directory / 'pilot-accounting.json'; data = gate.read(p); data['uncertain_usd'] = .1; p.write_text(json.dumps(data))
    if mutation == 'journal': task.write_text(json.dumps({'row': {'app_calls': []}, 'attempts': []}))
    if mutation == 'request':
        p = next((directory / 'native/tests').glob('*/*/calls/tests/*/request.json')); p.write_text(json.dumps(body('terminal')))
    with pytest.raises(ValueError): report(path, directory)


def test_regression_retains_report_but_blocks_receipt(pilot_evidence):
    from benchmarks.dolphinbench.pilot_readiness import report
    path, directory, ids = pilot_evidence
    historical = Path(__file__).parents[2] / 'docs/benchmarks/evidence/dolphin-execution-audit-20261025/task-ledger.jsonl'
    previous = {r['id']: r for r in map(json.loads, historical.read_text().splitlines())}
    key = next(i for i in ids if previous[i]['passed'])
    grade = directory / 'grades' / (key + '.json'); value = gate.read(grade)
    value['checks'][0]['passed'] = False; grade.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='Regressed'):
        report(path, directory, receipt_output=directory / 'pilot-receipt.json')
    assert (directory / 'pilot-report.json').exists()
    assert not (directory / 'pilot-receipt.json').exists()

@pytest.mark.parametrize('mutation', [None, 'model', 'local_api', 'home', 'assessor', 'outside_pilot'])
def test_effective_options_gate(condition, monkeypatch, mutation):
    path, receipts = condition
    cfg = gate.read(path)
    options = {'campaign_identity': {'agent': cfg['settings']['reader'], 'cap_usd': 10},
        'memory_engine': 'context-v3', 'memory_delivery': 'native-product-api', 'ingestion_mode': 'source-episode',
        'memory_options': gate.MEMORY_OPTIONS, **gate.MEMORY_OPTIONS,
        'baseline_memory_root': cfg['bindings']['memory_root'], 'runtime_root': cfg['bindings']['runtime_root'],
        'upstream_root': cfg['bindings']['upstream_root'], 'app_python': cfg['bindings']['app_python']}
    options_path = Path(cfg['inputs']['options']['path']); options_path.write_text(json.dumps(options))
    cfg['inputs']['options'] = gate.pin(options_path); path.write_text(json.dumps(cfg))
    qualify(condition)
    options = deepcopy(options)
    options.update(readiness_condition=str(path), readiness_receipts=str(receipts), readiness_stage='pilot', execution_profile=PROFILE)
    monkeypatch.setenv('ATMEM_HOME', cfg['bindings']['atmem_home'])
    import urllib.request, io
    payload = json.dumps({'models': [{'name': cfg['routes']['embedding']['model'], 'digest': cfg['routes']['embedding']['digest']}]}).encode()
    monkeypatch.setattr(urllib.request, 'urlopen', lambda *_a, **_k: io.BytesIO(payload))
    if mutation == 'model': options['campaign_identity']['agent']['model'] = 'openai/gpt-5.6-sol'
    if mutation == 'local_api': options['embedding_endpoint'] = 'https://example.test'
    if mutation == 'home': monkeypatch.setenv('ATMEM_HOME', '/another-home')
    if mutation == 'assessor': options['state_assessor'] = {'model': 'paid-model'}
    request = SimpleNamespace(persona='morgan', interaction_id='999') if mutation == 'outside_pilot' else None
    if mutation:
        with pytest.raises(ValueError): gate.require_options(options, request=request)
    else:
        assert gate.require_options(options)['profile'] == PROFILE

@pytest.mark.parametrize('mutation', ['terminal', 'reader_reasoning', 'judge_reasoning'])
def test_http_boundary_rejects_drift_before_forwarding(tmp_path, monkeypatch, mutation):
    import urllib.request, urllib.error
    from benchmarks.dolphinbench.gateway import Gateway
    forwarded = []
    original_urlopen = urllib.request.urlopen
    def checked_open(req, **kwargs):
        if req.full_url.startswith('http://127.0.0.1:1/'):
            forwarded.append(req)
            raise AssertionError('Forbidden request reached provider')
        return original_urlopen(req, **kwargs)
    monkeypatch.setattr(urllib.request, 'urlopen', checked_open)
    judge = mutation == 'judge_reasoning'
    gateway = Gateway(key='synthetic', output=tmp_path / 'calls', ledger_path=tmp_path / 'budget.db',
        campaign_identity={'synthetic': True}, cap_usd=1, phase='judge' if judge else 'tests',
        model='openai/gpt-5.6-sol' if judge else 'openai/gpt-5.6-luna',
        input_per_million=1, output_per_million=1, endpoint='http://127.0.0.1:1/v1/chat/completions',
        execution_profile=None if judge else PROFILE).start()
    try:
        data = body('terminal' if mutation == 'terminal' else 'mcp__dolphinbench_apps__create_doc')
        data.update(model=gateway.model, reasoning_effort='high' if judge else 'medium',
                    max_completion_tokens=8000 if judge else 4096,
                    response_format={'type':'json_object'})
        if mutation == 'terminal': data['reasoning_effort'] = 'high'
        req = urllib.request.Request(gateway.base_url + '/chat/completions',
            data=json.dumps(data).encode(), headers={'Authorization': 'Bearer ' + gateway.local_token})
        with pytest.raises(urllib.error.HTTPError): original_urlopen(req, timeout=5)
        assert not forwarded and not (tmp_path / 'budget.db').exists()
    finally:
        gateway.stop()


def test_superseded_sixty_case_selection_cannot_admit(condition):
    path, _ = condition
    cfg = gate.read(path)
    original = Path(__file__).parents[2] / 'docs/benchmarks/evidence/dolphin-execution-audit-20261025/pilot-selection.json'
    cfg['inputs']['selection'] = gate.pin(original)
    path.write_text(json.dumps(cfg))
    with pytest.raises(ValueError, match='Exactly 20'):
        gate.load_condition(path)
    assert cfg['settings']['reader']['max_turns'] == 60


def test_twenty_one_cases_cannot_pass_pilot(pilot_evidence):
    from benchmarks.dolphinbench.pilot_readiness import report
    path, directory, _ = pilot_evidence
    gate.save(directory / 'tests/alex/999.json', {'row': {}, 'attempts': []})
    with pytest.raises(ValueError, match='fixed selected'):
        report(path, directory)


def test_atsys_recovery_is_inspection_only_before_any_dispatch(tmp_path):
    import subprocess
    root = Path(__file__).parents[2]
    output = tmp_path / 'unstarted'
    result = subprocess.run([sys.executable, str(root / 'specs/048-dolphin-execution-readiness/atsys/run_pilot.py'),
        '--condition', str(tmp_path / 'absent-condition'), '--receipts', str(tmp_path / 'absent-receipts'),
        '--output', str(output), '--env-file', str(tmp_path / 'absent-private-env'),
        '--handoff', str(tmp_path / 'absent-handoff'), '--reconcile-only'], capture_output=True, text=True)
    assert result.returncode == 1 and 'No workload started' in result.stderr
    assert not output.exists() and not (tmp_path / 'absent-receipts').exists()


def test_atsys_stop_terminates_isolated_benchmark_descendants():
    import importlib.util, subprocess, os, signal
    root = Path(__file__).parents[2]
    spec = importlib.util.spec_from_file_location('atsys_pilot_worker', root / 'specs/048-dolphin-execution-readiness/atsys/run_pilot.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    code = 'import subprocess,sys,time; p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"]);print(p.pid,flush=True);time.sleep(30)'
    process = subprocess.Popen([sys.executable, '-c', code], start_new_session=True, stdout=subprocess.PIPE, text=True)
    try:
        descendant = int(process.stdout.readline())
        module.stop_group(process)
        assert process.poll() is not None
        state = subprocess.run(['ps', '-p', str(descendant), '-o', 'stat='], capture_output=True, text=True).stdout.strip()
        assert not state or state.startswith('Z')
    finally:
        try: os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError): pass
        process.wait()


def test_exfat_appledouble_files_are_not_tasks_or_inflight(pilot_evidence):
    from benchmarks.dolphinbench.pilot_readiness import report
    path, directory, ids = pilot_evidence
    task = directory / 'tests' / (ids[0] + '.json')
    task.with_name('._' + task.name).write_bytes(b'AppleDouble metadata, not JSON')
    task.with_name('._' + task.stem + '.inflight').write_bytes(b'metadata')
    assert report(path, directory)['tasks'] == 20


def test_private_app_socket_is_short_and_binds():
    import socket, os
    from benchmarks.dolphinbench.app_bridge import short_socket
    with short_socket() as path:
        assert len(os.fsencode(path)) < 104
        assert path.parent.stat().st_mode & 0o777 == 0o700
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            server.bind(str(path))
    assert not path.parent.exists()
