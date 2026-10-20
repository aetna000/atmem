"""Export verified public base source from completed source-boundary controls."""
import base64
from hashlib import sha256
import json
from pathlib import Path

from atmem.core.canonical import canonical_json
from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from benchmarks.code_replay.external_solver_source import tracked_solver_snapshot
from benchmarks.code_replay.projection_evidence import verified_projection_controller
from benchmarks.code_replay.run_evidence import operational_evidence
from benchmarks.code_replay.source_policy import SourcePolicy
from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT


RUN = 'external-windows-confirmation-public-exports-v1-20261018'
BOUNDARIES = (
    'external-windows-runtime-projection-boundary-operator-v2-20261018',
    'external-windows-runtime-projection-boundary-oci-operator-v2-20261018',
    'external-windows-runtime-projection-boundary-pyvista-vtk931-operator-v2-20261018-lossless-v4',
)


def recover_export(events, descriptor):
    by_id = {e['object_id']: e for e in events}
    parts = []; offset = 0
    for receipt in descriptor['receipts']:
        event = by_id[receipt['object_id']]; envelope = event['envelope']; row = envelope['payload']
        if (envelope['event_type'] != 'external.public_source_chunk'
            or envelope['run_id'] != receipt['run_id'] or envelope['run_id'] != descriptor['export_run']
            or sha256(canonical_json(row).encode()).hexdigest() != receipt['payload_sha256']
            or row['offset'] != offset):
            raise ValueError('export receipt identity/order differs')
        raw = base64.b64decode(row['bytes_base64'], validate=True)
        if not 0 < len(raw) <= 3_000_000:
            raise ValueError('bounded source export chunk required')
        offset += len(raw)
        if offset > descriptor['bytes'] or offset > 80_000_000:
            raise ValueError('source export expansion limit')
        parts.append(raw)
    raw = b''.join(parts)
    if len(raw) != descriptor['bytes'] or sha256(raw).hexdigest() != descriptor['sha256']:
        raise ValueError('complete export identity differs')
    result = json.loads(raw)
    if result['instance_id'] != descriptor['instance_id'] or result['evaluator_material_exported'] is not False:
        raise ValueError('source export role differs')
    return result


def verified_export(worker, public):
    """Only unchanged, complete public Git objects can become a solver export."""
    if (worker.get('phase') != 'unchanged' or worker.get('base_source_verified') is not True
        or worker.get('assembled_bytes_verified') is not True
        or worker.get('runtime_fixtures_verified') is not True
        or not worker.get('original_sha256')
        or worker['original_sha256'] != worker.get('candidate_sha256')
        or worker['original_sha256'] != worker.get('assembled_sha256')
        or public.get('qualified') is not True):
        raise ValueError('complete unchanged verified source boundary required')
    policy = worker['source_policy']
    parsed = {}
    for kind in ('commits', 'trees'):
        item = public['objects'][kind]
        raw = base64.b64decode(item['raw_base64'], validate=True)
        if sha256(raw).hexdigest() != item['sha256'] or json.loads(raw) != item['parsed']:
            raise ValueError('public Git response differs from retained bytes')
        parsed[kind] = item['parsed']
    snapshot = tracked_solver_snapshot(worker['original_files_base64'], worker['tracked_base'],
        parsed['commits'], parsed['trees'], public['base_commit'],
        runtime_manifest=worker['runtime_manifest'],
        runtime_policy=SourcePolicy(tuple(policy['source_roots']), test_roots=tuple(policy['test_roots'])))
    encoded = {name: base64.b64encode(raw).decode() for name, raw in snapshot.pop('files').items()}
    extras = {name: sha256(base64.b64decode(raw, validate=True)).hexdigest()
              for name, raw in worker['original_files_base64'].items() if name not in encoded}
    return {**snapshot, 'files_base64': encoded, 'image_extras_sha256': extras,
            'instance_id': public['instance_id'], 'repository': public['repo'],
            'public_commit': parsed['commits'], 'public_tree': parsed['trees'],
            'evaluator_material_exported': False, 'solver_calls': 0}


def main():
    scope = EvidenceScope('benchmark', 'local-operator', 'click-20261017')
    principal = EvidencePrincipal('local-benchmark-operator', EvidenceRole.ADMINISTRATOR, scope)
    vault = operational_evidence(EVIDENCE_ROOT, vault_id='confirmation-v1', scope=scope, writing_run=RUN)
    if vault.inspect(principal, RUN):
        raise ValueError('export already retained; no implicit restart')
    cache = {}
    def events(run):
        if run not in cache:
            cache[run] = vault.inspect(principal, run)
        return cache[run]
    def save(kind, payload):
        return vault.capture(run_id=RUN, kind=kind, principal=principal, payload=payload)
    def resolve(run, identity, phase):
        found = [e for e in events(run) if e['envelope']['event_type'] in {
            'external.runtime_projection_result', 'external.runtime_projection_reused_result'}
            and e['envelope']['payload'].get('instance_id') == identity
            and e['envelope']['payload'].get('phase') == phase]
        if len(found) != 1:
            raise ValueError('exact unique completed source phase required')
        event = found[0]; row = event['envelope']['payload']
        if event['envelope']['event_type'].endswith('_reused_result'):
            originals = [e for e in events(row['prior_run']) if e['object_id'] == row['prior_object_id']]
            if (len(originals) != 1 or sha256(canonical_json(originals[0]['envelope']['payload']).encode()).hexdigest()
                != row['prior_payload_sha256']):
                raise ValueError('reused source receipt identity differs')
            return resolve(row['prior_run'], identity, phase)
        return run, row
    groups = []
    for run in BOUNDARIES:
        plans = [e['envelope']['payload'] for e in events(run)
                 if e['envelope']['event_type'] == 'external.runtime_projection_planned']
        ends = [e['envelope']['payload'] for e in events(run)
                if e['envelope']['event_type'] == 'external.runtime_projection_completed']
        if len(plans) != 1 or len(ends) != 1:
            raise ValueError('all three source-boundary batches must be terminal')
        groups.append((run, plans[0], ends[0]['qualified_identities']))
    candidates = [identity for run, plan, ids in groups for identity in ids]
    if len(candidates) != len(set(candidates)):
        raise ValueError('source qualification groups overlap')
    save('external.confirmation_exports_planned', {'driver_source': Path(__file__).read_text(),
        'source_runs': list(BOUNDARIES), 'identities': candidates, 'model_calls': 0,
        'not_final_model_selection': True, 'per_task_encrypted_vaults': True})
    public_root = Path('public-git')
    manifest = json.loads((public_root/'manifest.json').read_bytes())
    declared = {item['instance_id']: item for item in manifest['results']}
    results = []
    for run, plan, ids in groups:
        for identity in ids:
            task_run = 'external-confirmation-public-source-' + identity + '-v1-20261018'
            target = operational_evidence(EVIDENCE_ROOT, vault_id='confirmation-v1', scope=scope, writing_run=task_run)
            if target.inspect(principal, task_run):
                raise ValueError('task export already retained; no duplicate export')
            try:
                raw = (public_root/(identity+'.json')).read_bytes()
                if len(raw) != declared[identity]['bytes'] or sha256(raw).hexdigest() != declared[identity]['sha256']:
                    raise ValueError('public Git input manifest differs')
                public = json.loads(raw)
                if public.get('instance_id') != identity:
                    raise ValueError('public source identity differs from source phase')
                source_run, row = resolve(run, identity, 'unchanged')
                worker = verified_projection_controller(events(source_run), row)['worker']
                exported = verified_export(worker, public)
                payload = canonical_json(exported).encode()
                receipts = []
                for offset in range(0, len(payload), 3_000_000):
                    receipts.append(target.capture(run_id=task_run, kind='external.public_source_chunk',
                        principal=principal, payload={'offset': offset,
                        'bytes_base64': base64.b64encode(payload[offset:offset+3_000_000]).decode()}))
                result = {'instance_id': identity, 'qualified': True, 'source_run': source_run,
                    'source_phase_object': next(e['object_id'] for e in events(source_run)
                        if e['envelope']['event_type'] == 'external.runtime_projection_result'
                        and e['envelope']['payload'] == row),
                    'export_run': task_run, 'bytes': len(payload), 'sha256': sha256(payload).hexdigest(),
                    'receipts': receipts, 'files': len(exported['files_base64']), 'model_calls': 0}
            except Exception as exc:
                result = {'instance_id': identity, 'qualified': False,
                          'failure': type(exc).__name__ + ': ' + str(exc), 'model_calls': 0}
            save('external.confirmation_public_export_result', result)
            results.append(result)
            print(json.dumps({k:v for k,v in result.items() if k != 'receipts'}), flush=True)
    save('external.confirmation_exports_completed', {'results': results,
        'qualified': sum(row['qualified'] for row in results), 'original_pool_changed': False,
        'final_model_manifest_frozen': False, 'model_calls': 0})


if __name__ == '__main__':
    main()
