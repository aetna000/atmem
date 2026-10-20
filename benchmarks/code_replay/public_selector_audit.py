"""Validate the exact public-selector delta in every archived CD2 template."""
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys

from benchmarks.code_replay import public_selector_profile as profile
from benchmarks.code_replay.query_nomination_preview import evidence, of
from benchmarks.code_replay.query_nomination_trace_audit import reader_program
from benchmarks.code_replay.query_nomination_transfer import RUN as TRANSFER

RUN = 'external-windows-public-selector-template-audit-v1-20261018'


def audit_programs(plans, validator_pair, profile_source):
    """Parse, but never execute, the archived server/worker programs."""
    from hashlib import sha256
    namespace = {'__name__': 'frozen_selector_profile'}
    exec(compile(profile_source, '<frozen-selector-profile>', 'exec'), namespace)
    if len(plans) != 19 or len({p['block']['instance_id'] for p in plans}) != 19:
        raise ValueError('all nineteen distinct original plans required')
    results = []
    for plan in plans:
        programs = {}
        for role, key in (('server', 'server_template'), ('worker', 'public_worker_source')):
            original = plan[key]
            revised = namespace['corrected_program'](original, role=role, validator_pair=validator_pair)
            programs[role] = {'original': original, 'corrected': revised,
                              'original_sha256': sha256(original.encode()).hexdigest(),
                              'corrected_sha256': sha256(revised.encode()).hexdigest(),
                              'validator_only_delta': True}
        results.append({'block': plan['block'], 'programs': programs})
    return {'summary': {'identities': 19, 'programs': 38, 'validator_only_delta': True,
                        'template_programs_executed': 0, 'model_calls': 0,
                        'private_grades_repeated': 0, 'source_vault_opened': False,
                        'runtime_qualified': False}, 'cases': results}


def audit(archive, output, keys):
    from hashlib import sha256
    from benchmarks.code_replay.windows_archive import recover_snapshot
    raw, _ = recover_snapshot(run_id=archive.COLLECTION, output=output/'collection', key_root=keys/'collection')
    members = {r['run_id']: r for r in json.loads(raw)['runs']}
    def read(run):
        member = members[run]; directory = sha256(run.encode()).hexdigest()
        if member['directory'] != directory:
            raise ValueError('authenticated archive member path required')
        raw, proof = recover_snapshot(run_id=run, output=output/directory, key_root=keys/directory)
        if proof['raw_sha256'] != member['raw_sha256'] or len(raw) != member['raw_bytes']:
            raise ValueError('complete authenticated archive member required')
        return json.loads(raw)
    lock, = archive.of(read(archive.LOCK), 'external.v3_execution_manifest_frozen')
    if len(lock['staged_blocks']) != 19:
        raise ValueError('complete original CD2 stage cohort required')
    plans = []
    for stage in lock['staged_blocks']:
        plan, = archive.of(read(stage['task_run']), 'external.confirmation_v3_stage_planned')
        if plan['block'] != stage['block'] or plan['model_calls'] != 0:
            raise ValueError('original stage identity differs')
        plans.append(plan)
    return audit_programs(plans, VALIDATOR_PAIR, PROFILE_SOURCE)


def main():
    os.environ['ATMEM_BENCHMARK_PER_RUN_VAULTS'] = '1'
    vault, principal = evidence(RUN)
    if vault.inspect(principal, RUN):
        raise ValueError('template audit already attempted; inspect retained evidence')
    rows = vault.inspect(principal, TRANSFER)
    terminal, = of(rows, 'external.query_nomination_MEM_recovery_completed')
    if (terminal['proof']['source_vault_opened'] is not False
            or terminal['proof']['request_audit']['verified_original_requests'] != 38):
        raise ValueError('complete independent recovery required')
    plan, = of(rows, 'external.query_nomination_MEM_transfer_planned')
    profile_source = inspect.getsource(profile)
    pair = profile.validators()
    source = ('import json\nPROFILE_SOURCE='+repr(profile_source)+'\nVALIDATOR_PAIR='+repr(pair)+'\n'
              +inspect.getsource(audit_programs)+'\n'+inspect.getsource(audit))
    program = reader_program(plan['standalone_recovery_program'], source)
    def save(kind, payload):
        return vault.capture(run_id=RUN, kind=kind, principal=principal, payload=payload)
    save('external.public_selector_template_audit_planned', {
        'driver_source': Path(__file__).read_text(), 'reader_program': program,
        'profile_source': profile_source, 'validator_pair': pair, 'model_calls': 0,
        'selection': 'every retained CD2 server and sandbox-worker template',
        'source_vault_access': False})
    loader = "import json,sys;exec(compile(json.load(sys.stdin)['program'],'<archive-only-selector-audit>','exec'))"
    result = subprocess.run([sys.executable, '-c', loader], input=json.dumps({'program': program}).encode(),
                            capture_output=True, timeout=3600)
    if result.returncode:
        save('external.public_selector_template_audit_failed', {
            'exit_code': result.returncode, 'stderr': result.stderr.decode(errors='replace')})
        raise RuntimeError('template audit failed; preserve evidence and inspect')
    value = json.loads(result.stdout)
    save('external.public_selector_template_audit_completed', value)
    print(json.dumps(value['summary']), flush=True)


if __name__ == '__main__':
    main()
