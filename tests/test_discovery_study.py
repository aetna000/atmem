import json
from hashlib import sha256

import pytest

from atmem.code.discovery import REQUEST
from benchmarks.code_replay.discovery_study import Comparator, definitions
from benchmarks.code_replay.discovery_metrics import usage, summarize_tools


def query(**extra):
    return {'format': REQUEST, 'request_id': 'req', 'turn_id': 'turn',
        'query': 'useful helper', 'limit': 3, 'budget': 4096, **extra}


@pytest.fixture
def native(tmp_path):
    source = b'def useful_helper():\n    return "private body marker"\n'
    (tmp_path / 'main.py').write_bytes(source)
    return Comparator({'workspace': str(tmp_path), 'backend': 'native',
        'source_files': {'main.py': sha256(source).hexdigest()}})


def test_native_real_locator_no_source_body_and_byte_bounds(native):
    result = native.discover(query())
    assert result['items'][0]['title'] == 'useful_helper'
    assert 'private body marker' not in json.dumps(result)
    assert len(json.dumps(native.discover(query(budget=512))).encode()) <= 512


def test_native_revalidates_source_and_never_crosses_snapshot(native):
    (native.root / 'main.py').write_text('def changed(): pass\n')
    assert native.discover(query())['status'] == 'withheld'
    with pytest.raises(PermissionError):
        native.path('outside.py')
    with pytest.raises(ValueError):
        native.discover(query(root='/elsewhere'))


def test_comparator_requires_real_graph_provider_and_identical_tools(tmp_path):
    with pytest.raises(ValueError):
        Comparator({'workspace': str(tmp_path), 'backend': 'cognee'})
    assert [t['name'] for t in definitions()] == ['repository_discover', 'workspace_command']


def test_usage_missing_never_zero_and_cache_not_double_counted():
    assert usage('codex', [])['input_tokens'] is None
    assert usage('copilot', [{'type': 'result', 'total': 1}])['input_tokens'] is None
    result = usage('codex', [{'type': 'turn.completed', 'usage': {
        'input_tokens': 100, 'cached_input_tokens': 40, 'output_tokens': 10}}])
    assert result['input_tokens'] == 100
    result = usage('claude', [{'type': 'result', 'usage': {
        'input_tokens': 20, 'cache_creation_input_tokens': 10, 'cache_read_input_tokens': 40, 'output_tokens': 5}}])
    assert result['input_tokens'] == 70
    assert not usage('codex', [{'type': 'turn.completed', 'usage': {
        'input_tokens': True, 'cached_input_tokens': 0, 'output_tokens': 0}}])['complete']


def test_non_use_and_unobservable_source_reads_are_not_imputed():
    result = summarize_tools([])
    assert not result['treatment_used'] and result['discovery_calls'] == 0
    assert result['source_read_coverage'].endswith('not_inferred')


def test_command_keeps_native_auth_no_api_or_credential_copy(monkeypatch):
    from benchmarks.code_replay.discovery_click import command_for, environment
    monkeypatch.setenv('OPENAI_API_KEY', 'not-for-this-benchmark')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'not-for-this-benchmark')
    monkeypatch.setenv('USER', 'native-account-identity')
    assert 'OPENAI_API_KEY' not in environment() and 'ANTHROPIC_API_KEY' not in environment()
    assert environment()['USER'] == 'native-account-identity'
    config = {'atmem_home': '/fixture'}
    for host in ('claude', 'codex', 'copilot'):
        argv, env = command_for(host, config, 'a fixed task')
        assert not any('OAUTH_TOKEN' in k or k.endswith('API_KEY') for k in env)
        if host == 'claude':
            assert '--bare' not in argv and '--strict-mcp-config' in argv
        if host == 'codex':
            assert '--ignore-user-config' in argv and '--ignore-rules' in argv
            assert 'default_tools_approval_mode' in ' '.join(argv)


def test_launcher_tmpdir_does_not_deny_workspace_scratch(tmp_path):
    from benchmarks.code_replay.discovery_click import source_environment
    env = source_environment(tmp_path, tmp_path / 'bin')
    assert env['TMPDIR'] == '/tmp'
    assert not env['TMPDIR'].startswith(str(tmp_path))


def test_windows_controller_is_campaign_scoped_without_mutating_previous_runs():
    from benchmarks.code_replay.discovery_swebench import worker_source, REMOTE
    source = worker_source()
    assert 'atmem.benchmark=discovery-044-20261020' in source
    assert "!= 'discovery-044-20261020'" in source
    assert "PREFIX = 'atmem-discovery-044-'" in source
    assert 'atmem.benchmark=swebench-lite-20261019' not in source
    assert REMOTE in source


def test_verified_full_count_and_partitioning_do_not_access_solution_fields():
    from tools.freeze_discovery_swebench import partition
    rows = [{'instance_id': 'task-' + str(i), 'repo': 'candidate/repo'} for i in range(500)]
    result = partition(rows)
    assert len(result) == 500
    assert sum(r['partition'] == 'qualification' for r in result) == 5
    assert sum(r['partition'] == 'confirmation' for r in result) == 495
    with pytest.raises(ValueError):
        partition(rows[:-1])


def test_report_does_not_call_an_error_or_empty_lookup_treatment_use():
    from tools.report_discovery_campaign import project
    def envelope(kind, payload):
        return {'envelope': {'event_type': kind, 'payload': payload}}
    rows = [{'run': 'case'}]
    request = {'method': 'tools/call', 'params': {'name': 'repository_discover'}}
    class Vault:
        def inspect(self, principal, run):
            if run == 'campaign':
                return [envelope('discovery.completed', {'rows': rows})]
            return [envelope('discovery.trial_started', {}), envelope('discovery.attempt', {}),
                envelope('discovery.tool_written', {'request': request, 'response': {'error': {}}}),
                envelope('discovery.tool_written', {'request': request, 'response': {'result': {
                    'content': [{'text': json.dumps({'status': 'ready', 'items': []})}]}}})]
    row = project(Vault(), None)['rows'][0]
    assert row['discovery_attempts'] == 2 and row['discovery_errors'] == 1
    assert row['nonempty_discovery_responses'] == 0 and not row['treatment_used']


def test_swe_mcp_initialization_list_and_ping_have_replies(monkeypatch):
    import io
    from benchmarks.code_replay import discovery_swebench as study
    class Vault:
        def capture(self, **kwargs):
            pass
    class Backend:
        def __init__(self, config):
            pass
        def close(self):
            pass
    monkeypatch.setattr(study, 'evidence', lambda root: (Vault(), None))
    monkeypatch.setattr(study, 'Comparator', Backend)
    requests = [{'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-03-26'}},
        {'id': 2, 'method': 'tools/list'}, {'id': 3, 'method': 'ping'}]
    output = io.StringIO()
    monkeypatch.setattr(study.sys, 'stdin', io.StringIO('\n'.join(map(json.dumps, requests)) + '\n'))
    monkeypatch.setattr(study.sys, 'stdout', output)
    study.serve({'evidence_root': '/fixture', 'run_id': 'fixture', 'backend': 'native'})
    replies = [json.loads(line) for line in output.getvalue().splitlines()]
    assert len(replies) == 3 and all('result' in r for r in replies)
    assert [t['name'] for t in replies[1]['result']['tools']] == ['repository_discover', 'workspace_command']


def test_publication_inventory_excludes_external_disk_metadata(tmp_path):
    from tools.publish_discovery_evidence import publication_files
    (tmp_path / 'standalone-recovery.json').write_text('{}')
    (tmp_path / '._standalone-recovery.json').write_bytes(b'\x00\xb0')
    (tmp_path / '.DS_Store').write_bytes(b'\x00\xb0')
    assert [p.name for p in publication_files(tmp_path)] == ['standalone-recovery.json']


def test_dataset_card_has_https_license_and_default_trials_config():
    from pathlib import Path
    import yaml
    text = (Path(__file__).parents[1] / 'docs/evidence/discovery-044-dataset-card.md').read_text()
    metadata = yaml.safe_load(text.split('---', 2)[1])
    assert metadata['license_link'].startswith('https://')
    assert next(c for c in metadata['configs'] if c.get('default'))['config_name'] == 'trials'
