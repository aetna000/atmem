"""Summarize recorded subscription usage, never infer ungraded correctness."""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path

from benchmarks.dolphinbench.gateway import save_new
from .evaluate import quantile


def summarize(root: Path) -> dict:
    manifest = json.loads((root/'manifest.json').read_text())
    if (manifest.get('authentication') != 'existing-Hermes-ChatGPT-subscription'
            or manifest.get('paid_fallback') is not False):
        raise ValueError('a declared subscription-only reader campaign is required')
    expected = {(arm, qid) for arm, qid in manifest['cases']}
    if len(expected) != len(manifest['cases']):
        raise ValueError('duplicate expected case')
    groups = defaultdict(list)
    seen = set()
    hashes = {}
    for path in sorted((root/'results').glob('*.json')):
        if path.name.startswith('.'):
            continue
        record = json.loads(path.read_text())
        key = (record['arm'], record['qa_index'])
        if key not in expected or key in seen:
            raise ValueError('unknown or duplicate attempted case')
        seen.add(key)
        response = record.get('response') or {}
        if response and (response.get('provider') != 'OpenAI-Subscription'
                         or response.get('model') != 'openai/'+manifest['reader']):
            raise ValueError('reader model/provider differs from declared subscription run')
        duration = record['duration_ms']
        if type(duration) not in (float, int) or not math.isfinite(duration) or duration < 0:
            raise ValueError('invalid recorded duration')
        usage = response.get('usage') or {}
        known_usage = all(type(usage.get(k)) is int and usage[k] >= 0
                          for k in ('prompt_tokens', 'completion_tokens'))
        # Only the transport's explicit subscription receipt establishes zero
        # incremental API cash. Missing usage is not a zero-token observation.
        known_zero = (usage.get('cost') == 0 and type(usage.get('cost')) in (int, float)
                      and usage.get('cost_basis') ==
                      'incremental_api_charge_zero_subscription_usage_not_free_or_unlimited')
        groups[record['arm']].append((record, usage, known_usage, known_zero))
        hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    arms = {}
    for arm in sorted({arm for arm, _ in expected}):
        rows = groups[arm]
        durations = [r['duration_ms'] for r, _, _, _ in rows]
        arms[arm] = {
            'expected_cases': sum(a == arm for a, _ in expected),
            'attempted_cases': len(rows),
            'transport_errors': sum(r.get('error') is not None for r, _, _, _ in rows),
            'known_prompt_tokens': sum(u['prompt_tokens'] for _, u, known, _ in rows if known),
            'known_completion_tokens': sum(u['completion_tokens'] for _, u, known, _ in rows if known),
            'cases_with_unknown_token_usage': sum(not known for _, _, known, _ in rows),
            'cases_with_confirmed_zero_incremental_api_charge': sum(z for _, _, _, z in rows),
            'reader_p50_ms': quantile(durations, .5) if durations else None,
            'reader_p95_ms': quantile(durations, .95) if durations else None,
            'fully_correct_answers': None,
        }
    return {
        'mode': 'subscription-reader-usage-not-answer-quality',
        'attempted_cases': len(seen), 'expected_cases': len(expected),
        'all_cases_attempted': seen == expected,
        'reader_complete_marker_present': (root/'reader-complete.json').exists(),
        'paid_fallback': False, 'arms': arms,
        'monthly_subscription_fee_not_allocated': True,
        'full_history_control_not_matched_context_budget': True,
        'independent_grading_required': True, 'ready_for_600': False,
        'manifest_sha256': hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest(),
        'result_sha256': hashes,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    save_new(args.output, summarize(args.root))


if __name__ == '__main__':
    main()
