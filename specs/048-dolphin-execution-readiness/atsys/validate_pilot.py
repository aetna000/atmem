"""Read-only AtSys acceptance: retained qualified pilot, never worker assertions."""
from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from benchmarks.dolphinbench.readiness import admit, identity, read


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--condition', type=Path, required=True)
    parser.add_argument('--receipts', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--handoff', type=Path, required=True)
    args = parser.parse_args()
    report_path = args.output / 'pilot-report.json'
    if not report_path.is_file() or not args.handoff.is_file():
        parser.exit(1, 'Pilot report or handoff missing; readiness is incomplete.\n')
    # This validates complete fixed 20-ID evidence, artifact hashes, cost and freshness.
    # It authorizes no paid call and does not launch a full campaign.
    condition = admit(args.condition, args.receipts, 'full')
    pilot_receipt = read(args.receipts / 'pilot.json')
    if Path(pilot_receipt['artifacts'][0]['path']).resolve() != report_path.resolve():
        parser.exit(1, 'Pilot receipt belongs to another output directory.\n')
    report, handoff = read(report_path), read(args.handoff)
    expected = {'condition_sha256': identity(condition), 'pilot_output': str(args.output.resolve()),
                'tasks': 20, 'passed': report['passed'], 'regressions': report['regressions'],
                'actual_usd': report['accounting']['actual_usd'],
                'decision': 'pilot_passed_full_launch_requires_owner_authorization'}
    if any(handoff.get(key) != value for key, value in expected.items()):
        parser.exit(1, 'Worker handoff does not match independently validated evidence.\n')
    print('Validated: fixed 20-task pilot, costs and evidence. Full 600 not launched.')


if __name__ == '__main__':
    main()
