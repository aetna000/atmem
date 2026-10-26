"""Trusted AtSys parent: qualify a bounded repair and continue without action replay.

This file and its contract/independent validator are outside coding-repair scope.
No workload can start until the separate implementation task is validated.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def raw(path):
    return json.loads(Path(path).read_text())


def pinned_json(entry):
    if fingerprint(entry['path']) != entry['sha256']:
        raise ValueError('Trusted pinned referent changed: ' + entry['path'])
    return raw(entry['path'])


def fingerprint(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checked_contract(path):
    value = raw(path)
    covered = {str(Path(item['path']).resolve()) for item in value['trusted_files']}
    required = [Path(__file__).resolve(), Path(value['independent_validator']).resolve(),
        ROOT / 'specs/048-dolphin-execution-readiness/atsys/run_pilot.py',
        ROOT / 'specs/048-dolphin-execution-readiness/atsys/validate_pilot.py',
        *(Path(value[k]).resolve() for k in ('descriptor', 'historical_bundle', 'proofs'))]
    if not {str(p) for p in required} <= covered:
        raise ValueError('Trusted controller/validator pin missing')
    for item in value['trusted_files']:
        if fingerprint(item['path']) != item['sha256']:
            raise ValueError('Trusted controller/validator changed; repair cannot approve itself')
    if value['pilot_tasks'] != 20 or value['cumulative_cap_usd'] != 10 or value['full600_authorized'] is not False:
        raise ValueError('Parent contract changes benchmark authority')
    return value


# Parent-owned policy is deliberately independent of repair-writable gates.
REPAIR_PATHS = frozenset({str(ROOT / p) for p in (
    'benchmarks/dolphinbench/tool_defaults.py', 'benchmarks/dolphinbench/pilot_readiness.py',
    'benchmarks/dolphinbench/readiness.py', 'benchmarks/dolphinbench/pilot_recovery.py',
    'benchmarks/dolphinbench/recovery_supervisor.py', 'scripts/launch_dolphin_readiness.py')})


def parent_source_guard(contract):
    bundle = raw(contract['historical_bundle'])
    original = pinned_json(bundle['source_manifest'])
    before = {p['path']: p['sha256'] for p in original}
    for name, digest in before.items():
        if fingerprint(name) != digest and name not in REPAIR_PATHS:
            raise ValueError('Parent forbids repair outside the fixed source allowlist: ' + name)
    for file in (ROOT / 'benchmarks/dolphinbench').glob('*.py'):
        if str(file) not in before and str(file) not in REPAIR_PATHS:
            raise ValueError('Parent forbids unqualified new orchestration code: ' + str(file))


def parent_epoch_guard(contract, condition_path, receipts, output, parent):
    """Independent science, source, evidence, receipt and ledger checks."""
    checked_contract(contract['_contract_path'])
    parent_source_guard(contract)
    output, parent = Path(output), Path(parent)
    baseline_bundle = raw(contract['historical_bundle'])
    old = pinned_json(baseline_bundle['condition'])
    new = raw(condition_path)
    def science(value):
        value = json.loads(json.dumps(value))
        value['inputs'].pop('source_manifest')
        return value
    if science(old) != science(new):
        raise ValueError('Independent parent scientific configuration mismatch')
    manifest_pin = new['inputs']['source_manifest']
    if fingerprint(manifest_pin['path']) != manifest_pin['sha256']:
        raise ValueError('New source manifest bytes differ')
    entries = raw(manifest_pin['path'])
    paths = {p['path'] for p in entries}
    required = {p['path'] for p in pinned_json(baseline_bundle['source_manifest'])}
    if not required <= paths or not {str(p) for p in (ROOT / 'benchmarks/dolphinbench').glob('*.py')} <= paths:
        raise ValueError('Independent parent source coverage incomplete')
    for entry in entries:
        if fingerprint(entry['path']) != entry['sha256']:
            raise ValueError('Independent executing source pin mismatch')
    digest = hashlib.sha256(json.dumps(new, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    for kind in ('profile', 'apps', 'recovery'):
        value = raw(Path(receipts) / (kind + '.json'))
        if (value.get('kind') != kind or value.get('status') != 'passed' or
                value.get('condition_sha256') != digest or not 0 <= time.time() - value.get('created_at', 0) < 86400):
            raise ValueError('Independent parent receipt mismatch')
        for artifact in value['artifacts']:
            if fingerprint(artifact['path']) != artifact['sha256']:
                raise ValueError('Independent parent qualification artifact changed')
    def rows(path):
        connection = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)
        try:
            campaign = connection.execute('SELECT cap,identity FROM campaign WHERE singleton=1').fetchone()
            calls = connection.execute('SELECT * FROM calls ORDER BY call_id').fetchall()
            status = connection.execute('SELECT state,reserved,actual FROM calls').fetchall()
            if campaign[0] != 10_000_000 or any(state not in ('completed', 'unsent') for state, _, _ in status):
                raise ValueError('Independent parent budget has unresolved calls/cap change')
            if sum(actual or 0 for state, _, actual in status if state == 'completed') > 10_000_000:
                raise ValueError('Independent cumulative budget exceeded')
            return campaign, {row[0]: row for row in calls}
        finally:
            connection.close()
    prior_campaign, prior_calls = rows(parent / 'budget.db')
    current_campaign, current_calls = rows(output / 'budget.db')
    if prior_campaign != current_campaign or any(current_calls.get(k) != v for k, v in prior_calls.items()):
        raise ValueError('Independent inherited budget rows modified or removed')
    selected = {i for group in raw(new['inputs']['selection']['path'])['groups'].values() for i in group}
    current = {p.parent.name + '/' + p.stem for p in (output / 'tests').glob('*/*.json') if not p.name.startswith('._')}
    inherited = {p.parent.name + '/' + p.stem for p in (parent / 'tests').glob('*/*.json') if not p.name.startswith('._')}
    if not inherited | {'morgan/129'} <= current <= selected:
        raise ValueError('Independent inherited execution inventory differs')
    for folder in ('tests', 'grades'):
        for path in (parent / folder).glob('*/*.json'):
            if not path.name.startswith('._') and fingerprint(path) != fingerprint(output / path.relative_to(parent)):
                raise ValueError('Independent completed execution/grade bytes changed')
    original_log = Path(contract['parent_output']) / 'apps/morgan/129/calls.jsonl'
    calls = [{k: row[k] for k in ('tool', 'args', 'result')} for row in
        map(json.loads, [line for line in original_log.read_text().splitlines() if line.strip()])]
    if raw(output / 'tests/morgan/129.json')['row'].get('app_calls') != calls:
        raise ValueError('Independent reconstructed task does not retain original backend calls')


def command(argv, *, environment=None):
    subprocess.run(list(map(str, argv)), cwd=ROOT, env=environment, check=True)


def latest_launch(control):
    records = sorted(Path(control).glob('launch-*.json'))
    return raw(records[-1]) if records else None


def archive_condition(condition_path, control):
    from benchmarks.dolphinbench.readiness import pin, identity, read, save, verify_pin
    condition = read(condition_path)
    archive = Path(control) / 'archives' / identity(condition)
    bundle = archive / 'historical-bundle.json'
    if bundle.exists():
        from benchmarks.dolphinbench.pilot_recovery import historical_condition
        historical_condition(bundle)
        return bundle
    archive.mkdir(parents=True, exist_ok=True)
    # Preserve executing bytes now, before a future coding repair can edit them.
    snapshots = []
    for index, item in enumerate(read(condition['inputs']['source_manifest']['path'])):
        source = verify_pin(item)
        target = archive / 'source' / str(index) / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            with source.open('rb') as inp, target.open('xb') as out:
                shutil.copyfileobj(inp, out); out.flush(); os.fsync(out.fileno())
        if fingerprint(target) != item['sha256']:
            raise ValueError('Archived executing source differs')
        snapshots.append({'original': item, 'retained': pin(target)})
    save(bundle, {'condition': pin(condition_path),
        'source_manifest': condition['inputs']['source_manifest'], 'snapshots': snapshots})
    return bundle


def helper():
    spec = importlib.util.spec_from_file_location('dolphin_parent_launch', ROOT / 'specs/048-dolphin-execution-readiness/atsys/run_pilot.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def receipts_fresh(directory):
    try:
        return all(0 <= time.time() - raw(Path(directory) / (kind + '.json'))['created_at'] < 86400
            for kind in ('profile', 'apps', 'recovery'))
    except (OSError, KeyError, ValueError):
        return False


def qualified_receipts(condition, qualification):
    from benchmarks.dolphinbench.readiness import read, issue_qualifications, admit
    receipt_dir = qualification / 'receipts'
    if receipt_dir.exists() and not receipts_fresh(receipt_dir):
        return qualified_receipts(condition, Path(str(qualification) + '-renew-' + str(time.time_ns())))
    configuration = read(condition)
    binding = configuration['bindings']
    qualification.mkdir(parents=True, exist_ok=True)
    apps = qualification / 'apps'
    profile = qualification / 'profile'
    if apps.exists() and not (apps / 'qualification.json').exists():
        apps = qualification / ('apps-' + str(time.time_ns()))
    if profile.exists() and not (profile / 'qualification.json').exists():
        profile = qualification / ('profile-' + str(time.time_ns()))
    if not (apps / 'qualification.json').exists():
        command([sys.executable, '-m', 'benchmarks.dolphinbench.qualify_execution',
            '--upstream', binding['upstream_root'], '--output', apps,
            '--python', binding['app_python']])
    if not (profile / 'qualification.json').exists():
        bootstrap = ('import sys,runpy;sys.path.append(' + repr(binding['controller_site']) + ');'
            'import atmem,atbot;sys.path.insert(0,' + repr(str(ROOT)) + ');'
            'runpy.run_module("benchmarks.dolphinbench.qualify_profile",run_name="__main__")')
        command([binding['product_python'], '-I', '-c', bootstrap,
            '--upstream', binding['upstream_root'], '--app-python', binding['app_python'],
            '--runtime-root', binding['runtime_root'], '--output', profile,
            '--options', configuration['inputs']['options']['path']],
            environment={**os.environ, 'ATMEM_HOME': binding['atmem_home']})
    if receipt_dir.exists() and not all((receipt_dir / (kind + '.json')).exists() for kind in ('profile', 'apps', 'recovery')):
        receipt_dir = qualification / ('receipts-' + str(time.time_ns()))
    if not receipt_dir.exists():
        issue_qualifications(condition, profile, apps, receipt_dir)
    admit(condition, receipt_dir, 'pilot')
    return receipt_dir


def controller(contract_path, *, validate=False):
    contract = checked_contract(contract_path)
    contract['_contract_path'] = str(contract_path)
    control = Path(contract['control_directory'])
    if validate:
        record = latest_launch(control)
        if record is None:
            raise ValueError('No independently qualified launch record')
        from benchmarks.dolphinbench.pilot_recovery import verify_epoch
        if record['contract'] != {'path': str(Path(contract_path).resolve()), 'sha256': fingerprint(contract_path)}:
            raise ValueError('Launch record belongs to another parent contract')
        parent_epoch_guard(contract, record['condition'], record['receipts'], record['output'], record['parent_output'])
        verify_epoch(record['output'], record['condition'])
        command([sys.executable, ROOT / 'specs/048-dolphin-execution-readiness/atsys/validate_pilot.py',
            '--condition', record['condition'], '--receipts', record['receipts'],
            '--output', record['output'], '--handoff', record['handoff']])
        return
    control.mkdir(parents=True, exist_ok=True)
    # Parent runs as an ordinary command worker. Coding workers never receive
    # write authority to private run paths merely because repair is enabled.
    deadline = time.monotonic() + 5400
    while True:
        result = subprocess.run(['atsys', 'task', 'show', contract['implementation_task']],
            capture_output=True, text=True, check=True)
        state = json.loads(result.stdout)['status']
        if state == 'completed':
            break
        if state not in {'queued', 'running', 'validating', 'recovering', 'supervising', 'repairing', 'retrying', 'backoff'} or time.monotonic() > deadline:
            raise ValueError('Implementation has not passed independent acceptance: ' + state)
        time.sleep(10)
    checked_contract(contract_path)
    parent_source_guard(contract)
    # Actual retained task129, not just synthetic fixtures, must reconstruct with
    # zero provider/app calls before creating a new epoch.
    command([sys.executable, contract['independent_validator']])
    from benchmarks.dolphinbench.readiness import freeze, issue_qualifications, admit, qualification_sources, identity, pin, read, save
    from benchmarks.dolphinbench.pilot_recovery import prepare_epoch, verify_epoch
    source = qualification_sources()
    key = identity(source)[:20]
    base = Path(contract['private_base'])
    condition = base / ('condition-pilot20-recovery-' + key + '.json')
    qualification = base / ('pilot20-recovery-' + key)
    receipt_dir = qualification / 'receipts'
    prior = latest_launch(control)
    parent_output = contract['parent_output']
    historical_bundle = contract['historical_bundle']
    if prior is not None and prior['source'] != source:
        # Only already exported/settled work can cross another harness revision.
        # Unknown interaction, judge intent or reservation remains a hard stop.
        from benchmarks.dolphinbench.pilot_recovery import historical_condition, preflight_resume, budget_status
        historical_bundle = prior['historical_bundle']
        old, _ = historical_condition(historical_bundle)
        preflight_resume(prior['output'], old)
        campaign = {**read(old['inputs']['options']['path'])['campaign_identity'], 'cap_usd': 10}
        budget_status(Path(prior['output']) / 'budget.db', campaign)
        parent_output = prior['output']
    if prior is not None and prior['source'] == source:
        condition, receipt_dir = Path(prior['condition']), Path(prior['receipts'])
        output = Path(prior['output'])
        verify_epoch(output, condition)
        if not receipts_fresh(receipt_dir):
            receipt_dir = qualified_receipts(condition, qualification)
            number = len(list(control.glob('launch-*.json'))) + 1
            save(control / ('launch-' + str(number).zfill(5) + '.json'), {**prior, 'receipts': str(receipt_dir)})
        admit(condition, receipt_dir, 'pilot')
    else:
        if not condition.exists():
            freeze(contract['descriptor'], condition)
        receipt_dir = qualified_receipts(condition, qualification)
        checked_contract(contract_path)
        output = Path(str(contract['output']) + '-' + key)
        if output.exists() and not (output / 'epoch-transition.json').exists():
            # A failed, offline-only import is retained. No launch record or
            # workload was created; safely retry the import in another directory.
            output = Path(str(output) + '-import-' + str(time.time_ns()))
        if not output.exists():
            prepare_epoch(historical_bundle, condition, receipt_dir,
                parent_output, output, contract['proofs'])
        verify_epoch(output, condition)
        parent_epoch_guard(contract, condition, receipt_dir, output, parent_output)
        archived = archive_condition(condition, control)
        number = len(list(control.glob('launch-*.json'))) + 1
        save(control / ('launch-' + str(number).zfill(5) + '.json'), {'condition': str(condition), 'receipts': str(receipt_dir),
            'output': str(output), 'handoff': contract['handoff'], 'source': source,
            'contract': pin(contract_path), 'historical_bundle': str(archived), 'parent_output': str(parent_output),
            'pilot_tasks': 20, 'full600_launched': False})
    checked_contract(contract_path)
    current_record = latest_launch(control)
    if current_record['contract'] != {'path': str(Path(contract_path).resolve()), 'sha256': fingerprint(contract_path)}:
        raise ValueError('Launch record belongs to another parent contract')
    parent_epoch_guard(contract, condition, receipt_dir, output, current_record['parent_output'])
    command_line = ['/usr/bin/caffeinate', '-i', '-s', sys.executable,
        str(ROOT / 'scripts/launch_dolphin_readiness.py'), '--condition', str(condition),
        '--receipts', str(receipt_dir), '--output', str(output), '--env-file', contract['env_file_path'],
        '--stage', 'pilot', '--resume-epoch']
    print(json.dumps({'qualified_recovery_epoch': str(output), 'tasks': 20,
        'existing_actions_replayed': False, 'full600_launched': False}), flush=True)
    # Reuse the qualified launcher process-group cancellation/liveness handling.
    launch = helper()
    launch.supervised_command(command_line)
    checked_contract(contract_path)
    verify_epoch(output, condition)
    parent_epoch_guard(contract, condition, receipt_dir, output, current_record['parent_output'])
    launch.handoff(SimpleNamespace(condition=condition, receipts=receipt_dir, output=output,
        handoff=Path(contract['handoff'])))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contract', type=Path, required=True)
    parser.add_argument('--validate', action='store_true')
    args = parser.parse_args()
    controller(args.contract, validate=args.validate)


if __name__ == '__main__':
    main()
