"""Fail-closed local-operator qualification, never independent attestation."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import time

from .execution_profile import PROFILE, ROUTED_PROFILE, ROUTED_PROFILES, CHECKPOINT_PROFILE, PROFILES

SCHEMA = 'dolphin-execution-condition-v1'
PILOT_COUNT = 20
PILOT_SELECTION = Path(__file__).parents[2] / 'docs/benchmarks/evidence/dolphin-execution-audit-20261025/pilot-selection-20-20261026.json'
MAX_AGE = 24 * 3600
CHECKS = {'profile': {'mcp_only', 'eager_tools', 'skills_disabled'},
          'apps': {'result_state_log_agree'},
          'recovery': {'uncertain_replay_refused', 'evidence_preserved'},
          'pilot': {'all_20_graded', 'no_unsupported_routes', 'no_unresolved_costs', 'regressions_reported'}}
ROLES = {'wheel', 'upstream_manifest', 'source_manifest', 'selection', 'options',
         'memory:morgan', 'memory:alex', 'memory:riley'}
MEMORY_OPTIONS = {'context_engine_variant': 'source-coherent-v1', 'read_only_discovery': True,
    'application_workflow': True, 'strict_application_contracts': True,
    'source_time_frames': False, 'source_bundles': False, 'initial_state_presentation': 'annotated-source'}
ROUTED_CHECKS = {'ordinary_inventory', 'plugin_loaded', 'checkpoint_disabled',
                 'native_write_state_log_agree', 'local_detour_refused', 'user_boundary_unchanged', 'route_note_in_system_prompt'}
CHECKPOINT_CHECKS = (ROUTED_CHECKS - {'checkpoint_disabled'}) | {'checkpoint_held_once'}
ROUTED_SOURCES = ('atmem/action_guard.py', 'atmem/adapters/hermes/action_guard_plugin.py',
                  'specs/048-dolphin-execution-readiness/atsys/run_routed.py',
                  '.atsys/tasks/dolphin-routed-fixed20.json',
                  '.atsys/tasks/dolphin-routed-fixed20-v2.json', '.atsys/tasks/dolphin-routed-fixed20-v3.json')


def checks_for(condition, kind):
    if kind == 'profile' and condition['profile'] == CHECKPOINT_PROFILE:
        return CHECKPOINT_CHECKS
    return ROUTED_CHECKS if kind == 'profile' and condition['profile'] in ROUTED_PROFILES else CHECKS[kind]


_VERIFIED_FILES = {}


def sha(path):
    path = Path(path)
    stat = path.stat()
    fingerprint = (str(path.resolve()), stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    if fingerprint not in _VERIFIED_FILES:
        _VERIFIED_FILES[fingerprint] = hashlib.sha256(path.read_bytes()).hexdigest()
    return _VERIFIED_FILES[fingerprint]


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def read(path):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError('Duplicate JSON key')
            value[key] = item
        return value
    return json.loads(Path(path).read_text(), object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as output:
        json.dump(value, output, sort_keys=True, allow_nan=False, indent=2)
        output.write('\n')
        output.flush()
        os.fsync(output.fileno())
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def pin(path):
    path = Path(path).resolve(strict=True)
    if not path.is_file():
        raise ValueError('Pinned input must be a file')
    return {'path': str(path), 'sha256': sha(path)}


def verify_pin(entry):
    if not isinstance(entry, dict) or set(entry) != {'path', 'sha256'}:
        raise ValueError('Invalid pinned artifact')
    path = Path(entry['path'])
    if not path.is_absolute() or sha(path) != entry['sha256']:
        raise ValueError('Pinned artifact changed: ' + str(path))
    return path


def load_condition(path):
    value = read(path)
    if value.get('schema') != SCHEMA or value.get('profile') not in PROFILES:
        raise ValueError('Frozen execution condition/profile required')
    routes_path = Path(__file__).parents[2] / 'specs/048-dolphin-execution-readiness/routes.json'
    if value.get('routes') != read(routes_path):
        raise ValueError('Local/subscription/API role policy differs from the frozen baseline')
    inputs = value.get('inputs', {})
    if set(inputs) != ROLES:
        raise ValueError('Pin wheel, source, upstream, selection and all three memory checkpoints')
    for entry in inputs.values():
        verify_pin(entry)
    source = read(inputs['source_manifest']['path'])
    if not isinstance(source, list) or not source:
        raise ValueError('Nonempty source manifest required')
    for entry in source:
        verify_pin(entry)
    # All executing orchestration modules must be covered, not only a declared SHA.
    covered = {Path(e['path']).resolve() for e in source}
    required = set(Path(__file__).parent.glob('*.py'))
    required |= {Path(__file__).parents[2] / 'research/retrieval_2310/dolphin_stage.py'}
    required.add(routes_path)
    required |= {Path(__file__).parents[2] / 'docs/benchmarks/evidence/dolphin-execution-audit-20261025' / n
                 for n in ('task-ledger.jsonl', 'pilot-selection.json', 'pilot-selection-20-20261026.json')}
    required |= {Path(__file__).parents[2] / p for p in ('scripts/openrouter_azure_sol.py',
        'scripts/launch_dolphin_readiness.py', 'specs/048-dolphin-execution-readiness/runbook.md',
        'specs/048-dolphin-execution-readiness/atsys/run_pilot.py',
        'specs/048-dolphin-execution-readiness/atsys/validate_pilot.py',
        '.atsys/tasks/dolphin-readiness-pilot-20.json')}
    if not {p.resolve() for p in required} <= covered:
        raise ValueError('Source manifest omits executing orchestration')
    if value['profile'] in ROUTED_PROFILES:
        if not {Path(__file__).parents[2] / p for p in ROUTED_SOURCES} <= covered:
            raise ValueError('Routed plugin/worker source not pinned')
        if read(inputs['options']['path']).get('execution_profile') != value['profile']:
            raise ValueError('Routed options/profile mismatch')
    selection = read(inputs['selection']['path'])
    groups = selection.get('groups', {})
    ids = [item for group in groups.values() for item in group]
    if len(ids) != PILOT_COUNT or len(set(ids)) != PILOT_COUNT or selection.get('tasks') != PILOT_COUNT or not selection.get('post_hoc_diagnostic_not_holdout'):
        raise ValueError('Exactly 20 frozen diagnostic IDs required')
    canonical = PILOT_SELECTION
    if selection != read(canonical):
        raise ValueError('Pilot selection differs from the fixed diagnostic')
    budget = value.get('budget', {})
    caps = budget.get('caps_usd', {})
    if (set(caps) != {'pilot', 'full'} or any(type(n) not in (int, float) or not math.isfinite(n) or n <= 0 for n in caps.values())
            or budget.get('uncertain_charges') != 'reserve_until_reconciled'):
        raise ValueError('Finite positive budget and uncertain-charge accounting required')
    settings = value.get('settings', {})
    if settings.get('reader') != {'model': 'openai/gpt-5.6-luna', 'reasoning': 'high',
                                'max_turns': 60, 'context_length': 1050000}:
        raise ValueError('Original reader settings must remain fixed')
    if settings.get('judge') != {'model': 'gpt-5.6-sol', 'reasoning': 'medium', 'output_cap': 8000}:
        raise ValueError('Original judge settings must remain fixed')
    if value.get('fixture_disposition') != 'retain_original_two_unavailable_cases_in_denominator':
        raise ValueError('Explicit original fixture disposition required; no silent repairs')
    if value.get('memory_options') != MEMORY_OPTIONS:
        raise ValueError('Original local-only memory configuration must remain fixed')
    for name in ('upstream_root', 'runtime_root', 'memory_root', 'atmem_home',
                 'subscription_python', 'product_python', 'app_python', 'controller_site'):
        if not Path(value.get('bindings', {}).get(name, '')).is_absolute():
            raise ValueError('Absolute execution binding required: ' + name)
    for name in ('subscription_python', 'product_python', 'app_python'):
        binary = Path(value['bindings'][name]).resolve()
        if not binary.is_file() or binary not in covered:
            raise ValueError('Interpreter missing or not source-pinned: ' + name)
    upstream = Path(value['bindings']['upstream_root']) / 'manifest.json'
    if upstream.resolve() != Path(inputs['upstream_manifest']['path']).resolve():
        raise ValueError('Upstream binding differs from pinned manifest')
    base = upstream.parent.resolve()
    for relative, expected in read(upstream)['files'].items():
        path = (base / relative).resolve()
        if not path.is_relative_to(base) or sha(path) != expected:
            raise ValueError('Upstream payload changed: ' + relative)
    return value


def receipt(condition_path, kind, checks, artifacts, output):
    condition = load_condition(condition_path)
    if kind not in CHECKS or set(checks) != checks_for(condition, kind) or not all(v is True for v in checks.values()):
        raise ValueError('Incomplete qualification checks')
    if not artifacts:
        raise ValueError('Raw qualification artifacts required')
    result = {'schema': 'dolphin-readiness-receipt-v1', 'kind': kind,
              'condition_sha256': identity(condition), 'created_at': time.time(),
              'status': 'passed', 'checks': checks, 'artifacts': [pin(p) for p in artifacts]}
    save(output, result)
    return result


def qualification_sources():
    root = Path(__file__).parents[2]
    paths = [*Path(__file__).parent.glob('*.py'),
             root / 'specs/048-dolphin-execution-readiness/atsys/run_pilot.py',
             root / 'specs/048-dolphin-execution-readiness/atsys/validate_pilot.py',
             root / '.atsys/tasks/dolphin-readiness-pilot-20.json']
    paths.extend(root / p for p in ROUTED_SOURCES)
    return [pin(p) for p in sorted(paths)]


def issue_qualifications(condition_path, profile_directory, apps_directory, receipts):
    """Issue receipts only from retained native/bridge qualification evidence."""
    from .execution_profile import validate
    condition = load_condition(condition_path)
    pinned_source = read(condition['inputs']['source_manifest']['path'])
    profile_directory, apps_directory = Path(profile_directory), Path(apps_directory)
    profile, apps = read(profile_directory / 'qualification.json'), read(apps_directory / 'qualification.json')
    for report in (profile, apps):
        if report.get('model_calls') != 0 or report.get('upstream_manifest') != condition['inputs']['upstream_manifest']:
            raise ValueError('Qualification upstream/model route mismatch')
        if report.get('app_python') != pin(Path(condition['bindings']['app_python']).resolve()):
            raise ValueError('Qualification used another app runtime')
        if report.get('source') != qualification_sources() or any(p not in pinned_source for p in report['source']):
            raise ValueError('Qualification source differs from frozen executing source')
    if (profile.get('options') != condition['inputs']['options']
            or profile.get('same_adapter_profile_builder') is not True
            or profile.get('provider_forwarding_exists') is not False
            or any(profile.get(k) is not True for k in checks_for(condition, 'profile'))):
        raise ValueError('Actual frozen-profile qualification missing')
    names = validate(condition['profile'], read(profile_directory / 'model-request.json'))
    if condition['profile'] in ROUTED_PROFILES:
        from .qualify_routed import verify_evidence
        if (profile.get('profile') != condition['profile']
                or profile.get('runtime_root') != condition['bindings']['runtime_root']
                or profile.get('native_python') != pin(Path(condition['bindings']['subscription_python']).resolve())):
            raise ValueError('Routed native runtime differs from frozen condition')
        verify_evidence(profile_directory)
    if names != profile['tools'] or not names:
        raise ValueError('Captured model-visible profile differs')
    if (apps.get('synthetic_only') is not True or apps.get('same_macos_sandbox_and_upstream_bridge') is not True
            or any(apps.get(k) is not True for k in CHECKS['apps'] | CHECKS['recovery'])
            or [(r['name'], r['returncode'], r['calls']) for r in apps['outcomes']] != [('apps', 0, 3), ('crash', 73, 1)]):
        raise ValueError('Incomplete real bridge/crash qualification')
    profile_artifacts = (sorted(p for p in profile_directory.iterdir() if p.is_file())
                         if condition['profile'] in ROUTED_PROFILES
                         else list(profile_directory.glob('*.json')))
    raw = []
    for outcome in apps['outcomes']:
        raw.extend(verify_pin(a) for a in outcome['artifacts'])
    for kind, artifacts in [('profile', profile_artifacts),
                            ('apps', [apps_directory / 'qualification.json', *raw]),
                            ('recovery', [apps_directory / 'qualification.json', *raw])]:
        receipt(condition_path, kind, {k: True for k in checks_for(condition, kind)}, artifacts,
                Path(receipts) / (kind + '.json'))


def admit(condition_path, receipts, stage, *, now=None):
    if stage not in {'pilot', 'full'}:
        raise ValueError('Unknown readiness stage')
    if not condition_path or not receipts:
        raise ValueError('Frozen execution condition and readiness receipts required before scored dispatch')
    condition = load_condition(condition_path)
    now = time.time() if now is None else now
    for kind in ('profile', 'apps', 'recovery') + (('pilot',) if stage == 'full' else ()):
        item = read(Path(receipts) / (kind + '.json'))
        stamp = item.get('created_at')
        if (item.get('schema') != 'dolphin-readiness-receipt-v1' or item.get('kind') != kind
                or item.get('status') != 'passed' or item.get('condition_sha256') != identity(condition)
                or type(stamp) not in (int, float) or not math.isfinite(stamp)
                or stamp > now + 5 or now - stamp > MAX_AGE
                or set(item.get('checks', {})) != checks_for(condition, kind)
                or any(v is not True for v in item['checks'].values()) or not item.get('artifacts')):
            raise ValueError('Missing, stale, failed or mismatched readiness: ' + kind)
        for artifact in item['artifacts']:
            verify_pin(artifact)
        if kind == 'pilot':
            report = read(item['artifacts'][0]['path'])
            wanted = {i for group in read(condition['inputs']['selection']['path'])['groups'].values() for i in group}
            rows = report.get('rows', [])
            if (report.get('schema') != 'dolphin-fixed-pilot-report-v1' or report.get('tasks') != PILOT_COUNT
                    or report.get('condition_sha256') != identity(condition) or len(rows) != PILOT_COUNT
                    or {r.get('id') for r in rows} != wanted or report.get('regressions') != []
                    or any(type(r.get('passed')) is not bool for r in rows)
                    or report.get('accounting', {}).get('uncertain_usd') != 0
                    or report.get('accounting', {}).get('complete') is not True
                    or type(report.get('accounting', {}).get('actual_usd')) not in (int, float)
                    or not 0 <= report['accounting']['actual_usd'] <= condition['budget']['caps_usd']['pilot']):
                raise ValueError('Partial or invalid pilot report; full launch blocked')
    return condition


def freeze(descriptor, output):
    """Pin explicit inputs; never fill in missing checkpoints or credentials."""
    descriptor = read(descriptor)
    if Path(output).exists():
        raise FileExistsError('Frozen condition already exists')
    source_path = Path(output).with_name(Path(output).stem + '-source.json')
    root = Path(__file__).parents[2]
    source = [*Path(__file__).parent.glob('*.py'), * (root / 'research/retrieval_2310').glob('*.py'),
              root / 'specs/048-dolphin-execution-readiness/routes.json']
    source.extend(root / 'docs/benchmarks/evidence/dolphin-execution-audit-20261025' / n
                  for n in ('task-ledger.jsonl', 'pilot-selection.json', 'pilot-selection-20-20261026.json'))
    source.extend(Path(descriptor['bindings']['controller_site']).glob('*.dist-info/RECORD'))
    source.extend(root / p for p in ('scripts/openrouter_azure_sol.py', 'scripts/launch_dolphin_readiness.py',
                                     'specs/048-dolphin-execution-readiness/runbook.md',
                                     'specs/048-dolphin-execution-readiness/atsys/run_pilot.py',
                                     'specs/048-dolphin-execution-readiness/atsys/validate_pilot.py',
                                     '.atsys/tasks/dolphin-readiness-pilot-20.json'))
    source.extend(root / p for p in ROUTED_SOURCES)
    hermes = Path.home() / '.hermes/hermes-agent'
    source.extend(hermes / name for name in ['run_agent.py', 'model_tools.py', 'toolsets.py',
        'agent/prompt_builder.py', 'agent/skill_utils.py', 'tools/tool_search.py',
        'tools/tool_search_catalog.py', 'tools/mcp_tool_discovery.py'])
    source.extend(Path(descriptor['bindings'][n]).resolve() for n in ('subscription_python', 'product_python', 'app_python'))
    upstream = Path(descriptor['bindings']['upstream_root'])
    source.extend(p for folder in ('harness', 'graders', 'mock_mcp') for p in (upstream / folder).rglob('*.py') if not p.name.startswith('._'))
    options = read(descriptor['inputs']['options'])
    indexes = Path(options['context_index_directory'])
    source.extend(p for p in indexes.rglob('*') if p.is_file() and not p.name.endswith(('-wal', '-shm', '.lock')))
    for name in ('product_python', 'app_python'):
        environment = Path(descriptor['bindings'][name]).absolute().parent.parent
        source.extend(environment.glob('lib/python*/site-packages/*.dist-info/RECORD'))
    records = [pin(p) for p in sorted(set(source))]
    # Validate in a private temporary file before publishing the frozen condition.
    import tempfile
    with tempfile.TemporaryDirectory() as temporary:
        temporary_source = Path(temporary) / 'source.json'
        save(temporary_source, records)
        inputs = {**descriptor['inputs'], 'source_manifest': str(temporary_source)}
        value = {**descriptor, 'schema': SCHEMA, 'profile': descriptor.get('profile', PROFILE),
                 'inputs': {k: pin(p) for k, p in inputs.items()}}
        test = Path(temporary) / 'condition.json'
        save(test, value)
        load_condition(test)
    if source_path.exists():
        if read(source_path) != records:
            raise ValueError('Prior source manifest differs; select a new freeze filename')
    else:
        save(source_path, records)
    value['inputs']['source_manifest'] = pin(source_path)
    save(output, value)
    return value


def require_options(options, *, request=None):
    """Shared adapter gate: old entry points cannot bypass a missing receipt."""
    stage = options.get('readiness_stage', 'full')
    launched = options.get('readiness_admission')
    if launched:
        lease = read(launched)
        if (lease.get('schema') != 'dolphin-launch-admission-v1' or lease.get('pid') != os.getpid()
                or lease.get('stage') != stage or not Path(launched).resolve().is_relative_to(Path(lease['run_root']).resolve())):
            raise ValueError('Admission belongs to a different process/run')
        condition = admit(options['readiness_condition'], options['readiness_receipts'], stage, now=lease['created_at'])
        if request is not None and Path(request.work_dir).resolve() != Path(lease['run_root']).resolve():
            raise ValueError('Interaction belongs to a different admitted output directory')
        if identity(condition) != lease['condition_sha256']:
            raise ValueError('Admitted condition changed')
        for artifact in lease['receipt_files']:
            verify_pin(artifact)
        epoch_path = Path(lease['run_root']) / 'epoch-transition.json'
        if epoch_path.exists() or 'recovery_transition' in lease:
            if lease.get('recovery_transition') != pin(epoch_path):
                raise ValueError('Recovery admission lacks the immutable epoch transition')
            from .pilot_recovery import verify_epoch
            # Startup/between-task checks remain strict. During this admitted
            # process, simultaneous primary/auxiliary reservations are live;
            # retain their full bounds and reject any pre-launch uncertainty.
            verify_epoch(lease['run_root'], options['readiness_condition'],
                         inflight_since=lease['created_at'])
    else:
        condition = admit(options.get('readiness_condition', ''), options.get('readiness_receipts', ''), stage)
    campaign = options.get('campaign_identity', {})
    expected = read(condition['inputs']['options']['path'])
    dynamic = {'readiness_condition', 'readiness_receipts', 'readiness_stage',
               'execution_profile', 'env_file', 'subscription_endpoint', 'readiness_admission'}
    expected = {**expected, 'campaign_identity': {**expected.get('campaign_identity', {}),
                'cap_usd': condition['budget']['caps_usd'][stage]}}
    if {k: v for k, v in options.items() if k not in dynamic} != {k: v for k, v in expected.items() if k not in dynamic}:
        raise ValueError('Actual adapter options differ from pinned options')
    if campaign.get('cap_usd') != condition['budget']['caps_usd'][stage]:
        raise ValueError('Actual budget differs from condition')
    agent = campaign.get('agent', {})
    if {k: agent.get(k) for k in condition['settings']['reader']} != condition['settings']['reader']:
        raise ValueError('Actual reader differs from frozen condition')
    if options.get('execution_profile') != condition['profile']:
        raise ValueError('Actual profile differs from frozen condition')
    if options.get('memory_engine') != 'context-v3':
        raise ValueError('Frozen V3 memory required')
    if options.get('memory_options', {}) != condition.get('memory_options', {}):
        raise ValueError('Memory settings differ from frozen condition')
    for key, value in MEMORY_OPTIONS.items():
        if options.get(key) != value:
            raise ValueError('Missing or changed effective memory option: ' + key)
    if (Path(options.get('app_python', '')).resolve() != Path(condition['bindings']['app_python']).resolve()
            or Path(options.get('upstream_root', '')).resolve() != Path(condition['bindings']['upstream_root']).resolve()
            or options.get('memory_delivery') != 'native-product-api'
            or options.get('ingestion_mode') != 'source-episode'):
        raise ValueError('Actual execution binding differs from the unchanged baseline')
    for key in ('context_engine_variant', 'read_only_discovery', 'application_workflow',
                'strict_application_contracts', 'state_assessor', 'initial_state_assessor',
                'source_time_frames', 'source_bundles', 'initial_state_presentation'):
        if key in options and options[key] != condition.get('memory_options', {}).get(key):
            raise ValueError('Unfrozen memory/host option: ' + key)
    if options.get('state_assessor') is not None or options.get('initial_state_assessor') is not None:
        raise ValueError('Remote state assessment is disabled for the unchanged-memory run')
    if Path(options.get('baseline_memory_root', '')).resolve() != Path(condition['bindings']['memory_root']).resolve():
        raise ValueError('Actual memory root differs from condition')
    if Path(options.get('runtime_root', '')).resolve() != Path(condition['bindings']['runtime_root']).resolve():
        raise ValueError('Actual runtime differs from condition')
    if os.environ.get('ATMEM_HOME') != condition['bindings']['atmem_home']:
        raise ValueError('Actual AtMem Home differs from condition')
    # A mutable Ollama tag must not silently change during a long campaign.
    import urllib.request
    embedding = condition['routes']['embedding']
    with urllib.request.urlopen(embedding['endpoint'] + '/api/tags', timeout=5) as response:
        models = json.load(response).get('models', [])
    found = [m for m in models if m.get('name') == embedding['model']]
    if len(found) != 1 or 'sha256:' + found[0].get('digest', '').removeprefix('sha256:') != embedding['digest']:
        raise ValueError('Actual local embedding model differs from frozen digest')
    if request is not None and options.get('readiness_stage') == 'pilot':
        selection = read(condition['inputs']['selection']['path'])
        allowed = {key for group in selection['groups'].values() for key in group}
        if request.persona + '/' + request.interaction_id not in allowed:
            raise ValueError('Task outside the fixed 20-case pilot')
    return condition


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--condition', type=Path, required=True)
    parser.add_argument('--receipts', type=Path, required=True)
    parser.add_argument('--stage', choices=('pilot', 'full'), required=True)
    args = parser.parse_args()
    result = admit(args.condition, args.receipts, args.stage)
    print(json.dumps({'admitted': True, 'stage': args.stage, 'condition_sha256': identity(result)}))


if __name__ == '__main__':
    main()
