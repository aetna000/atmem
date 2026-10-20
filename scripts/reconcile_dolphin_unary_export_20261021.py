"""One-time, reversible recording-only repair. Never invoke an agent or judge."""
import copy
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, '/Volumes/AtMemDolphin/upstream')

from benchmarks.dolphinbench.driver import private_json
from benchmarks.dolphinbench.export import normalize_dispatch_envelopes
from benchmarks.dolphinbench.gateway import save_new
from benchmarks.dolphinbench.recording import fingerprint
from harness.submission import grading_calls


def main():
    root = Path('/Volumes/AtMemDolphin/campaign-atmem-v3-system-full-20261021')
    repairs = root / 'repairs/unary-export-20261021'
    assert not repairs.exists(), 'Repair already attempted; inspect retained evidence'
    assert not list((root / 'grades').glob('*/*.json')), 'Repair is preregistered before grading'
    run = json.loads((root / 'run.json').read_text())
    revised = copy.deepcopy(run)
    sources = {p.name: fingerprint(p.read_text()) for p in (REPO / 'benchmarks/dolphinbench').glob('*.py')}
    prior = run['configuration']['adapter_source']
    changed = {name for name in set(sources) | set(prior) if sources.get(name) != prior.get(name)}
    assert changed == {'export.py', 'campaign_v3.py'}, changed
    revised['configuration']['adapter_source'] = sources
    path = root / 'tests/morgan/001.json'
    original = json.loads(path.read_text())
    updated = copy.deepcopy(original)
    messages, normalization = normalize_dispatch_envelopes(original['row']['messages'])
    assert len(normalization['changes']) == 1
    updated['row']['messages'] = messages
    assert grading_calls(updated['row'], 'retained first execution') == original['row']['app_calls']
    save_new(repairs / 'original-run.json', run)
    save_new(repairs / 'original-test-morgan-001.json', original)
    save_new(repairs / 'normalized-test-morgan-001.json', updated)
    save_new(repairs / 'receipt.json', {'format': 'recording-only-reconciliation-v1',
        'changes': normalization, 'source_changes': sorted(changed),
        'original_test_sha256': fingerprint(original), 'updated_test_sha256': fingerprint(updated),
        'model_or_tool_rerun': False, 'grading_performed': False,
        'raw_native_export_unchanged': True,
        'method_model_memory_rubric_and_usage_unchanged': True})
    private_json(path, updated)
    private_json(root / 'run.json', revised)
    print(json.dumps({'reconciled': True, 'independent_app_calls_matched': True,
                      'model_or_tool_rerun': False}))


if __name__ == '__main__':
    main()
