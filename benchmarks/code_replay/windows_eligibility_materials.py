"""Prefetch verified evaluator-only material while independent image checks run."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
import json
from pathlib import Path

from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.eligibility_binding import bound_worker_source
from benchmarks.code_replay.external_catalog import digest
from benchmarks.code_replay.external_qualification import harness_material, task_material
from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
from benchmarks.code_replay.windows_eligibility_images import PREFLIGHT, RUN as IMAGES_RUN, validate_pool

RUN = 'external-windows-eligibility-materials-v2-20261018'


def main():
    selection = json.loads((PREFLIGHT / 'selection.json').read_bytes())
    metadata = json.loads((PREFLIGHT / 'metadata.json').read_bytes())
    validate_pool(selection, metadata)
    scope = EvidenceScope('benchmark', 'local-operator', 'click-20261017')
    principal = EvidencePrincipal('local-benchmark-operator', EvidenceRole.ADMINISTRATOR, scope)
    vault = ReplayEvidence(EVIDENCE_ROOT, vault_id='confirmation-v1', scope=scope)
    if vault.inspect(principal, RUN):
        raise ValueError('material prefetch already dispatched; inspect its handle')
    events = vault.inspect(principal, IMAGES_RUN)
    complete = [e for e in events if e['envelope']['event_type'] == 'external.eligibility_registry_completed']
    if len(complete) != 1:
        raise ValueError('full frozen-pool registry accounting required')
    registry = complete[0]['envelope']['payload']['rows']
    available = {r['instance_id'] for r in registry if 'descriptor' in r}
    worker, registration = bound_worker_source(selection, metadata)
    namespace = {'__name__': 'operator_bound_prefetch'}
    exec(compile(worker, 'operator_bound_prefetch.py', 'exec'), namespace)
    tasks = {r['instance_id']: r['metadata'] for r in metadata['reports']}
    harness = harness_material()
    def save(kind, payload):
        return vault.capture(run_id=RUN, kind=kind, principal=principal, payload=payload)
    save('external.eligibility_materials_planned', {'selection_sha256': digest(selection),
        'driver_source': Path(__file__).read_text(), 'registered_worker': worker,
        'registration': registration, 'available_images': sorted(available),
        'max_workers': 4, 'solver_calls': 0, 'material_to_product_or_solver': False})
    chosen = [r for r in selection['selected'] if r['instance_id'] in available]
    def fetch(selected):
        identity = selected['instance_id']
        try:
            material = {'instance_id': identity, 'base_commit': tasks[identity]['base_commit'],
                'task_files': task_material(selected), 'harness_files': harness}
            namespace['validated_files']({**material, 'phase': 'parent'}, task_identity=identity)
            return {'instance_id': identity, 'material': material, 'material_sha256': digest(material),
                'verified': True}
        except Exception as exc:
            return {'instance_id': identity, 'verified': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    verified = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        for number, future in enumerate(as_completed([pool.submit(fetch, r) for r in chosen]), 1):
            result = future.result()
            save('external.eligibility_material_result', result)
            verified += int(result['verified'])
            print(json.dumps({'instance_id': result['instance_id'], 'recorded': number,
                'verified': result['verified'], 'error': result.get('error')}), flush=True)
    save('external.eligibility_materials_completed', {'available_images': len(chosen),
        'material_records': len(chosen), 'verified_materials': verified,
        'worker_sha256': sha256(worker.encode()).hexdigest(), 'solver_calls': 0})


if __name__ == '__main__':
    main()
