"""Record a recovery-only source amendment; preserve all saved results."""
import copy
import hashlib
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from benchmarks.dolphinbench.driver import private_json
from benchmarks.dolphinbench.gateway import save_new
from benchmarks.dolphinbench.recording import fingerprint


def main():
    root = Path('/Volumes/AtMemDolphin/campaign-atmem-v3-matched-luna-high-20261021')
    destination = root / 'repairs/resume-backup-scheduling-20261021'
    assert not destination.exists()
    original = json.loads((root / 'run.json').read_text())
    revised = copy.deepcopy(original)
    sources = {p.name: fingerprint(p.read_text()) for p in (REPO / 'benchmarks/dolphinbench').glob('*.py')}
    prior = original['configuration']['adapter_source']
    changed = {k for k in set(sources) | set(prior) if sources.get(k) != prior.get(k)}
    assert changed == {'campaign_v3.py'}, changed
    paths = list((root / 'tests').glob('*/*.json')) + list((root / 'grades').glob('*/*.json'))
    saved = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    assert 'tests/morgan/090.json' in saved and 'grades/morgan/090.json' not in saved
    save_new(destination / 'original-run.json', original)
    save_new(destination / 'receipt.json', {'format': 'resume-backup-scheduling-amendment-v1',
        'changed_source': 'campaign_v3.py', 'saved_execution_and_grade_sha256': saved,
        'change': 'Skip repeated cloud backups for already-graded boundaries; verify frozen memory as before',
        'model_memory_or_grading_settings_changed': False,
        'model_tool_or_judge_rerun': False, 'existing_results_changed': False})
    revised['configuration']['adapter_source'] = sources
    private_json(root / 'run.json', revised)
    assert all(hashlib.sha256((root / name).read_bytes()).hexdigest() == digest for name, digest in saved.items())
    print(json.dumps({'source_amendment_recorded': True, 'saved_files_unchanged': len(saved)}))


if __name__ == '__main__':
    main()
