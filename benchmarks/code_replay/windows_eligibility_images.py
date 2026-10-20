"""Image qualification for the frozen forty-candidate pool, not model selection."""
import base64
import json
import os
from pathlib import Path
import re
import subprocess
from uuid import uuid4

from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.external_catalog import digest, ELIGIBILITY_REPOSITORIES, ELIGIBILITY_SEED
from benchmarks.code_replay.external_runtime import command as runtime_command
from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT, REGISTRY, bound_descriptor, runtime_program, runtime_evidence_qualifies
from benchmarks.code_replay.windows_transport import framed_command, framed_input

PREFLIGHT = Path(os.environ.get('ATMEM_BENCHMARK_PREFLIGHT',
    '/Volumes/MEM/AtMem-Code-Replay-20261017/cross-repository-confirmation-eligibility-v2'))
RUN = 'external-windows-confirmation-eligibility-images-v2-20261018'
LOCK_RUN = 'external-windows-confirmation-eligibility-v2-20261018'


def validate_pool(selection, metadata):
    chosen = selection['selected']
    if (selection['seed'] != ELIGIBILITY_SEED or selection['per_repo'] != 8
        or selection.get('sampling_stage') != 'eligibility_candidates_not_final_model_tasks'
        or selection.get('final_model_tasks_per_repository') != 4
        or set(selection['ordered_candidate_pools']) != set(ELIGIBILITY_REPOSITORIES)
        or len(chosen) != 40 or len({r['instance_id'] for r in chosen}) != 40
        or metadata['selection_sha256'] != digest(selection)
        or len(metadata['reports']) != 40
        or {r['instance_id'] for r in metadata['reports']} != {r['instance_id'] for r in chosen}):
        raise ValueError('exact prospective forty-candidate eligibility pool required')
    for repo in ELIGIBILITY_REPOSITORIES:
        identities = [r['instance_id'] for r in chosen if r['repo'] == repo]
        if identities != selection['ordered_candidate_pools'][repo][:8]:
            raise ValueError('candidate order or repository membership differs')
    for row in metadata['reports']:
        if row['status'] != 'metadata_verified_environment_not_executed' or row['metadata']['instance_id'] != row['instance_id']:
            raise ValueError('complete identity-bound metadata required')


def main():
    selection = json.loads((PREFLIGHT / 'selection.json').read_bytes())
    metadata = json.loads((PREFLIGHT / 'metadata.json').read_bytes())
    validate_pool(selection, metadata)
    scope = EvidenceScope('benchmark', 'local-operator', 'click-20261017')
    principal = EvidencePrincipal('local-benchmark-operator', EvidenceRole.ADMINISTRATOR, scope)
    vault = ReplayEvidence(EVIDENCE_ROOT, vault_id='confirmation-v1', scope=scope)
    if vault.inspect(principal, RUN):
        raise ValueError('eligibility images already dispatched; inspect handle, no implicit retry')
    locks = vault.inspect(principal, LOCK_RUN)
    lock = next(e['envelope']['payload'] for e in locks if e['envelope']['event_type'] == 'external.confirmation_v2_candidate_locked')
    if lock['wheel_sha256'] != '9900aa70371a1ec911b7215532711cbdc83da726198ca0eacf85bbf6054146c8':
        raise ValueError('new candidate lock differs')
    def save(kind, payload):
        return vault.capture(run_id=RUN, kind=kind, principal=principal, payload=payload)
    def remote(job, timeout):
        try:
            proc = subprocess.run(framed_command(), input=framed_input(job), capture_output=True, timeout=timeout)
            return {'transport_exit': proc.returncode, 'transport_stdout_base64': base64.b64encode(proc.stdout).decode(),
                'transport_stderr_base64': base64.b64encode(proc.stderr).decode()}
        except subprocess.TimeoutExpired as exc:
            return {'transport_exit': None, 'transport_failure': 'timeout', 'timeout_seconds': timeout,
                'transport_stdout_base64': base64.b64encode(exc.stdout or b'').decode(),
                'transport_stderr_base64': base64.b64encode(exc.stderr or b'').decode()}
    program = runtime_program()
    save('external.eligibility_images_planned', {'selection': selection, 'metadata': metadata,
        'driver_source': Path(__file__).read_text(), 'registry_program': REGISTRY, 'runtime_program': program,
        'transport': framed_command(), 'candidate_lock': lock, 'solver_calls': 0, 'final_model_selection': False})
    registry = []
    for selected, row in zip(selection['selected'], metadata['reports']):
        task = row['metadata']
        if task['instance_id'] != selected['instance_id']:
            raise ValueError('metadata order differs from frozen selection')
        identity, tag = task['instance_id'], task['image']
        if not re.fullmatch(r'swebench/sweb\.eval\.x86_64\.[A-Za-z0-9_.-]+:latest', tag):
            raise ValueError('declared benchmark Docker Hub image required before registry access')
        record = {'instance_id': identity, 'repo': selected['repo'], 'image_tag': tag,
            **remote({'program': REGISTRY, 'image': tag}, 75)}
        try:
            if record['transport_exit'] != 0:
                raise RuntimeError('registry transport failed')
            result = json.loads(base64.b64decode(record['transport_stdout_base64']))
            if result['exit_code']:
                raise RuntimeError('declared image inaccessible')
            descriptor = bound_descriptor(base64.b64decode(result['stdout_base64'], validate=True))
            record.update(descriptor=descriptor, image=tag.rsplit(':', 1)[0] + '@' + descriptor['digest'])
        except Exception as exc:
            record['failure'] = type(exc).__name__ + ': ' + str(exc)
        save('external.eligibility_registry_result', record); registry.append(record)
        print(json.dumps({'instance_id': identity, 'phase': 'registry', 'passed': 'descriptor' in record}), flush=True)
    save('external.eligibility_registry_completed', {'rows': registry, 'solver_calls': 0, 'final_model_selection': False})
    passed = 0
    for row in registry:
        if 'descriptor' not in row:
            continue
        name = 'atmem-runtime-control-' + uuid4().hex
        job = {'program': program, 'image': row['image'], 'runtime_command': runtime_command(row['image'], name)}
        save('external.eligibility_runtime_dispatch', {'instance_id': row['instance_id'], 'job': job})
        record = {'instance_id': row['instance_id'], 'repo': row['repo'], 'image': row['image'],
            **remote(job, 300), 'qualified': False}
        if record['transport_exit'] == 0:
            record['result'] = json.loads(base64.b64decode(record['transport_stdout_base64']))
            record['qualified'] = runtime_evidence_qualifies(record, row['descriptor'])
        save('external.eligibility_runtime_result', record)
        passed += int(record['qualified'])
        print(json.dumps({'instance_id': row['instance_id'], 'phase': 'runtime', 'qualified': record['qualified'],
            'reason': record.get('result', {}).get('pull', {}).get('reason') or record.get('transport_failure')}), flush=True)
    save('external.eligibility_images_completed', {'candidates': 40, 'runtime_qualified': passed,
        'solver_calls': 0, 'final_model_tasks': 'not selected; source/product/reference/public qualification pending'})


if __name__ == '__main__':
    main()
