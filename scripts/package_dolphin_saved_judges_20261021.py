"""Canonicalize judge export copies using upstream clean_message, then package.

Never regrade or call a model. All original judge responses, reasoning metadata,
verdicts and raw API receipts remain unchanged. Replay reads verdict content only.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.append(str(REPO))
sys.path.append('/Volumes/AtMemDolphin/upstream')


def normalize_grade(original):
    from harness.submission import MESSAGE_FIELDS, clean_message
    revised, changes = copy.deepcopy(original), []
    for i, check in enumerate(revised['checks']):
        for j, message in enumerate(check.get('messages', [])):
            extra = set(message) - MESSAGE_FIELDS
            if not extra <= {'refusal', 'reasoning', 'reasoning_details'}:
                raise ValueError('Unexpected judge message field; retain for explicit review')
            if message.get('refusal') is not None:
                raise ValueError('A non-null refusal is not silently discarded')
            cleaned = clean_message(message)
            assert {k: v for k, v in message.items() if k in MESSAGE_FIELDS and v is not None} == cleaned
            if cleaned != message:
                changes.append({'check_position': i, 'message_position': j,
                    'removed_fields': {k: message[k] for k in set(message) - set(cleaned)}})
                check['messages'][j] = cleaned
    assert revised['settings'] == original['settings']
    assert [{k: v for k, v in c.items() if k != 'messages'} for c in revised['checks']] == [
        {k: v for k, v in c.items() if k != 'messages'} for c in original['checks']]
    return revised, changes


def main():
    from benchmarks.dolphinbench.gateway import save_new
    from harness.runner import Runner, run_lock
    from harness.submission import read_release, check_messages
    root = Path('/Volumes/AtMemDolphin/campaign-atmem-v3-matched-luna-high-20261021')
    destination = root / 'repairs/judge-canonical-export-20261021'
    assert not destination.exists()
    paths = sorted((root / 'grades').glob('*/*.json'))
    assert len(paths) == 600 and len(list((root / 'tests').glob('*/*.json'))) == 600
    assert not list((root / 'tests').glob('*/*.inflight'))
    changes, digests, passed = [], {}, 0
    with run_lock(root):
        for path in paths:
            raw = json.loads(path.read_text())
            passed += all(c['passed'] for c in raw['checks'])
            normalized, removed = normalize_grade(raw)
            for check in normalized['checks']:
                if check.get('messages'):
                    check_messages(check['messages'], 'canonical saved judge')
            relative = str(path.relative_to(root))
            digests[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
            save_new(destination / relative, normalized)
            if removed:
                changes.append({'grade': relative, 'original_sha256': digests[relative], 'changes': removed})
        save_new(destination / 'receipt.json', {'format': 'upstream-judge-canonical-export-v1',
            'original_grade_sha256': digests, 'removed_api_extensions_retained_here': changes,
            'canonicalizer': 'unmodified harness.submission.clean_message',
            'model_calls': 0, 'judge_reruns': 0, 'verdicts_changed': False,
            'content_usage_duration_and_settings_changed': False,
            'original_grade_files_changed': False})

        class SavedOnlyRunner(Runner):
            def _path(self, phase, persona, item_id):
                if phase == 'grades':
                    return destination / phase / persona / f'{item_id}.json'
                return super()._path(phase, persona, item_id)

        runner = object.__new__(SavedOnlyRunner)
        runner.directory = root
        runner.release = read_release(Path('/Volumes/AtMemDolphin/upstream'))
        package = runner.package(root / 'submission.zip')
        assert all(hashlib.sha256((root / p).read_bytes()).hexdigest() == h for p, h in digests.items())
        identity = json.loads((root / 'run.json').read_text())['configuration']['campaign']
        save_new(root / 'private-result.json', {'tasks': 600, 'passed': passed,
            'package_validation': package, 'transport_acceptance': 'unconfirmed',
            'historical_reference': {'atmem': '9/30', 'mem0_oss': '7/30'},
            'matched_mem0_rerun': False, 'campaign_identity': identity,
            'canonical_judge_export_receipt': str((destination / 'receipt.json').relative_to(root))})
    print(json.dumps({'tasks': 600, 'passed': passed, 'package_validation': package,
        'original_grades_unchanged': True, 'new_model_calls': 0}), flush=True)


if __name__ == '__main__':
    main()
