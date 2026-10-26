"""Run/report the fixed diagnostic; never substitute it for a 600-task score."""
from __future__ import annotations
import argparse
import json
import math
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import zipfile

from .execution_profile import PROFILE, validate_request
from .readiness import PILOT_COUNT, CHECKS, admit, identity, load_condition, pin, read, receipt, save, sha
from .safe_runner import protected_runner_class


def selection(condition):
    return {item for group in read(condition['inputs']['selection']['path'])['groups'].values() for item in group}


def report(condition_path, directory, *, receipt_output=None, stage='pilot'):
    condition = load_condition(condition_path)
    directory = Path(directory)
    ledger = Path(__file__).parents[2] / 'docs/benchmarks/evidence/dolphin-execution-audit-20261025/task-ledger.jsonl'
    original = {r['id']: r for r in map(json.loads, ledger.read_text().splitlines())}
    expected = selection(condition) if stage == 'pilot' else set(original)
    count = PILOT_COUNT if stage == 'pilot' else 600
    recorded_identity = read(directory / 'execution-condition.json')
    if recorded_identity != condition:
        raise ValueError('Pilot ran under a different frozen configuration')
    epoch = None
    if (directory / 'epoch-transition.json').exists():
        from .pilot_recovery import verify_epoch
        epoch = verify_epoch(directory, condition_path)
    paths = [p for p in (directory / 'tests').glob('*/*.json') if not p.name.startswith('._')]
    if {p.parent.name + '/' + p.stem for p in paths} != expected or len(paths) != count:
        raise ValueError('Run must contain exactly the fixed selected executions')
    if any(not p.name.startswith('._') for p in (directory / 'tests').rglob('*.inflight')):
        raise ValueError('Uncertain pilot interactions require reconciliation')
    historical = Path(__file__).parents[2] / 'docs/benchmarks/evidence/dolphin-execution-audit-20261025/task-ledger.jsonl'
    original = {r['id']: r for r in (json.loads(line) for line in historical.read_text().splitlines())}
    rows, artifacts = [], [directory / 'execution-condition.json']
    for path in sorted(paths):
        key = path.parent.name + '/' + path.stem
        data = read(path)
        grade_path = directory / 'grades' / path.parent.name / path.name
        checks = read(grade_path)['checks']
        if (len(checks) != original[key]['checks_total'] or
                any(type(c.get('passed')) is not bool or c.get('check') != i for i, c in enumerate(checks))):
            raise ValueError('Pilot grade is partial or differs from original check layout')
        passed = all(c['passed'] for c in checks)
        trace = bool(data['row'].get('app_calls'))
        rows.append({'id': key, 'passed': passed, 'original_passed': original[key]['passed'],
                     'regressed': original[key]['passed'] and not passed,
                     'recovered': not original[key]['passed'] and passed,
                     'trace': trace, 'checks_passed': sum(c['passed'] for c in checks),
                     'original_cohort': ('pass' if original[key]['passed'] else
                         'untraced_zero' if not original[key]['independent_app_trace'] else
                         'traced_zero' if original[key]['checks_passed'] == 0 else 'traced_partial')})
        if epoch is not None:
            rows[-1]['execution_condition_sha256'] = epoch['execution_conditions'].get(key, identity(condition))
            rows[-1]['grade_condition_sha256'] = epoch['grade_conditions'].get(key, identity(condition))
        native = directory / 'native/tests' / key
        ruling = native / 'pre-action-ruling.json'
        blocked = any(a.get('gate_blocked') is True for a in data.get('attempts', []))
        if blocked:
            if not ruling.exists() or read(ruling).get('reason') == 'authorized':
                raise ValueError('Gate-only task lacks refusal evidence: ' + key)
            artifacts.append(ruling)
        else:
            outcome = native / 'app-evidence/outcome.json'
            recovered = epoch is not None and key == epoch['reconstructed_id']
            if not outcome.exists() or (read(outcome).get('completed') is not True and not recovered):
                raise ValueError('Missing completed interaction journal: ' + key)
            if not list((native / 'calls/tests').glob('*/request.json')):
                raise ValueError('Per-task provider request evidence absent: ' + key)
            raw = read(outcome).get('artifacts', [])
            if len(raw) != 2:
                raise ValueError('Missing persisted app state/log: ' + key)
            from .readiness import verify_pin
            artifacts.extend([outcome, *(verify_pin(a) for a in raw)])
        artifacts.extend([path, grade_path])
    # Inspect actual forwarded requests, not a proposed config or CLI flag.
    requests = list((directory / 'native/tests').glob('*/*/calls/tests/*/request.json'))
    if not requests:
        raise ValueError('Actual model-visible pilot request evidence is absent')
    for path in requests:
        validate_request(read(path))
    artifacts.extend(requests)
    artifacts.extend(verify_forwarded_routes(condition, directory))
    accounting = read(directory / 'pilot-accounting.json')
    if (accounting.get('condition_sha256') != identity(condition)
            or accounting.get('uncertain_usd') != 0 or accounting.get('complete') is not True
            or type(accounting.get('actual_usd')) not in (int, float)
            or not 0 <= accounting['actual_usd'] <= condition['budget']['caps_usd'][stage]):
        raise ValueError('Unreconciled or invalid pilot cost accounting')
    artifacts.append(directory / 'pilot-accounting.json')
    if epoch is not None:
        from .pilot_recovery import verify_inherited_budget
        campaign = {**read(condition['inputs']['options']['path'])['campaign_identity'], 'cap_usd': 10}
        spent = verify_inherited_budget(epoch['inherited_budget']['path'], directory / 'budget.db', campaign)
        if not math.isclose(accounting['actual_usd'], spent / 1_000_000, abs_tol=1e-9, rel_tol=0):
            raise ValueError('Report accounting differs from cumulative inherited/new ledger')
    result = {'schema': 'dolphin-fixed-pilot-report-v1' if stage == 'pilot' else 'dolphin-full-report-v1', 'condition_sha256': identity(condition),
              'post_hoc_diagnostic_not_holdout': True, 'tasks': count, 'rows': rows,
              'passed': sum(r['passed'] for r in rows), 'regressions': [r['id'] for r in rows if r['regressed']],
              'recoveries': [r['id'] for r in rows if r['recovered']], 'accounting': accounting,
              'fixture_limitations': ['morgan/085', 'morgan/130'], 'full_600_score': None,
              'self_tested_unverified': True, 'official_submission': False, 'original_score_unchanged': '390/600'}
    if epoch is not None:
        result['epoch_lineage'] = epoch
        result['limitations'] = [epoch['lineage'],
            '390/517 = 75.4% remains conditional, not a full score',
            read(directory / 'recovery-129.json')['duration_basis']]
        artifacts.extend([directory / 'epoch-transition.json', directory / 'recovery-129.json'])
    report_path = directory / ('pilot-report.json' if stage == 'pilot' else 'full-result.json')
    if report_path.exists():
        if read(report_path) != result:
            raise ValueError('Existing report differs; preserve and reconcile')
    else:
        save(report_path, result)
    if receipt_output is not None:
        if result['regressions']:
            raise ValueError('Regressed controls require investigation; report retained, full launch blocked')
        if Path(receipt_output).exists():
            existing = read(receipt_output)
            if (existing.get('kind') != 'pilot' or existing.get('condition_sha256') != identity(condition)
                    or not existing.get('artifacts') or existing['artifacts'][0] != pin(directory / 'pilot-report.json')):
                raise ValueError('Existing pilot receipt differs; preserve and reconcile')
            admit(condition_path, Path(receipt_output).parent, 'full')
        else:
            receipt(condition_path, 'pilot', {k: True for k in CHECKS['pilot']},
                    [directory / 'pilot-report.json', *artifacts], receipt_output)
    return result


def verify_forwarded_routes(condition, directory):
    from urllib.parse import urlsplit
    directory = Path(directory)
    paths = list((directory / 'subscription').glob('calls/*/attempt-*/provider-request.json'))
    paths += list((directory / 'launches').glob('*/subscription/calls/*/attempt-*/provider-request.json'))
    if not paths:
        raise ValueError('Actual subscription provider request evidence absent')
    for path in paths:
        request = read(path)
        body = request['body']
        if (urlsplit(request['url']).hostname != condition['routes']['reader']['endpoint_host']
                or body.get('model') != condition['routes']['reader']['model']
                or body.get('reasoning', {}).get('effort') != condition['routes']['reader']['reasoning']):
            raise ValueError('Actual subscription route differs from frozen reader')
    judge_paths = list((directory / 'judge-calls').glob('judge/*/request.json'))
    judge_paths += list((directory / 'launches').glob('*/judge-calls/judge/*/request.json'))
    for path in judge_paths:
        body = read(path)
        route = condition['routes']['judge']
        if (body.get('model') != route['model'] or body.get('reasoning_effort') != route['reasoning']
                or body.get('max_completion_tokens') != route['max_completion_tokens']
                or body.get('response_format') != {'type': route['response_format']}
                or body.get('provider', {}).get('only') != [route['provider_only']]
                or body.get('provider', {}).get('allow_fallbacks') is not False):
            raise ValueError('Actual judge route differs from frozen judge')
        paths.append(path)
    return paths


def _regressions(directory):
    historical = Path(__file__).parents[2] / 'docs/benchmarks/evidence/dolphin-execution-audit-20261025/task-ledger.jsonl'
    previous = {r['id']: r for r in map(json.loads, historical.read_text().splitlines())}
    return sorted(p.parent.name + '/' + p.stem for p in (directory / 'grades').glob('*/*.json')
                  if not p.name.startswith('._') and previous[p.parent.name + '/' + p.stem]['passed']
                  and not all(c['passed'] for c in read(p)['checks']))


def run_pilot(condition_path, receipts, options_path, output, env_file, *, stage='pilot', resume_epoch=False):
    if resume_epoch:
        from .pilot_recovery import epoch_lock, verify_epoch
        if stage != 'pilot':
            raise ValueError('Recovery is limited to the fixed20 pilot')
        verify_epoch(output, condition_path)
        with epoch_lock(output):
            condition = admit(condition_path, receipts, 'pilot')
            expected = selection(condition)
            if all((Path(output) / 'tests' / (k + '.json')).exists() and
                   (Path(output) / 'grades' / (k + '.json')).exists() for k in expected):
                return report(condition_path, output, receipt_output=Path(receipts) / 'pilot.json')
            return _run_pilot(condition_path, receipts, options_path, output, env_file,
                              stage=stage, resume_epoch=True)
    return _run_pilot(condition_path, receipts, options_path, output, env_file, stage=stage)


def _run_pilot(condition_path, receipts, options_path, output, env_file, *, stage='pilot', resume_epoch=False):
    # Admission and immutable input checks precede output creation and provider startup.
    condition = admit(condition_path, receipts, stage)
    if (Path(sys.executable).resolve() != Path(condition['bindings']['product_python']).resolve()
            or Path(sys.prefix).resolve() != Path(condition['bindings']['product_python']).absolute().parent.parent.resolve()):
        raise ValueError('Controller interpreter differs from frozen installed-product interpreter')
    if condition['bindings']['controller_site'] not in sys.path:
        raise ValueError('Frozen controller dependencies are not active')
    options = read(options_path)
    if pin(options_path) != condition['inputs']['options']:
        raise ValueError('Pilot options file differs from frozen condition')
    bindings = condition['bindings']
    output = Path(output).resolve()
    if output.exists() and not resume_epoch:
        raise ValueError('Fresh pilot output required; reconcile uncertain runs explicitly')
    from .readiness import require_options
    options.update({'readiness_condition': str(Path(condition_path).resolve()),
                    'readiness_receipts': str(Path(receipts).resolve()), 'readiness_stage': stage,
                    'execution_profile': PROFILE, 'env_file': str(env_file)})
    cap = condition['budget']['caps_usd'][stage]
    options['campaign_identity']['cap_usd'] = cap
    if resume_epoch:
        from .pilot_recovery import budget_status, verify_epoch, preflight_resume
        verify_epoch(output, condition_path)
        budget_status(output / 'budget.db', options['campaign_identity'])
        preflight_resume(output, condition)
    require_options(options)
    import atmem
    with zipfile.ZipFile(condition['inputs']['wheel']['path']) as archive:
        for name in archive.namelist():
            if name.startswith('atmem/') and not name.endswith('/'):
                installed = Path(atmem.__file__).parent / name[len('atmem/'):]
                import hashlib
                if hashlib.sha256(installed.read_bytes()).digest() != hashlib.sha256(archive.read(name)).digest():
                    raise ValueError('Executed AtMem package differs from frozen wheel')
    sys.path.insert(0, bindings['upstream_root'])
    from harness.runner import Runner, run_lock
    from harness.submission import read_release
    from .adapter import AtMemAdapter
    from .gateway import Gateway
    from .judge import openrouter_judge
    from .recording import BudgetLedger
    from scripts.openrouter_azure_sol import load_key
    release = read_release(Path(bindings['upstream_root']))
    selected = (selection(condition) if stage == 'pilot' else
                {p + '/' + str(s['id']).zfill(3) for p, entry in release.items() for s in entry['tests']})
    # Only slice IDs; never add required tool/check information to user inputs.
    sliced = {p: {**entry, 'tests': [s for s in entry['tests'] if p + '/' + str(s['id']).zfill(3) in selected]}
              for p, entry in release.items()}
    if not resume_epoch:
        output.mkdir(parents=True)
        save(output / 'execution-condition.json', condition)
    kinds = ('profile', 'apps', 'recovery') + (('pilot',) if stage == 'full' else ())
    launch = output / 'launches' / secrets.token_hex(16) if resume_epoch else output
    lease = launch / 'launch-admission.json'
    lease_value = {'schema': 'dolphin-launch-admission-v1', 'pid': os.getpid(),
        'stage': stage, 'run_root': str(output), 'created_at': time.time(),
        'condition_sha256': identity(condition),
        'receipt_files': [pin(Path(receipts) / (kind + '.json')) for kind in kinds]}
    if resume_epoch:
        lease_value['recovery_transition'] = pin(output / 'epoch-transition.json')
    save(lease, lease_value)
    options['readiness_admission'] = str(lease)
    options['subscription_endpoint'] = 'http://127.0.0.1:1/v1/chat/completions'
    os.environ['ATMEM_SUBSCRIPTION_PROXY_TOKEN'] = secrets.token_urlsafe(32)
    listener = launch / 'subscription/listener.json'
    server = judge = adapter = None
    with (launch / 'subscription-service.log').open('x') as log:
        try:
            adapter = AtMemAdapter(options, output)
            runner = protected_runner_class(Runner)(sliced, output, adapter,
                identity=adapter.identity(), release_root=Path(bindings['upstream_root']))
            runner.allow_paid = True
            server = subprocess.Popen([bindings['subscription_python'], '-I',
                str(Path(__file__).with_name('subscription_service.py')), '--output', str(launch / 'subscription'),
                '--listener-file', str(listener), '--reasoning-effort', condition['routes']['reader']['reasoning'],
                '--model', condition['settings']['reader']['model']],
                env={**os.environ, 'HERMES_HOME': str(Path.home() / '.hermes')},
                stdout=log, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 60
            while not listener.exists():
                if server.poll() is not None or time.monotonic() > deadline:
                    raise ValueError('Subscription startup failed; no scored retry')
                time.sleep(.25)
            while True:
                try:
                    listener_data = read(listener)
                    break
                except json.JSONDecodeError:
                    if time.monotonic() > deadline:
                        raise ValueError('Subscription listener incomplete')
                    time.sleep(.05)
            options['subscription_endpoint'] = listener_data['endpoint']
            with run_lock(output):
                for persona in release:
                    checkpoint = read(condition['inputs']['memory:' + persona]['path'])
                    adapter.verify_checkpoint(persona, checkpoint)
                    checkpoint_path = output / 'checkpoints' / (persona + '.json')
                    if checkpoint_path.exists():
                        if read(checkpoint_path) != checkpoint:
                            raise ValueError('Saved checkpoint differs')
                    else:
                        save(checkpoint_path, checkpoint)
                judge = Gateway(key=load_key(env_file), output=launch / 'judge-calls', ledger_path=adapter.ledger,
                    campaign_identity=options['campaign_identity'], cap_usd=cap,
                    phase='judge', model='openai/gpt-5.6-sol', input_per_million=5,
                    output_per_million=30, output_token_cap=8000, readiness_options=options).start()
                with openrouter_judge(judge):
                    for persona, entry in sliced.items():
                        for spec in entry['tests']:
                            from .pilot_recovery import execute_once
                            def boundary():
                                admit(condition_path, receipts, stage)
                                if resume_epoch:
                                    verify_epoch(output, condition_path)
                                    budget_status(output / 'budget.db', options['campaign_identity'])
                            execute_once(runner, output, persona, spec, boundary=boundary)
                            adapter.verify_checkpoint(persona, read(condition['inputs']['memory:' + persona]['path']))
                            print(json.dumps({'pilot_completed': persona + '/' + str(spec['id']).zfill(3)}), flush=True)
                book = BudgetLedger(adapter.ledger, cap_usd=cap, identity=options['campaign_identity'])
                try:
                    totals = book.totals()
                    unresolved = book.connection.execute(
                        "SELECT COUNT(*) FROM calls WHERE state NOT IN ('completed','unsent')").fetchone()[0]
                finally:
                    book.close()
                save(output / 'pilot-accounting.json', {'condition_sha256': identity(condition), 'complete': unresolved == 0,
                    'unresolved_calls': unresolved,
                    'actual_usd': sum(r['actual_usd'] for r in totals.values()),
                    'uncertain_usd': sum(r['reserved_usd'] for r in totals.values()), 'phase_totals': totals})
            if stage == 'pilot':
                return report(condition_path, output, receipt_output=Path(receipts) / 'pilot.json')
            result = report(condition_path, output, stage='full')
            return result
        finally:
            if judge:
                judge.stop()
            if adapter:
                adapter.stop()
            if server:
                server.terminate()
                try:
                    server.wait(10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--condition', type=Path, required=True)
    parser.add_argument('--receipts', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--options', type=Path)
    parser.add_argument('--env-file', type=Path)
    parser.add_argument('--report-only', action='store_true')
    parser.add_argument('--resume-epoch', action='store_true')
    parser.add_argument('--stage', choices=('pilot', 'full'), default='pilot')
    args = parser.parse_args()
    if args.report_only:
        result = report(args.condition, args.output, receipt_output=args.receipts / 'pilot.json')
    else:
        if not args.options or not args.env_file:
            parser.error('Pilot execution requires frozen options and private env-file path')
        result = run_pilot(args.condition, args.receipts, args.options, args.output, args.env_file,
                           stage=args.stage, resume_epoch=args.resume_epoch)
    print(json.dumps({'tasks': result['tasks'], 'passed': result['passed'], 'regressions': result['regressions']}))


if __name__ == '__main__':
    main()
