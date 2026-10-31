"""Exact-command AtSys worker for the owner-authorized 600-task routed run.

One launch only (durable intent), the launcher's ``--stage full --confirm-full-run``
path under the already validated condition, saved execution/grade progress out of
600, and an honest terminal summary even on failure. ``--reconcile-only`` never
launches: it summarizes an existing ``full-result.json`` or exits non-zero.
"""
from pathlib import Path
import argparse
import json
import threading

import run_pilot
from run_pilot import ROOT, supervised_command
from benchmarks.dolphinbench.readiness import admit, identity, pin, read, save

ARTIFACTS = ROOT / 'specs/048-dolphin-execution-readiness/atsys'
TOTAL = 600


def atomic(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def count(directory):
    return len([p for p in directory.glob('*/*.json') if not p.name.startswith('._')]) if directory.exists() else 0


def observe(output, prefix):
    executions, grades = count(output / 'tests'), count(output / 'grades')
    atomic(ARTIFACTS / f'{prefix}-progress.json', {'completed': executions + grades, 'total': 2 * TOTAL,
                                                   'checkpoint': f'{executions}/{TOTAL} executions, {grades}/{TOTAL} grades'})


def summarize(args, prefix, error=None):
    result_path = args.output / 'full-result.json'
    result = read(result_path) if result_path.exists() else None
    if result:
        summary = (f"Routed full DolphinBench (dolphin-routed-v4): {result['passed']}/{TOTAL} passed; "
                   f"{len(result['recoveries'])} recoveries and {len(result['regressions'])} regressions versus "
                   f"the original 390/600 run.")
        value = {'condition_sha256': result['condition_sha256'], 'output': str(args.output), 'tasks': result['tasks'],
                 'passed': result['passed'], 'recoveries': len(result['recoveries']),
                 'regressions': len(result['regressions']), 'actual_usd': result['accounting']['actual_usd'],
                 'result': pin(result_path), 'self_tested_unverified': True, 'official_submission': False}
        atomic(args.summary, value)
    else:
        summary = 'Routed full DolphinBench incomplete; inspect preserved evidence. No replay was started.'
    status = 'passed' if result and not error else 'failed'
    limitations = ['Self-tested, not an official submission; the published 390/600 is unchanged until reviewed.',
                   'Subscription and supervision costs are separate from the benchmark API ledger.']
    if error:
        limitations.append(str(error)[:2000])
    atomic(ARTIFACTS / f'{prefix}-outcome.json', {'version': 1, 'summary': summary,
           'results': [{'name': 'full 600 routed run', 'status': status, 'detail': summary,
                        'evidence': [str(result_path)]}], 'limitations': limitations})
    text = summary + '\n\nCondition: dolphin-routed-v4 (verified standing facts, routing guard, checkpoint).\n\n'
    if result:
        text += f"API cost: USD {result['accounting']['actual_usd']}.\n\n"
        cohorts = {}
        for row in result['rows']:
            c = cohorts.setdefault(row['original_cohort'], [0, 0])
            c[0] += 1
            c[1] += bool(row['passed'])
        text += '| Original cohort | Tasks | Passed |\n| --- | ---: | ---: |\n'
        text += ''.join(f'| {k} | {v[0]} | {v[1]} |\n' for k, v in sorted(cohorts.items()))
    text += '\n' + '\n'.join('- ' + item for item in limitations) + '\n'
    (ARTIFACTS / f'{prefix}-report.md').write_text(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('condition', 'receipts', 'output', 'env-file', 'summary'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--reconcile-only', action='store_true')
    args = parser.parse_args()
    args.output = args.output.resolve()
    prefix = args.summary.stem.removesuffix('-summary')
    if args.reconcile_only:
        if not (args.output / 'full-result.json').exists():
            parser.exit(1, 'No completed full result; inspect uncertain work. No workload started.\n')
        summarize(args, prefix)
        return
    admit(args.condition, args.receipts, 'full')
    intent = args.receipts / 'atsys-full-launch-intent.json'
    if args.output.exists() or intent.exists():
        parser.exit(1, 'Existing output or launch intent: refusing a second full launch. Use inspect-only recovery.\n')
    save(intent, {'schema': 'dolphin-atsys-full-one-launch-v1', 'output': str(args.output),
                  'condition': pin(args.condition), 'condition_sha256': identity(read(args.condition)),
                  'atsys_task_id': run_pilot.os.getenv('ATSYS_TASK_ID')})
    stop = threading.Event()
    def monitor():
        while not stop.is_set():
            observe(args.output, prefix)
            stop.wait(60)
    threading.Thread(target=monitor, daemon=True).start()
    error = None
    try:
        supervised_command(['/usr/bin/caffeinate', '-i', '-s', '/opt/homebrew/bin/python3',
                            str(ROOT / 'scripts/launch_dolphin_readiness.py'), '--condition', str(args.condition),
                            '--receipts', str(args.receipts), '--output', str(args.output),
                            '--env-file', str(args.env_file), '--stage', 'full', '--confirm-full-run'])
    except BaseException as exc:
        error = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        stop.set()
        observe(args.output, prefix)
        summarize(args, prefix, error)


if __name__ == '__main__':
    main()
