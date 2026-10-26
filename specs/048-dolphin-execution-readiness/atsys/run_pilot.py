"""Exact-command AtSys worker: one qualified pilot launch, inspect-only recovery."""
from pathlib import Path
import argparse
import json
import os
import statistics
import signal
import time
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from benchmarks.dolphinbench.readiness import PILOT_COUNT, admit, identity, pin, read, save


def stop_group(child):
    """Stop only the isolated benchmark process group; uncertainty stays on disk."""
    try:
        os.killpg(child.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    time.sleep(.25)
    try:
        os.killpg(child.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except PermissionError:
        # Darwin can return EPERM for a group containing only reaped/zombie
        # descendants. Ignore it only when there are no live group members.
        listing = subprocess.run(['/bin/ps', '-axo', 'pgid=,stat='], check=True,
                                 capture_output=True, text=True).stdout
        live = [row for row in listing.splitlines() if len(row.split()) >= 2
                and row.split()[0] == str(child.pid) and not row.split()[1].startswith('Z')]
        if live:
            raise
    child.wait(timeout=1)


def supervised_command(command):
    parent = os.getppid()
    child = subprocess.Popen(command, cwd=ROOT, start_new_session=True)
    def interrupted(signum, _frame):
        stop_group(child)
        raise SystemExit(128 + signum)
    prior = {s: signal.signal(s, interrupted) for s in (signal.SIGTERM, signal.SIGINT)}
    try:
        while child.poll() is None:
            if os.getppid() != parent:
                stop_group(child)
                raise RuntimeError('AtSys runner disappeared; uncertain benchmark evidence retained')
            time.sleep(.2)
        if child.returncode:
            raise subprocess.CalledProcessError(child.returncode, command)
    finally:
        if child.poll() is None:
            stop_group(child)
        for s, handler in prior.items():
            signal.signal(s, handler)


def handoff(args):
    condition = admit(args.condition, args.receipts, 'full')
    report_path = args.output / 'pilot-report.json'
    receipt = read(args.receipts / 'pilot.json')
    if Path(receipt['artifacts'][0]['path']).resolve() != report_path.resolve():
        raise ValueError('Pilot receipt belongs to another output')
    report = read(report_path)
    durations = [read(p)['row']['duration_ms'] for p in (args.output / 'tests').glob('*/*.json')]
    cohorts = {}
    for row in report['rows']:
        cohort = cohorts.setdefault(row['original_cohort'], {'tasks': 0, 'passed': 0, 'recoveries': 0})
        cohort['tasks'] += 1; cohort['passed'] += row['passed']; cohort['recoveries'] += row['recovered']
    value = {'condition_sha256': identity(condition), 'pilot_output': str(args.output.resolve()),
             'tasks': PILOT_COUNT, 'passed': report['passed'], 'regressions': report['regressions'],
             'actual_usd': report['accounting']['actual_usd'],
             'decision': 'pilot_passed_full_launch_requires_owner_authorization',
             'cohorts': cohorts, 'recoveries': report['recoveries'],
             'median_task_ms': statistics.median(durations),
             'fixture_limitations': report['fixture_limitations'],
             'post_hoc_diagnostic_not_holdout': True,
             'orchestration': {'worker': 'exact-command', 'atsys_task_id': os.getenv('ATSYS_TASK_ID'),
                               'supervision_cost': 'not available in benchmark ledger; separately accounted'},
             'full_600_launched': False}
    if args.handoff.exists():
        prior = read(args.handoff)
        if any(prior.get(k) != value[k] for k in ('condition_sha256', 'pilot_output', 'tasks', 'passed', 'regressions', 'actual_usd')):
            raise ValueError('Existing handoff differs; preserve it and reconcile')
    else:
        save(args.handoff, value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('condition', 'receipts', 'output', 'env-file', 'handoff'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--reconcile-only', action='store_true')
    args = parser.parse_args()
    args.output = args.output.resolve()
    # A retry can validate already completed work; it cannot dispatch another call.
    if args.reconcile_only:
        if not (args.output / 'pilot-report.json').exists():
            parser.exit(1, 'No completed report; inspect uncertain work before any manual recovery. No workload started.\n')
    else:
        admit(args.condition, args.receipts, 'pilot')
        if args.output.exists():
            parser.exit(1, 'Existing output: refusing scored replay. Use inspect-only recovery.\n')
        save(args.receipts / 'atsys-launch-intent.json', {'schema': 'dolphin-atsys-one-launch-v1',
             'output': str(args.output), 'condition': pin(args.condition), 'atsys_task_id': os.getenv('ATSYS_TASK_ID')})
        command = ['/usr/bin/caffeinate', '-i', '-s', '/opt/homebrew/bin/python3', str(ROOT / 'scripts/launch_dolphin_readiness.py'),
                   '--condition', str(args.condition), '--receipts', str(args.receipts),
                   '--output', str(args.output), '--env-file', str(args.env_file), '--stage', 'pilot']
        supervised_command(command)
    result = handoff(args)
    print(json.dumps({'pilot_tasks': result['tasks'], 'passed': result['passed'],
                      'regressions': result['regressions'], 'full_600_launched': False}), flush=True)


if __name__ == '__main__':
    main()
