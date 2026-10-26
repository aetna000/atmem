"""Bounded supervisor handoff, never an arbitrary command/approval bypass.

The coding worker edits only the workspace. The trusted parent runs qualification,
freeze, epoch preparation and continuation outside that sandbox after review.
This utility verifies the resulting handoff; it never runs supplied shell code.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from .pilot_recovery import ROOT, REPAIR_SOURCES, preflight_resume, verify_epoch
from .readiness import admit, pin, read, save, verify_pin

TEST_ARGV = ['/Users/javadtaghia/miniconda3/bin/python', '-m', 'pytest', '-q',
    'tests/benchmarking/test_dolphin_pilot_recovery.py',
    'tests/benchmarking/test_execution_readiness.py',
    'tests/benchmarking/test_dolphinbench_campaign_gate.py',
    'tests/benchmarking/test_dolphin_campaign_resume.py',
    'tests/benchmarking/test_dolphinbench_gateway.py']


def test_sources():
    from .readiness import qualification_sources
    return qualification_sources() + [pin(ROOT / p) for p in TEST_ARGV[4:]]


def check_scope(paths):
    for value in paths:
        path = Path(value)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('Repair path outside workspace')
        relative = path.as_posix()
        if relative not in REPAIR_SOURCES and not (
                (relative.startswith('tests/benchmarking/test_dolphin') and path.suffix == '.py') or
                relative == 'tests/benchmarking/test_execution_readiness.py' or
                (relative.startswith('specs/048-dolphin-execution-readiness/') and path.suffix == '.md') or
                relative == 'docs/benchmarks/dolphin-lessons-and-readiness.md'):
            raise ValueError('Repair outside harness/export/recovery tests/docs: ' + relative)
        # Never allow fixture/result/review evidence writes hidden below docs.
        if any(p in path.parts for p in ('fixtures', 'results', 'review', 'atsys')):
            raise ValueError('Historical/control evidence is outside coding repair scope')


def retry_handoff(contract_path, request_path, output):
    contract, request = read(contract_path), read(request_path)
    if (contract.get('allowRepair') is not True or contract.get('maxRetries') != 2
            or contract.get('worker') != 'codex' or contract.get('cwd') != str(ROOT)):
        raise ValueError('Bounded workspace coding contract required')
    attempt = request.get('attempt')
    if type(attempt) is not int or not 1 <= attempt <= 2:
        raise ValueError('At most two reviewed repair attempts')
    if request.get('unknown_side_effect_or_charge') is not False:
        raise ValueError('Unknown side effect/charge must escalate')
    check_scope(request['changed_paths'])
    # Immutable test receipt must bind the exact command and current source bytes.
    test = read(verify_pin(request['tests']))
    if test.get('argv') != TEST_ARGV or test.get('exit_code') != 0:
        raise ValueError('Focused tests have not passed')
    condition = admit(request['condition'], request['receipts'], 'pilot')
    from .readiness import qualification_sources, identity
    if test.get('source') != test_sources():
        raise ValueError('Tests were run against another source revision')
    epoch = verify_epoch(request['output'], request['condition'])
    preflight_resume(request['output'], condition)
    if Path(request['output']).resolve() == Path(epoch['parent']).resolve():
        raise ValueError('Retry must use a new immutable epoch')
    # Inspect raw source-bound real qualification reports as well as normal receipts.
    from .readiness import CHECKS
    for kind in ('profile', 'apps', 'recovery'):
        item = read(Path(request['receipts']) / (kind + '.json'))
        reports = [read(a['path']) for a in item['artifacts'] if Path(a['path']).name == 'qualification.json']
        if len(reports) != 1:
            raise ValueError('Real zero-call qualification report required: ' + kind)
        report = reports[0]
        if (report.get('model_calls') != 0 or report.get('source') != qualification_sources()
                or any(report.get(k) is not True for k in CHECKS[kind])):
            raise ValueError('Fresh executing-source qualification failed: ' + kind)
    # Reuse the actual qualification issuer's complete checks: original runtime,
    # adapter builder, native tool array, bridge outcomes73/0 and raw snapshots.
    # These temporary receipts are validation output only, never launch authority.
    from .readiness import issue_qualifications
    profile_receipt = read(Path(request['receipts']) / 'profile.json')
    apps_receipt = read(Path(request['receipts']) / 'apps.json')
    profile_dir = next(Path(a['path']).parent for a in profile_receipt['artifacts'] if Path(a['path']).name == 'qualification.json')
    apps_dir = next(Path(a['path']).parent for a in apps_receipt['artifacts'] if Path(a['path']).name == 'qualification.json')
    with tempfile.TemporaryDirectory() as temporary:
        issue_qualifications(request['condition'], profile_dir, apps_dir, temporary)
    # No command is executed here. Parent receives a fixed, reviewable launcher.
    argv = ['/opt/homebrew/bin/python3', str(ROOT / 'scripts/launch_dolphin_readiness.py'),
        '--condition', str(Path(request['condition']).resolve()),
        '--receipts', str(Path(request['receipts']).resolve()),
        '--output', str(Path(request['output']).resolve()), '--env-file', request['env_file_path'],
        '--stage', 'pilot', '--resume-epoch']
    handoff = {'schema': 'dolphin-supervised-repair-handoff-v1', 'attempt': attempt,
        'contract': pin(contract_path), 'request': pin(request_path),
        'condition_sha256': identity(condition), 'epoch': pin(Path(request['output']) / 'epoch-transition.json'),
        'parent_execution_required': True, 'coding_worker_may_execute': False,
        'argv': argv, 'no_automatic_execution': True}
    for prior in Path(output).glob('retry-*.json'):
        previous = read(prior)
        if previous['epoch'] == handoff['epoch']:
            raise ValueError('Each retry requires a new immutable epoch')
    # One persistent intent for this attempt; retrying the handoff cannot grant a
    # second dispatch. The epoch also has its own lock and O_EXCL task intents.
    save(Path(output) / ('retry-' + str(attempt) + '.json'), handoff)
    return handoff


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    tests = commands.add_parser('test')
    tests.add_argument('--receipt', type=Path, required=True)
    retry = commands.add_parser('handoff')
    for name in ('contract', 'request', 'output'):
        retry.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'test':
        from .readiness import qualification_sources
        import os
        source = test_sources()
        result = subprocess.run(TEST_ARGV, cwd=ROOT,
            env={**os.environ, 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1'}, check=False)
        if source != test_sources():
            raise ValueError('Source changed during tests')
        save(args.receipt, {'argv': TEST_ARGV, 'exit_code': result.returncode, 'source': source})
        raise SystemExit(result.returncode)
    print(json.dumps(retry_handoff(args.contract, args.request, args.output), indent=2))


if __name__ == '__main__':
    main()
