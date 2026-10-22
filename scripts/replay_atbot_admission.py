"""Replay one real, recorded AtBot proposal response through AtMem admission.

Diagnostic only: the intelligence response is replayed, not a live end-to-end
benchmark. No model calls, automatic approvals, test answers or custom admission
rules are used. Existing benchmark stores and configurations are untouched.
"""
import argparse
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.output.resolve()
    root.relative_to(Path('/Volumes/AtMemDolphin'))
    root.mkdir(mode=0o700)
    if not os.environ.get('ATMEM_HOME', '').startswith('/Volumes/AtMemDolphin/'):
        raise ValueError('An isolated external AtMem Home is required')
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from benchmarks.dolphinbench.driver import AtMemHost
    from benchmarks.dolphinbench.gateway import save_new
    recorded = json.loads(Path('/Volumes/AtMemDolphin/atbot-semantic-diagnostic/result.json').read_text())
    source = json.loads(Path('/Volumes/AtMemDolphin/campaign-atmem-239-frozen/ingestion/morgan/000001.json').read_text())
    message = next(row['content'] for row in source['row']['messages'] if row['role'] == 'user')
    host = AtMemHost(root / 'memory', 'recorded-admission')
    try:
        with patch('atmem.control.atbot_companion.AtBotCompanionClient.propose', return_value=recorded['result']):
            result = host.manager.capture(message, authenticated_user=True,
                subject_id=host.admin.subject_id, agent_id='main', session_id='diagnostic-replay')
        row = host.service._load(host.binding['binding_id'])
        checkpoint = host.service._canonical_checkpoint(row)
        save_new(root / 'result.json', {'diagnostic_only': True, 'intelligence_replayed': True,
            'real_recorded_model_output': True, 'new_provider_calls': 0, 'manual_approvals': 0,
            'model_proposals': len(recorded['result']['proposals']),
            'capture': result, 'canonical_checkpoint': checkpoint})
        print(json.dumps({'diagnostic_only': True, 'intelligence_replayed': True,
            'model_proposals': len(recorded['result']['proposals']),
            'canonical_records': checkpoint['record_count'],
            'admission_decisions': [row.get('decision') for row in result.get('admissions', [])]}), flush=True)
    finally:
        host.stop()


if __name__ == '__main__':
    main()
