"""Resume CD1's empty export using its exact retained reader implementations.

No inference or private-test execution. Existing partial archives are refused.
"""
import json
import os
from pathlib import Path
import sys
import types

PREFIX = 'external-windows-corrective-development-'
RUN = PREFIX+'archive-v1-20261018'
POST = PREFIX+'postprocessing-v1-20261018'
ROOT = Path('/home/jt/atmem-benchmark-runtime-20261018')


def empty_export(events, output, keys):
    if [e['envelope']['event_type'] for e in events] != ['external.v3_archive_planned']:
        raise ValueError('exact original empty export journal required')
    plan = events[0]['envelope']['payload']
    if (output != ROOT/'corrective-development-archive-v1'
            or keys != ROOT/'corrective-development-archive-keys-v1'
            or str(output) != plan['output'] or str(keys) != plan['internal_key_root']):
        raise ValueError('exact original archive/key destinations required')
    for path in (output, keys):
        if path.is_symlink() or not path.is_dir() or any(path.iterdir()):
            raise ValueError('existing real empty directories required; never overwrite partial evidence')
    return plan


def main():
    from hashlib import sha256
    from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole, EvidenceOperation
    from atmem.core.canonical import canonical_json
    from benchmarks.code_replay.run_evidence import operational_evidence
    from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
    from benchmarks.code_replay.windows_archive import export_snapshot
    scope = EvidenceScope('benchmark', 'local-operator', 'click-20261017')
    principal = EvidencePrincipal('local-benchmark-operator', EvidenceRole.ADMINISTRATOR, scope)
    vault = operational_evidence(EVIDENCE_ROOT, vault_id='confirmation-v1', scope=scope, writing_run=RUN)
    def read(run): return vault.inspect(principal, run)
    def save(kind, payload): return vault.capture(run_id=RUN, kind=kind, principal=principal, payload=payload)
    output, keys = ROOT/'corrective-development-archive-v1', ROOT/'corrective-development-archive-keys-v1'
    plan = empty_export(read(RUN), output, keys)
    if Path('/proc/212838').exists():
        raise ValueError('original waiter PID remains present; do not race or signal it')
    post = read(POST)
    of = lambda rows, kind: [e['envelope']['payload'] for e in rows if e['envelope']['event_type'] == kind]
    post_plan, = of(post, 'external.v3_postprocessing_planned')
    terminal, = of(post, 'external.v3_postprocessing_completed')
    if terminal['comparison_and_public_recovery'] is not True:
        raise ValueError('terminal postprocessing required')
    for name, source in post_plan['postprocess_programs'].items():
        module = types.ModuleType(name); sys.modules[name] = module
        exec(compile(source, '<original-retained-CD1-helper>', 'exec'), module.__dict__)
    archive = types.ModuleType('benchmarks.code_replay.confirmation_v3_archive')
    sys.modules[archive.__name__] = archive
    exec(compile(plan['driver_source'], '<original-retained-CD1-archive>', 'exec'), archive.__dict__)
    lock, = archive.of(read(archive.LOCK), 'external.v3_execution_manifest_frozen')
    runs = archive.required_runs(lock,
        archive.of(read(archive.MODELS), 'external.v3_case_completed'),
        archive.of(read(archive.GRADING), 'external.v3_grade_summary'),
        archive.of(read(archive.PUBLIC), 'external.v3_public_evidence_recovered'), read)
    if sorted(runs) != plan['runs']:
        raise ValueError('original full archive membership must not change')
    # Check original framing/reader imports before recording or writing exports.
    archive.validate_run(sorted(runs)[0], read(sorted(runs)[0]))
    empty_export(read(RUN), output, keys)
    save('external.v3_archive_empty_export_recovery_planned', {
        'driver_source': job['driver_source'], 'original_archive_source': plan['driver_source'],
        'helper_sources': post_plan['postprocess_programs'], 'runs': sorted(runs),
        'reason': 'original process absent; export journal planned, both destinations empty',
        'models_repeated': 0, 'private_grades_repeated': 0, 'pid': os.getpid()})
    members = []
    for run in sorted(runs):
        target = EvidenceScope(scope.tenant_id, scope.subject_id, scope.workspace_id, run)
        principal.authorize(EvidenceOperation.ENCRYPTED_EXPORT, target)
        events = read(run); archive.validate_run(run, events)
        raw = canonical_json(events).encode(); directory = sha256(run.encode()).hexdigest()
        exported = export_snapshot(raw, run_id=run, output=output/directory, key_root=keys/directory)
        vault.for_run(run).service._record_access(principal, 'encrypted_export', target, True)
        members.append({'run_id': run, 'directory': directory, 'raw_bytes': len(raw),
            'raw_sha256': exported['raw_sha256'], 'segments': len(exported['segments'])})
        if len(members) % 25 == 0:
            save('external.v3_archive_export_progress', {'archived_runs': len(members), 'required_runs': len(runs)})
    manifest = {'format': archive.COLLECTION, 'runs': members, 'models_repeated': 0,
        'scope': 'retained benchmark evidence; external pinned runtime images are not copied'}
    export_snapshot(canonical_json(manifest).encode(), run_id=archive.COLLECTION,
        output=output/'collection', key_root=keys/'collection')
    save('external.v3_archive_export_completed', {'runs': len(members), 'output': str(output),
        'independent_recovery': 'pending', 'MEM_copy': 'pending', 'goal_complete': False,
        'empty_export_recovered': True})


if __name__ == '__main__': main()
