"""Read-only tool delivery audit; never consult expected answers or modify runs."""
import argparse
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from benchmarks.dolphinbench.gateway import save_new


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path('/Volumes/AtMemDolphin/campaign-atmem-v3-matched-luna-high-20261021')
    audited, blocked, missing = [], [], []
    for case in sorted((root / 'tests').glob('*/*.json')):
        persona, case_id = case.parent.name, case.stem
        requests = sorted((root / 'native/tests' / persona / case_id / 'calls/tests').glob('*/request.json'))
        if not requests:
            row = json.loads(case.read_text())
            assert any(a.get('gate_blocked') for a in row['attempts']), 'Missing native API evidence'
            blocked.append(f'{persona}/{case_id}')
            continue
        configuration = json.loads((root / 'apps' / persona / case_id / 'tools.json').read_text())
        active = configuration['active_tools']
        body = json.loads(requests[0].read_text())
        catalog = json.dumps(body['tools'], ensure_ascii=False)
        absent = []
        for tool in active:
            name = tool if isinstance(tool, str) else tool['name']
            if not any(re.search(r'(?<!\w)' + re.escape(prefix + name) + r'(?!\w)', catalog)
                       for prefix in ('mcp__dolphinbench_apps__', 'mcp_dolphinbench_apps_')):
                absent.append(name)
        audited.append({'case': f'{persona}/{case_id}', 'declared_app_tools': len(active),
                        'missing_declared_tools': absent})
        if absent:
            missing.append(audited[-1])
    save_new(args.output, {'format': 'native-tool-catalog-delivery-audit-v1',
        'audited_cases': audited, 'blocked_before_model': blocked, 'catalog_omissions': missing,
        'checked_against': 'supplied per-case active_tools, not expected actions or answers',
        'actor_inputs_or_scores_changed': False, 'inference_calls': 0})
    print(json.dumps({'audited_cases': len(audited), 'blocked_before_model': len(blocked),
                      'catalog_omissions': len(missing), 'inference_calls': 0}), flush=True)


if __name__ == '__main__':
    main()
