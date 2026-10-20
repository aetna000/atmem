"""Repair saved effective-call serialization without agent/tool/judge reruns."""
import copy
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, '/Volumes/AtMemDolphin/upstream')
from benchmarks.dolphinbench.driver import private_json
from benchmarks.dolphinbench.gateway import save_new
from benchmarks.dolphinbench.recording import fingerprint
from benchmarks.dolphinbench.tool_defaults import normalize_effective_arguments
from harness.submission import grading_calls


def main():
    root = Path('/Volumes/AtMemDolphin/campaign-atmem-v3-product-api-full-20261021')
    destination = root / 'repairs/signature-defaults-20261021'
    assert not destination.exists()
    run = json.loads((root / 'run.json').read_text())
    revised = copy.deepcopy(run)
    sources = {p.name: fingerprint(p.read_text()) for p in (REPO / 'benchmarks/dolphinbench').glob('*.py')}
    prior = run['configuration']['adapter_source']
    assert {k for k in set(sources) | set(prior) if sources.get(k) != prior.get(k)} == {
        'export.py', 'adapter.py', 'tool_defaults.py'}
    revised['configuration']['adapter_source'] = sources
    save_new(destination / 'original-run.json', run)
    repaired = []
    for path in sorted((root / 'tests').glob('*/*.json')):
        original = json.loads(path.read_text())
        updated = copy.deepcopy(original)
        messages, receipt = normalize_effective_arguments(original['row']['messages'],
            original['row'].get('app_calls', []), Path('/Volumes/AtMemDolphin/upstream/mock_mcp').glob('repair*.py'))
        updated['row']['messages'] = messages
        grading_calls(updated['row'], 'retained execution')
        if messages != original['row']['messages']:
            assert not (root / 'grades' / path.parent.name / path.name).exists()
            name = path.parent.name + '-' + path.stem
            save_new(destination / (name + '-original.json'), original)
            save_new(destination / (name + '-normalized.json'), updated)
            save_new(destination / (name + '-receipt.json'), receipt)
            private_json(path, updated)
            repaired.append(name)
    assert repaired == ['morgan-005'], repaired
    save_new(destination / 'receipt.json', {'format': 'effective-default-export-reconciliation-v1',
        'repaired_rows': repaired, 'model_tool_or_judge_rerun': False,
        'explicit_argument_values_changed': False, 'app_calls_and_grading_inputs_changed': False,
        'reversible_originals_and_signature_source_hashes_retained': True})
    private_json(root / 'run.json', revised)
    print(json.dumps({'repaired': repaired, 'rerun': False, 'upstream_validation': 'passed'}))


if __name__ == '__main__':
    main()
