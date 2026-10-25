"""Full-run entry point with mandatory execution qualification.

Historical orchestration remains in Git. New campaigns use the frozen condition
and the same guarded dispatch as the fixed pilot. A legacy qualification flag
cannot substitute for the complete evidence bundle.
"""
import argparse
from pathlib import Path


def checkpoint_due(test_id, *, reused_grade):
    return int(test_id) % 10 == 0 and not reused_grade


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--env-file', type=Path, required=True)
    parser.add_argument('--confirm-paid-grading', action='store_true')
    parser.add_argument('--readiness-condition', type=Path, required=True)
    parser.add_argument('--readiness-receipts', type=Path, required=True)
    args = parser.parse_args()
    if not args.confirm_paid_grading:
        parser.error('Explicit full-run paid-grading confirmation required')
    from .readiness import admit
    condition = admit(args.readiness_condition, args.readiness_receipts, 'full')
    from .pilot_readiness import run_pilot
    run_pilot(args.readiness_condition, args.readiness_receipts,
              Path(condition['inputs']['options']['path']), args.output, args.env_file, stage='full')


if __name__ == '__main__':
    main()
