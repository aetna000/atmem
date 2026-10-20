"""Derive accurate provider settings without changing any execution or grade.

The native Chat Completions request includes a completion cap that Hermes's
Codex compatibility converter does not forward. Preserve the original ZIP and
all wire bodies; remove only that unsupported setting in a separate artifact.
This policy is fixed before task results are available, not selected by scores.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path('/Volumes/AtMemDolphin/campaign-atmem-v3-system-full-20261021')
UPSTREAM = Path('/Volumes/AtMemDolphin/upstream')
sys.path.append(str(UPSTREAM))
from harness.submission import read_release, read_zip, write_zip

CAPS = ('max_tokens', 'max_completion_tokens', 'max_output_tokens')
MODEL = 'openai/gpt-5.6-luna'


def normalize(tests):
    result = deepcopy(tests)
    removed = []

    def settings(value, location):
        if value.get('model') != MODEL:
            return
        for field in CAPS:
            if field in value:
                removed.append({'location': location, 'field': field, 'requested': value.pop(field)})

    settings(result['settings'], 'tests.settings')
    for index, row in enumerate(result['tests']):
        for message_index, message in enumerate(row['messages']):
            if 'settings' in message:
                settings(message['settings'], f'tests.tests[{index}].messages[{message_index}].settings')
    return result, removed


def main():
    original = ROOT / 'submission.zip'
    output = ROOT / 'submission-actual-provider-settings.zip'
    assert original.exists() and not output.exists()
    observed = 0
    for response in (ROOT / 'subscription-transport/calls').glob('*/normalized-response.json'):
        requests = sorted(response.parent.glob('attempt-*/provider-request.json'))
        body = json.loads(requests[-1].read_text())['body']
        assert body['model'] == 'gpt-5.6-luna'
        assert body.get('reasoning', {}).get('effort') == 'medium'
        assert not any(field in body for field in CAPS), 'An actual applied cap must not be removed'
        observed += 1
    assert observed, 'Actual provider request evidence is required'
    ingestion, native_tests = read_zip(original)
    actual_tests, removed = normalize(native_tests)
    # Everything except the explicitly identified unsupported settings stays
    # byte-defined JSON-equivalent, including calls, outputs, usage and grading.
    restored = deepcopy(actual_tests)
    assert restored['tests'] and len(restored['tests']) == 600
    for item in removed:
        if item['location'] == 'tests.settings':
            target = restored['settings']
        else:
            import re
            match = re.fullmatch(r'tests.tests\[(\d+)\].messages\[(\d+)\].settings', item['location'])
            assert match
            target = restored['tests'][int(match[1])]['messages'][int(match[2])]['settings']
        target[item['field']] = item['requested']
    assert restored == native_tests, 'Normalization changed more than the declared setting fields'
    summary = write_zip(output, ingestion, actual_tests, read_release(UPSTREAM))
    assert read_zip(original) == (ingestion, native_tests)
    assert read_zip(output) == (ingestion, actual_tests)
    receipt = {'format': 'atmem-provider-settings-normalization-v1',
        'original_zip_sha256': hashlib.sha256(original.read_bytes()).hexdigest(),
        'actual_provider_zip_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
        'actual_provider_requests_verified': observed, 'removed_requested_settings': removed,
        'execution_messages_changed': False, 'usage_changed': False, 'grading_changed': False,
        'judge_settings_changed': False, 'original_preserved': True,
        'unmodified_upstream_validation_and_replay': summary}
    with (ROOT / 'actual-provider-settings-receipt.json').open('x') as stream:
        json.dump(receipt, stream, indent=2)
    print(json.dumps({'validated': True, 'settings_normalized': len(removed),
                      'submission': str(output), 'summary': summary}), flush=True)


if __name__ == '__main__':
    main()
