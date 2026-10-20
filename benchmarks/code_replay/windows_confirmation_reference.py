"""Parent/reference environment controls for the fixed confirmation pool only."""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from uuid import uuid4

from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.external_catalog import digest
from benchmarks.code_replay.external_qualification import harness_material, task_material, worker_command
from benchmarks.code_replay.external_qualify_worker import validated_files
from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT, PREFLIGHT, RUN as IMAGES_RUN, validate_preflight, runtime_evidence_qualifies
from benchmarks.code_replay.windows_transport import command, worker_program

RUN = 'external-windows-confirmation-reference-v1-20261018'


def verified_material_cache(events, worker_sha256):
    if not events:
        return None
    complete = [e['envelope']['payload'] for e in events if e['envelope']['event_type'] == 'external.eligibility_materials_completed']
    if len(complete) != 1:
        raise ValueError('material prefetch is live; wait on its handle before starting reference controls')
    if complete[0]['worker_sha256'] != worker_sha256:
        raise ValueError('cached worker registration differs')
    result = {}
    for event in events:
        if event['envelope']['event_type'] != 'external.eligibility_material_result':
            continue
        row = event['envelope']['payload']
        if row['instance_id'] in result or type(row['verified']) is not bool:
            raise ValueError('duplicate or invalid cached evaluator material')
        if row['verified'] and digest(row['material']) != row['material_sha256']:
            raise ValueError('cached evaluator material digest differs')
        result[row['instance_id']] = row
    if len(result) != complete[0]['material_records']:
        raise ValueError('cached material count differs')
    return result


def strict_reference_qualified(parent, reference):
    for row in (parent, reference):
        worker = row.get('worker', {})
        marks = worker.get('grading', {})
        if (row.get('reason') or row.get('exit_code') != 0 or worker.get('worker_failure')
            or worker.get('base_source_verified') is not True
            or worker.get('embedded_test_patch_verified') is not True
            or not marks.get('results_found') or marks.get('expected_f2p', 0) <= 0
            or marks.get('p2p_skipped') != 0 or marks.get('p2p_failure') != 0
            or marks.get('p2p_success') != marks.get('expected_p2p')):
            return False
    a, b = parent['worker']['grading'], reference['worker']['grading']
    return bool(a['expected_f2p'] == b['expected_f2p']
        and a['expected_p2p'] == b['expected_p2p']
        and a['observed_f2p_failures'] == a['expected_f2p']
        and a['f2p_failure'] == a['expected_f2p'] and a['f2p_success'] == 0
        and b['f2p_success'] == b['expected_f2p'] and b['f2p_failure'] == 0
        and b['resolution'] == 'RESOLVED_FULL')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--eligibility-v2', action='store_true', help='Qualify the frozen forty-candidate pool; do not select model tasks')
    args = parser.parse_args()
    preflight, images_run, run_id = PREFLIGHT, IMAGES_RUN, RUN
    if args.eligibility_v2:
        from benchmarks.code_replay.windows_eligibility_images import PREFLIGHT as NEW_PREFLIGHT, RUN as NEW_IMAGES_RUN, validate_pool
        preflight, images_run = NEW_PREFLIGHT, NEW_IMAGES_RUN
        run_id = 'external-windows-confirmation-eligibility-reference-v2-20261018'
    selection = json.loads((preflight / 'selection.json').read_bytes())
    metadata = json.loads((preflight / 'metadata.json').read_bytes())
    (validate_pool if args.eligibility_v2 else validate_preflight)(selection, metadata)
    scope = EvidenceScope('benchmark', 'local-operator', 'click-20261017')
    principal = EvidencePrincipal('local-benchmark-operator', EvidenceRole.ADMINISTRATOR, scope)
    vault = ReplayEvidence(EVIDENCE_ROOT, vault_id='confirmation-v1', scope=scope)
    if vault.inspect(principal, run_id):
        raise ValueError('reference controls already dispatched; no implicit retry')
    images = vault.inspect(principal, images_run)
    def image_rows(kind):
        return [e['envelope']['payload'] for e in images if e['envelope']['event_type'] == kind]
    if len(image_rows('external.eligibility_images_completed' if args.eligibility_v2 else 'external.confirmation_images_completed')) != 1:
        raise ValueError('image qualification must be terminal before reference controls')
    all_runtimes = image_rows('external.eligibility_runtime_result' if args.eligibility_v2 else 'external.confirmation_runtime_result')
    descriptors = {r['instance_id']: r['descriptor'] for r in image_rows('external.eligibility_registry_result' if args.eligibility_v2 else 'external.confirmation_registry_descriptor') if 'descriptor' in r}
    runtimes = {r['instance_id']: r for r in all_runtimes
        if runtime_evidence_qualifies(r, descriptors[r['instance_id']])}
    if len({r['instance_id'] for r in all_runtimes}) != len(all_runtimes):
        raise ValueError('duplicate runtime attempt')
    source = Path(__file__).with_name('external_qualify_worker.py').read_text()
    registration = None
    validate_material = validated_files
    if args.eligibility_v2:
        from benchmarks.code_replay.eligibility_binding import bound_worker_source
        source, registration = bound_worker_source(selection, metadata)
        namespace = {'__name__': 'operator_bound_private_worker'}
        exec(compile(source, 'operator_bound_private_worker.py', 'exec'), namespace)
        validate_material = namespace['validated_files']
    cached_materials = None
    if args.eligibility_v2:
        from benchmarks.code_replay.windows_eligibility_materials import RUN as MATERIAL_RUN
        material_events = vault.inspect(principal, MATERIAL_RUN)
        cached_materials = verified_material_cache(material_events, sha256(source.encode()).hexdigest())
    cached_successes = [r for r in (cached_materials or {}).values() if r['verified']]
    harness = cached_successes[0]['material']['harness_files'] if cached_successes else harness_material()
    def save(kind, payload):
        return vault.capture(run_id=run_id, kind=kind, principal=principal, payload=payload)
    save('external.eligibility_runtime_evidence_verified' if args.eligibility_v2 else 'external.confirmation_runtime_interpretation_corrected', {
        'reason': 'Exact retained raw transport and verified registry image identities required' if args.eligibility_v2 else 'Docker 29 containerd image Id is manifest digest; original controller expected only config digest',
        'new_image_or_runtime_execution': False, 'raw_transport_metadata_equality_required': True,
        'original_runtime_qualified': sorted(r['instance_id'] for r in all_runtimes if r['qualified']),
        'corrected_runtime_qualified': sorted(runtimes),
        'verifier_source': Path(__file__).with_name('windows_confirmation_images.py').read_text(),
        'original_negative_records_preserved': True})
    selected = {r['instance_id']: r for r in selection['selected']}
    tasks = {r['instance_id']: r['metadata'] for r in metadata['reports']}
    if not set(runtimes) <= set(selected):
        raise ValueError('runtime outside frozen pool')
    qualification_workers = 4 if args.eligibility_v2 else 2
    save('external.confirmation_reference_planned', {'driver_source': Path(__file__).read_text(),
        'worker_source': source, 'worker_sha256': sha256(source.encode()).hexdigest(),
        'selection_sha256': digest(selection), 'harness_files': harness,
        'operator_task_registration': registration,
        'eligibility_candidates_not_final_model_tasks': args.eligibility_v2,
        'runtime_eligible': sorted(runtimes), 'unrun_environment': sorted(set(selected) - set(runtimes)),
        'max_workers': qualification_workers, 'solver_calls': 0, 'automatic_replacement': False})
    jobs = []
    for identity in selected:
        if identity not in runtimes:
            continue
        try:
            if cached_materials is not None:
                cached = cached_materials.get(identity)
                if not cached or not cached['verified']:
                    raise ValueError('prefetch material unavailable: ' + str(cached.get('error') if cached else 'missing'))
                material = cached['material']
                if material['harness_files'] != harness:
                    raise ValueError('prefetch harness identity differs')
            else:
                material = {'instance_id': identity, 'base_commit': tasks[identity]['base_commit'],
                    'task_files': task_material(selected[identity]), 'harness_files': harness}
            validate_material({**material, 'phase': 'parent'}, task_identity=identity)
        except Exception as exc:
            save('external.confirmation_material_unqualified', {'instance_id': identity,
                'error': type(exc).__name__ + ': ' + str(exc), 'solver_calls': 0})
            continue
        save('external.confirmation_private_material', material)
        for phase in ('parent', 'reference'):
            name = 'atmem-reference-control-' + uuid4().hex
            job = {'program': worker_program(), 'name': name,
                'command': worker_command(runtimes[identity]['image'], name, source),
                'payload': {**material, 'phase': phase}}
            save('external.confirmation_reference_dispatch', {'instance_id': identity, 'phase': phase, 'job': job})
            jobs.append((identity, phase, job))
    def execute(item):
        identity, phase, job = item
        try:
            if args.eligibility_v2:
                from benchmarks.code_replay.windows_transport import framed_command, framed_input
                return identity, phase, subprocess.run(framed_command(), input=framed_input(job), capture_output=True, timeout=205), None
            return identity, phase, subprocess.run(command(), input=json.dumps(job).encode(), capture_output=True, timeout=205), None
        except subprocess.TimeoutExpired as exc:
            from types import SimpleNamespace
            partial = SimpleNamespace(returncode=None, stdout=exc.stdout or b'', stderr=exc.stderr or b'')
            return identity, phase, partial, 'TimeoutExpired: incomplete transport after 205 seconds'
        except Exception as exc:
            return identity, phase, None, type(exc).__name__ + ': ' + str(exc)
    results = {}
    with ThreadPoolExecutor(max_workers=qualification_workers) as pool:
        for future in as_completed([pool.submit(execute, item) for item in jobs]):
            identity, phase, proc, failure = future.result()
            row = {'instance_id': identity, 'phase': phase, 'transport_failure': failure}
            if proc is not None:
                row.update(transport_exit_code=proc.returncode, streams={})
                for stream, raw in [('stdout', proc.stdout), ('stderr', proc.stderr)]:
                    receipts = []
                    for offset in range(0, len(raw), 3_000_000):
                        receipts.append(save('external.confirmation_reference_chunk', {
                            'instance_id': identity, 'phase': phase, 'stream': stream, 'offset': offset,
                            'total_bytes': len(raw), 'sha256': sha256(raw).hexdigest(),
                            'content_base64': base64.b64encode(raw[offset:offset + 3_000_000]).decode()}))
                    row['streams'][stream] = {'bytes': len(raw), 'sha256': sha256(raw).hexdigest(), 'receipts': receipts}
                if proc.returncode == 0:
                    controller = json.loads(proc.stdout)
                    controller.pop('raw_output_base64', None)
                    worker = controller.get('worker', {})
                    worker.pop('stdout_base64', None); worker.pop('stderr_base64', None)
                    row['controller'] = controller
            results[(identity, phase)] = row
            save('external.confirmation_reference_result', row)
            controller = row.get('controller', {})
            print(json.dumps({'instance_id': identity, 'phase': phase, 'controls_recorded': len(results),
                'reason': controller.get('reason') or failure,
                'grading': controller.get('worker', {}).get('grading')}), flush=True)
    summaries = []
    for identity in selected:
        pair = [results.get((identity, phase), {}).get('controller', {}) for phase in ('parent', 'reference')]
        summaries.append({'instance_id': identity, 'runtime_qualified': identity in runtimes,
            'reference_qualified': strict_reference_qualified(*pair)})
    save('external.confirmation_reference_completed', {'rows': summaries, 'solver_calls': 0,
        'reference_qualified': sum(row['reference_qualified'] for row in summaries),
        'all_original_tasks_retained': True})
    print(json.dumps({'rows': summaries, 'solver_calls': 0}), flush=True)


if __name__ == '__main__':
    main()
