"""Full per-run protected archives with standalone recovery, not hash-only export."""
from hashlib import sha256
import json
from pathlib import Path

RUN = 'external-windows-confirmation-v3-archive-v1-20261018'
COLLECTION = 'atmem-code-confirmation-v3-protected-collection-v1'
LOCK = 'external-windows-confirmation-v3-execution-lock-v1-20261018'
MODELS = 'external-windows-confirmation-v3-models-v1-20261018'
GRADING = 'external-windows-confirmation-v3-grading-v1-20261018'
PUBLIC = 'external-windows-confirmation-v3-public-recovery-v1-20261018'
REPORT = 'external-windows-confirmation-v3-comparison-v1-20261018'
FINISH = 'external-windows-confirmation-v3-postprocessing-v1-20261018'


def of(events, kind):
    return [e['envelope']['payload'] for e in events if e['envelope']['event_type'] == kind]


def core_runs(lock, cases, grades, public):
    expected = {(b['slot'], a): (b['instance_id'], b['repeat'])
                for b in lock['staging_manifest']['blocks'] for a in b['order']}
    runs = {LOCK, MODELS, GRADING, PUBLIC, REPORT, FINISH,
            'external-windows-confirmation-v3-staging-v1-20261018',
            'external-windows-product-build-source-storage-v1-20261018',
            'external-windows-compatibility-build-inspection-v1-20261018',
            'external-windows-source-storage-qualification-v1-20261018',
            'external-windows-confirmation-v3-process-scope-v1-20261018'}
    if len(expected) != 76:
        raise ValueError('exact frozen cohort required')
    for rows in (cases, grades, public):
        if (len(rows) != 76 or len({(r['slot'], r['arm']) for r in rows}) != 76
                or any(expected.get((r['slot'], r['arm'])) != (r['instance_id'], r['repeat']) for r in rows)):
            raise ValueError('all model, grade and recovered-public cells required')
        runs.update(r['task_run'] for r in rows)
    runs.update(r['task_run'] for r in lock['staged_blocks'])
    runs.update(r['task_run'] for r in lock['grade_plans'].values())
    runs.update(r['export_run'] for r in lock['staging_manifest']['source_descriptors'].values())
    return runs


def required_runs(lock, cases, grades, public, read):
    runs = core_runs(lock, cases, grades, public)
    for root, kind in [('external-windows-confirmation-v3-mcp-readiness-v1-20261018', 'external.v3_mcp_case_summary'),
                       ('external-windows-confirmation-v3-sandbox-v1-20261018', 'external.v3_sandbox_case_summary'),
                       ('external-windows-confirmation-v3-sandbox-v2-20261018', 'external.v3_sandbox_case_summary')]:
        rows = of(read(root), kind)
        if len(rows) != 76 or len({(r['slot'], r['arm']) for r in rows}) != 76:
            raise ValueError('all original readiness outcomes required, including failed probes')
        runs.add(root); runs.update(r['task_run'] for r in rows)
    qualification = 'external-windows-source-storage-qualification-v1-20261018'
    rows = of(read(qualification), 'external.compatibility_case_result')
    if len(rows) != 5: raise ValueError('all five installed compatibility controls required')
    runs.update(r['task_run'] for r in rows)
    prior = lock['staging_manifest']['prior_manifest_run']
    runs.add(prior)
    runs.update(prior + '-block-' + str(b['slot']) for b in lock['staging_manifest']['blocks'])
    return runs


def validate_run(run, events):
    """Verify available full streams after archive-only recovery."""
    from benchmarks.code_replay.windows_metrics import recover_stream
    from benchmarks.code_replay.confirmation_v3_grade import recover_candidate
    from benchmarks.code_replay.confirmation_v3_report import private_controller
    from benchmarks.code_replay.windows_retain import decode_recovery
    if not events or any(e['envelope']['run_id'] != run for e in events):
        raise ValueError('archive run identity or full events missing')
    by_id = {e['object_id']: e for e in events}
    counts = {'events': len(events), 'full_streams': 0, 'candidates': 0, 'private_grades': 0, 'public_vaults': 0}
    for model in of(events, 'external.v3_model_result'):
        raw = {k: recover_stream(by_id, v) for k, v in model['raw_response_transport'].items()}
        original = json.loads(raw['stdout'])
        if model['usage_receipts'] != [e for e in original['events'] if e.get('type') == 'turn.completed']:
            raise ValueError('archived model receipt differs from raw exchange')
        counts['full_streams'] += len(raw)
    for candidate in of(events, 'external.v3_case_completed'):
        # The root run contains references; full candidate chunks live in the case run.
        if candidate['task_run'] == run:
            recover_candidate(events, candidate); counts['candidates'] += 1
    for grade in of(events, 'external.v3_private_grade'):
        private_controller(events, grade); counts['private_grades'] += 1
    for public in of(events, 'external.v3_public_evidence_recovered'):
        if public['task_run'] == run:
            raw = {k: recover_stream(by_id, v) for k, v in public['streams'].items()}
            transport, recovered = decode_recovery(raw['stdout'])
            if transport['sha256'] != public['recovered_sha256'] or recovered['public_run_id'] != public['public_run_id']:
                raise ValueError('archived public-vault identity differs')
            counts['public_vaults'] += 1; counts['full_streams'] += len(raw)
    return counts


def recover_collection(output, key_root):
    """Only archive files and internal keys are consulted; no live vault access."""
    from benchmarks.code_replay.windows_archive import recover_snapshot
    from benchmarks.code_replay.windows_confirmation_exports import recover_export
    raw, _ = recover_snapshot(run_id=COLLECTION, output=output/'collection', key_root=key_root/'collection')
    manifest = json.loads(raw)
    if manifest['format'] != COLLECTION or len({r['run_id'] for r in manifest['runs']}) != len(manifest['runs']):
        raise ValueError('unique authenticated archive collection required')
    indexed = {r['run_id']: r for r in manifest['runs']}
    def read(run):
        row = indexed[run]
        if row['directory'] != sha256(run.encode()).hexdigest():
            raise ValueError('bounded exact per-run archive location required')
        raw, observed = recover_snapshot(run_id=run, output=output/row['directory'], key_root=key_root/row['directory'])
        if observed['raw_sha256'] != row['raw_sha256'] or observed['raw_bytes'] != row['raw_bytes']:
            raise ValueError('authenticated collection member differs')
        return json.loads(raw)
    lock, = of(read(LOCK), 'external.v3_execution_manifest_frozen')
    cases = of(read(MODELS), 'external.v3_case_completed')
    grades = of(read(GRADING), 'external.v3_grade_summary')
    public = of(read(PUBLIC), 'external.v3_public_evidence_recovered')
    if not required_runs(lock, cases, grades, public, read) <= indexed.keys():
        raise ValueError('required cohort archive member missing')
    totals = {'runs': len(indexed), 'events': 0, 'full_streams': 0, 'candidates': 0, 'private_grades': 0, 'public_vaults': 0}
    for run in indexed:
        proof = validate_run(run, read(run))
        for key, value in proof.items(): totals[key] += value
    for descriptor in lock['staging_manifest']['source_descriptors'].values():
        recover_export(read(descriptor['export_run']), descriptor)
    if (totals['candidates'], totals['private_grades'], totals['public_vaults']) != (76, 76, 76):
        raise ValueError('full cohort streams and artifacts not independently recovered')
    return {**totals, 'source_vault_opened': False, 'models_repeated': 0, 'collection_sha256': sha256(raw).hexdigest()}


def main():
    from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole, EvidenceOperation
    from atmem.core.canonical import canonical_json
    from benchmarks.code_replay.run_evidence import operational_evidence
    from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
    from benchmarks.code_replay.windows_archive import export_snapshot
    scope = EvidenceScope('benchmark', 'local-operator', 'click-20261017')
    principal = EvidencePrincipal('local-benchmark-operator', EvidenceRole.ADMINISTRATOR, scope)
    vault = operational_evidence(EVIDENCE_ROOT, vault_id='confirmation-v1', scope=scope, writing_run=RUN)
    if vault.inspect(principal, RUN): raise ValueError('archive already attempted; inspect retained progress')
    def events(run): return vault.inspect(principal, run)
    def save(kind, payload): return vault.capture(run_id=RUN, kind=kind, principal=principal, payload=payload)
    lock, = of(events(LOCK), 'external.v3_execution_manifest_frozen')
    end, = of(events(FINISH), 'external.v3_postprocessing_completed')
    if end['comparison_and_public_recovery'] is not True: raise ValueError('terminal postprocessing required')
    runs = required_runs(lock, of(events(MODELS), 'external.v3_case_completed'),
                         of(events(GRADING), 'external.v3_grade_summary'),
                         of(events(PUBLIC), 'external.v3_public_evidence_recovered'), events)
    output, keys = Path(job['output']), Path(job['key_root'])
    if output.exists() or keys.exists(): raise ValueError('fresh archive and internal-key directories required')
    if (not str(output).startswith('/home/jt/atmem-benchmark-runtime-20261018/')
            or not str(keys).startswith('/home/jt/atmem-benchmark-runtime-20261018/')):
        raise ValueError('exact benchmark-owned remote archive destinations required')
    output.mkdir(mode=0o700); keys.mkdir(mode=0o700)
    save('external.v3_archive_planned', {'driver_source': job['driver_source'], 'runs': sorted(runs),
         'output': str(output), 'internal_key_root': str(keys), 'models_repeated': 0,
         'scope': 'full scored cohort, source exports, frozen graders, staging, readiness and build records'})
    members = []
    for run in sorted(runs):
        target = EvidenceScope(scope.tenant_id, scope.subject_id, scope.workspace_id, run)
        principal.authorize(EvidenceOperation.ENCRYPTED_EXPORT, target)
        es = events(run); validate_run(run, es)
        raw = canonical_json(es).encode(); directory = sha256(run.encode()).hexdigest()
        exported = export_snapshot(raw, run_id=run, output=output/directory, key_root=keys/directory)
        vault.for_run(run).service._record_access(principal, 'encrypted_export', target, True)
        members.append({'run_id': run, 'directory': directory, 'raw_bytes': len(raw),
                        'raw_sha256': exported['raw_sha256'], 'segments': len(exported['segments'])})
        print(json.dumps({'archived_runs': len(members), 'required_runs': len(runs)}), flush=True)
    manifest = {'format': COLLECTION, 'runs': members, 'models_repeated': 0,
                'scope': 'retained benchmark evidence; external pinned runtime images are not copied'}
    export_snapshot(canonical_json(manifest).encode(), run_id=COLLECTION,
                    output=output/'collection', key_root=keys/'collection')
    save('external.v3_archive_export_completed', {'runs': len(members), 'output': str(output),
         'independent_recovery': 'pending', 'MEM_copy': 'pending', 'goal_complete': False})


if __name__ == '__main__': main()
