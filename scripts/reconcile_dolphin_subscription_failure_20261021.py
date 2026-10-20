"""Retain Alex024's actual native terminal failure, without any task replay."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, '/Volumes/AtMemDolphin/upstream')


def main():
    from benchmarks.dolphinbench.driver import private_json
    from benchmarks.dolphinbench.export import export_interaction
    from benchmarks.dolphinbench.gateway import save_new
    from benchmarks.dolphinbench.recording import BudgetLedger, fingerprint
    from graders.mechanical import load_tool_calls
    from harness.submission import check_messages, check_settings, grading_calls
    root = Path('/Volumes/AtMemDolphin/campaign-atmem-v3-matched-luna-high-20261021')
    destination = root / 'repairs/subscription-timeout-terminal-20261021'
    if '--seal-retry-export' in sys.argv:
        original = json.loads((root / 'run.json').read_text())
        revised = copy.deepcopy(original)
        sources = {p.name: fingerprint(p.read_text()) for p in (REPO / 'benchmarks/dolphinbench').glob('*.py')}
        prior = original['configuration']['adapter_source']
        assert {k for k in set(sources) | set(prior) if sources.get(k) != prior.get(k)} == {'export.py'}
        save_new(destination / 'pre-retry-export-run.json', original)
        save_new(destination / 'retry-export-amendment.json', {
            'change': 'Recognize identical native retry identities and retain failed attempts even if later transport succeeds',
            'model_or_tool_replay': False, 'completed_results_changed': False})
        revised['configuration']['adapter_source'] = sources
        private_json(root / 'run.json', revised)
        print('Retry export amendment sealed; no execution replay')
        return
    assert not destination.exists()
    native = root / 'native/tests/alex/024'
    home = Path('/private/tmp/atmem-dolphin-runtime-v3-20261021/profiles/db-d5784f4829d0e5b79126dfcc')
    process = json.loads((native / 'process.json').read_text())
    result = [json.loads(s) for s in process['stdout'].splitlines() if s.startswith('{')]
    terminal = [r for r in result if r.get('type') == 'result']
    assert process['exit_code'] == 1 and len(terminal) == 1
    terminal = terminal[0]
    assert terminal['exit_code'] == 1 and 'HTTP 502' in terminal['error']
    app_calls = load_tool_calls(root / 'apps/alex/024/calls.jsonl')
    export = export_interaction(native / 'calls', home / 'api-witness.jsonl',
        app_calls=app_calls, default_source_paths=Path('/Volumes/AtMemDolphin/upstream/mock_mcp').glob('repair*.py'),
        terminal_failure=terminal)
    check_settings(export['settings'], 'retained native failure')
    check_messages(export['messages'], 'retained native failure')
    saved = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for parent in ('tests', 'grades') for p in (root / parent).glob('*/*.json')}
    original = json.loads((root / 'run.json').read_text())
    revised = copy.deepcopy(original)
    sources = {p.name: fingerprint(p.read_text()) for p in (REPO / 'benchmarks/dolphinbench').glob('*.py')}
    changed = {k for k in set(sources) | set(original['configuration']['adapter_source'])
        if sources.get(k) != original['configuration']['adapter_source'].get(k)}
    assert changed == {'adapter.py', 'export.py', 'gateway.py', 'recording.py', 'subscription_service.py'}, changed
    save_new(destination / 'original-run.json', original)
    reconciled = []
    book = BudgetLedger(root / 'budget.db', cap_usd=249, identity=original['configuration']['campaign'])
    try:
        for failed in export['native_terminal_failure']['failed_attempts']:
            directory = Path(failed['call_directory'])
            request = json.loads((directory / 'request.json').read_text())
            receipt = {'provider': 'OpenAI-Subscription', 'response_delivered': False,
                'http_status': json.loads((directory / 'error.json').read_text())['http_status'],
                'usage': None, 'incremental_api_charge_usd': 0,
                'billing_basis': 'subscription, not paid API; generation outcome unknown'}
            save_new(directory / 'subscription-failure.json', receipt)
            book.settle_subscription_failure(directory.name, request=request, failure_receipt=receipt)
            reconciled.append(directory.name)
    finally:
        book.close()
    save_new(native / 'export.json', export)
    shutil.copyfile(home / 'api-witness.jsonl', native / 'api-witness.jsonl')
    shutil.copyfile(home / 'app_client.provenance.json', native / 'app_client.provenance.json')
    save_new(native / 'profile.json', {'profile_name': home.name, 'campaign_root': str(root), 'ephemeral': True})
    row = {'persona': 'alex', 'test_id': '024', 'messages': export['messages'],
        'duration_ms': terminal['duration_ms'],
        'app_calls': [{k: c[k] for k in ('tool', 'args', 'result') if k in c} for c in app_calls]}
    grading_calls(row, 'retained native failure')
    save_new(root / 'tests/alex/024.json', {'settings': export['settings'], 'row': row,
        'attempts': [{'native_terminal_failure': export['native_terminal_failure'],
            'duration_basis': 'native CLI measured duration; preparation overhead unavailable for this recovered case'}]})
    save_new(destination / 'receipt.json', {'format': 'native-subscription-terminal-failure-recovery-v1',
        'source_amendments': sorted(changed), 'saved_execution_and_grade_sha256': saved,
        'model_memory_or_grading_settings_changed': False,
        'model_tool_or_judge_replay': False, 'terminal_output_origin': 'actual native CLI runtime error',
        'failed_token_usage': None, 'token_totals_lower_bound': True,
        'incremental_subscription_api_charge_usd': 0, 'reconciled_call_ids': reconciled})
    revised['configuration']['adapter_source'] = sources
    private_json(root / 'run.json', revised)
    assert all(hashlib.sha256((root / p).read_bytes()).hexdigest() == h for p, h in saved.items())
    print(json.dumps({'retained_execution': 'alex/024', 'rerun': False, 'saved_files_unchanged': len(saved)}))


if __name__ == '__main__':
    main()
