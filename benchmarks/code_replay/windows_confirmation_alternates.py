"""Read-only registry checks for official-name images of inaccessible tasks.

No task replacement, image pull, container execution, model or owner login.
Any resolved alternate still needs recorded runtime/source/reference controls.
"""
import base64
import json
from pathlib import Path
import subprocess

from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT, RUN as IMAGES_RUN, REGISTRY, bound_descriptor
from benchmarks.code_replay.windows_transport import command

RUN = 'external-windows-confirmation-alternate-images-v1-20261018'
EXPECTED_UNAVAILABLE = frozenset({'sqlfluff__sqlfluff-4084', 'sqlfluff__sqlfluff-3436',
    'sqlfluff__sqlfluff-4041', 'pytest-dev__pytest-5227'})


def alternate_tag(identity):
    if identity not in EXPECTED_UNAVAILABLE:
        raise ValueError('only recorded inaccessible original identities allowed')
    return 'swebench/sweb.eval.x86_64.' + identity + ':latest'


def main():
    scope = EvidenceScope('benchmark', 'local-operator', 'click-20261017')
    principal = EvidencePrincipal('local-benchmark-operator', EvidenceRole.ADMINISTRATOR, scope)
    vault = ReplayEvidence(EVIDENCE_ROOT, vault_id='confirmation-v1', scope=scope)
    if vault.inspect(principal, RUN):
        raise ValueError('alternate registry check already recorded; no automatic retry')
    events = vault.inspect(principal, IMAGES_RUN)
    rows = [e['envelope']['payload'] for e in events if e['envelope']['event_type'] == 'external.confirmation_registry_descriptor']
    if len(rows) != 20 or {r['instance_id'] for r in rows if 'descriptor' not in r} != EXPECTED_UNAVAILABLE:
        raise ValueError('exact twenty original registry results and four inaccessible identities required')
    def save(kind, payload):
        return vault.capture(run_id=RUN, kind=kind, principal=principal, payload=payload)
    save('external.confirmation_alternates_planned', {'driver_source': Path(__file__).read_text(),
        'program': REGISTRY, 'tags': {i: alternate_tag(i) for i in sorted(EXPECTED_UNAVAILABLE)},
        'models_run': 0, 'tasks_replaced': 0, 'image_pull': False, 'reference_qualification': 'still required'})
    results = []
    for identity in sorted(EXPECTED_UNAVAILABLE):
        tag = alternate_tag(identity)
        proc = subprocess.run(command(), input=json.dumps({'program': REGISTRY, 'image': tag}).encode(), capture_output=True, timeout=75)
        row = {'instance_id': identity, 'image_tag': tag, 'transport_exit': proc.returncode,
            'transport_stdout_base64': base64.b64encode(proc.stdout).decode(),
            'transport_stderr_base64': base64.b64encode(proc.stderr).decode()}
        try:
            if proc.returncode:
                raise RuntimeError('registry transport failed')
            result = json.loads(proc.stdout)
            if result['exit_code']:
                raise RuntimeError('alternate image unavailable')
            row['descriptor'] = bound_descriptor(base64.b64decode(result['stdout_base64'], validate=True))
            row['image'] = tag.rsplit(':', 1)[0] + '@' + row['descriptor']['digest']
        except Exception as exc:
            row['failure'] = type(exc).__name__ + ': ' + str(exc)
        results.append(row)
        save('external.confirmation_alternate_registry_result', row)
        print(json.dumps({'instance_id': identity, 'resolved': 'descriptor' in row, 'failure': row.get('failure')}), flush=True)
    save('external.confirmation_alternates_completed', {'rows': results, 'models_run': 0,
        'tasks_replaced': 0, 'source_and_reference_controls_required': True})


if __name__ == '__main__':
    main()
