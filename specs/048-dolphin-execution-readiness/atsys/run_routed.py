"""Routed fixed20 command wrapper: durable progress and honest terminal report."""
import argparse
import json
from pathlib import Path
import sys
import threading

import run_pilot

ROOT = run_pilot.ROOT
ARTIFACTS = ROOT / 'specs/048-dolphin-execution-readiness/atsys'


def atomic(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def observe(output):
    executions = len([p for p in (output / 'tests').glob('*/*.json') if not p.name.startswith('._')])
    grades = len([p for p in (output / 'grades').glob('*/*.json') if not p.name.startswith('._')])
    atomic(ARTIFACTS / 'routed-fixed20-progress.json', {
        'completed': executions + grades, 'total': 40,
        'checkpoint': f'{executions}/20 executions, {grades}/20 grades'})


def write_outcome(output, error=None):
    report = json.loads((output / 'pilot-report.json').read_text()) if (output / 'pilot-report.json').exists() else None
    summary = (f"Routed fixed20 diagnostic: {report['passed']}/20 passed; "
               f"{report['recoveries']} recoveries; {len(report['regressions'])} control regressions."
               if report else 'Routed fixed20 diagnostic incomplete; inspect preserved evidence.')
    status = 'passed' if report and not error and not report['regressions'] else 'partial' if report else 'failed'
    limitations = ['Post hoc diagnostic; published 390/600 and prior fixed20 13/20 unchanged.',
                   'Checkpoint disabled; full600 unauthorized.',
                   'Subscription and supervision costs separate from benchmark API ledger.']
    if error:
        limitations.append(str(error)[:2000])
    atomic(ARTIFACTS / 'routed-fixed20-outcome.json', {
        'version': 1, 'summary': summary,
        'results': [{'name': 'fixed20 routed diagnostic', 'status': status,
                     'detail': summary, 'evidence': [str(output / 'pilot-report.json')]}],
        'limitations': limitations})
    text = summary + '\n\nCondition: dolphin-routed-v1; checkpoint=false.\n\n'
    if report:
        text += f"API cost: USD {report['accounting']['actual_usd']}.\n\n"
        text += '| Task | Original cohort | Passed | Recovered | Regressed |\n| --- | --- | --- | --- | --- |\n'
        for row in report['rows']:
            text += '| ' + ' | '.join(str(row[k]) for k in ('id', 'original_cohort', 'passed', 'recovered', 'regressed')) + ' |\n'
    text += '\n' + '\n'.join('- ' + item for item in limitations) + '\n'
    (ARTIFACTS / 'routed-fixed20-report.md').write_text(text)


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--output', type=Path, required=True)
    args, _ = parser.parse_known_args()
    stop = threading.Event()
    def monitor():
        while not stop.is_set():
            observe(args.output)
            stop.wait(30)
    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()
    error = None
    try:
        run_pilot.main()
    except BaseException as exc:
        error = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        stop.set()
        thread.join(5)
        observe(args.output)
        write_outcome(args.output, error)


if __name__ == '__main__':
    main()
