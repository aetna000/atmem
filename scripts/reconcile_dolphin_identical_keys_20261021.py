"""Export saved Alex128; coalesce identical keys only, with no model/tool replay."""
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
    from benchmarks.dolphinbench.recording import fingerprint
    from graders.mechanical import load_tool_calls
    from harness.submission import check_messages, check_settings, grading_calls
    root = Path('/Volumes/AtMemDolphin/campaign-atmem-v3-matched-luna-high-20261021')
    destination = root / 'repairs/identical-argument-keys-20261021'
    assert not destination.exists()
    profile = 'db-' + fingerprint({'run': str(root), 'persona': 'alex', 'phase': 'tests', 'id': '128'})[:24]
    home = Path('/private/tmp/atmem-dolphin-runtime-v3-20261021/profiles') / profile
    native = root / 'native/tests/alex/128'
    process = json.loads((native / 'process.json').read_text())
    assert process['exit_code'] == 0
    results = [json.loads(s) for s in process['stdout'].splitlines() if s.startswith('{')]
    final = [r for r in results if r.get('type') == 'result']
    assert len(final) == 1 and final[0]['exit_code'] == 0
    app_calls = load_tool_calls(root / 'apps/alex/128/calls.jsonl')
    export = export_interaction(native / 'calls', home / 'api-witness.jsonl',
        app_calls=app_calls, default_source_paths=Path('/Volumes/AtMemDolphin/upstream/mock_mcp').glob('repair*.py'))
    changes = export['identical_argument_key_normalization']
    assert len(changes) == 1 and changes[0]['changes'][0]['identical_duplicate_keys'] == ['title']
    check_settings(export['settings'], 'retained execution')
    check_messages(export['messages'], 'retained execution')
    original = json.loads((root / 'run.json').read_text())
    revised = copy.deepcopy(original)
    sources = {p.name: fingerprint(p.read_text()) for p in (REPO / 'benchmarks/dolphinbench').glob('*.py')}
    prior = original['configuration']['adapter_source']
    assert {k for k in set(sources) | set(prior) if sources.get(k) != prior.get(k)} == {'export.py'}
    saved = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for parent in ('tests', 'grades') for p in (root / parent).glob('*/*.json')}
    save_new(destination / 'original-run.json', original)
    save_new(native / 'export.json', export)
    for name in ('api-witness.jsonl', 'app_client.provenance.json'):
        shutil.copyfile(home / name, native / name)
    save_new(native / 'profile.json', {'profile_name': profile, 'campaign_root': str(root), 'ephemeral': True})
    row = {'persona': 'alex', 'test_id': '128', 'messages': export['messages'],
        'duration_ms': final[0]['duration_ms'],
        'app_calls': [{k: c[k] for k in ('tool', 'args', 'result') if k in c} for c in app_calls]}
    grading_calls(row, 'retained execution')
    save_new(root / 'tests/alex/128.json', {'settings': export['settings'], 'row': row,
        'attempts': [{'auxiliary_calls': export['auxiliary_calls'],
            'duration_basis': 'native CLI measured duration; preparation overhead unavailable for this recovered case'}]})
    save_new(destination / 'receipt.json', {'format': 'identical-json-key-export-recovery-v1',
        'source_amendment': 'export.py', 'saved_execution_and_grade_sha256': saved,
        'wire_argument_normalizations': changes, 'model_tool_or_judge_replay': False,
        'conflicting_duplicates_permitted': False, 'argument_values_changed': False,
        'application_results_changed': False, 'model_memory_or_grading_settings_changed': False})
    revised['configuration']['adapter_source'] = sources
    private_json(root / 'run.json', revised)
    assert all(hashlib.sha256((root / p).read_bytes()).hexdigest() == h for p, h in saved.items())
    print(json.dumps({'retained_execution': 'alex/128', 'rerun': False, 'saved_files_unchanged': len(saved)}))


if __name__ == '__main__':
    main()
