"""Recover actual public-test and Code audit evidence, without another model run."""
import base64
from hashlib import sha256
import json
import subprocess

RUN = 'external-windows-confirmation-v3-public-recovery-v1-20261018'


def main():
    from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
    from benchmarks.code_replay.run_evidence import operational_evidence
    from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
    from benchmarks.code_replay.confirmation_v3_grade import LOCK, MODELS, complete_cases
    from benchmarks.code_replay.windows_retain import PROGRAM, decode_recovery
    from benchmarks.code_replay.windows_transport import framed_command, framed_input
    scope = EvidenceScope('benchmark', 'local-operator', 'click-20261017')
    principal = EvidencePrincipal('local-benchmark-operator', EvidenceRole.ADMINISTRATOR, scope)
    vault = operational_evidence(EVIDENCE_ROOT, vault_id='confirmation-v1', scope=scope, writing_run=RUN)
    def events(run): return vault.inspect(principal, run)
    def of(es, kind): return [e['envelope']['payload'] for e in es if e['envelope']['event_type'] == kind]
    if events(RUN): raise ValueError('recovery already attempted; inspect retained progress')
    lock, = of(events(LOCK), 'external.v3_execution_manifest_frozen')
    models = events(MODELS)
    completed = of(models, 'external.v3_case_completed')
    complete_cases(lock, completed, of(models, 'external.v3_models_completed'))
    def save(kind, payload): return vault.capture(run_id=RUN, kind=kind, principal=principal, payload=payload)
    save('external.v3_public_recovery_planned', {'driver_source': job['driver_source'],
        'recovery_program': PROGRAM, 'bridge_source': job['bridge_source'], 'cases': 76,
        'models_repeated': 0, 'credential_export': False})
    cases = {r['block']['slot']: r for r in lock['staged_blocks']}
    finished = []
    for summary in completed:
        case = cases[summary['slot']]['cases'][summary['arm']]
        target_run = RUN + '-block-' + str(summary['slot']) + '-' + summary['arm']
        target = operational_evidence(EVIDENCE_ROOT, vault_id='confirmation-v1', scope=scope, writing_run=target_run)
        if target.inspect(principal, target_run): raise ValueError('public evidence recovery already attempted')
        def retain(kind, payload): return target.capture(run_id=target_run, kind=kind, principal=principal, payload=payload)
        payload = {'case': {k: case[k] for k in ('operator', 'atmem_home', 'database', 'scope')},
                   'bridge_source': job['bridge_source'], 'program': PROGRAM}
        wrapper = "import subprocess,sys,json;p=subprocess.run([job['python'],'-I','-c',\"import json,sys;job=json.load(sys.stdin);exec(job['program'])\"],input=json.dumps(job['payload']).encode());sys.exit(p.returncode)"
        request = {'program': wrapper, 'python': lock['staging_manifest']['product_python'], 'payload': payload}
        retain('external.v3_public_recovery_dispatch', {'request': request, 'model_case_run': summary['task_run']})
        proc = subprocess.run(framed_command(), input=framed_input(request), capture_output=True, timeout=120)
        streams = {}
        for name, raw in [('stdout', proc.stdout), ('stderr', proc.stderr)]:
            receipts = []
            for offset in range(0, len(raw), 3_000_000):
                receipts.append(retain('external.v3_public_recovery_chunk', {'stream': name, 'offset': offset,
                    'total_bytes': len(raw), 'sha256': sha256(raw).hexdigest(),
                    'content_base64': base64.b64encode(raw[offset:offset+3_000_000]).decode()}))
            streams[name] = {'bytes': len(raw), 'sha256': sha256(raw).hexdigest(), 'receipts': receipts}
        retain('external.v3_public_recovery_transport', {'exit_code': proc.returncode, 'streams': streams})
        if proc.returncode: raise RuntimeError('public recovery failure retained; no automatic retry')
        compressed, result = decode_recovery(proc.stdout)
        item = {**{k: summary[k] for k in ('slot', 'instance_id', 'repeat', 'arm')},
                'task_run': target_run, 'streams': streams, 'recovered_bytes': compressed['bytes'],
                'recovered_sha256': compressed['sha256'], 'public_run_id': result['public_run_id'],
                'public_event_count': len(result['public_test_events']),
                'code_audit_events': len(result.get('code_audit_events', [])),
                'code_audit_chain_verified': result.get('code_audit_chain_verified')}
        retain('external.v3_public_evidence_recovered', item)
        save('external.v3_public_evidence_recovered', item); finished.append(item)
        print(json.dumps({'recovered_cases': len(finished), 'slot': summary['slot'], 'arm': summary['arm']}), flush=True)
    save('external.v3_public_recovery_completed', {'cases': len(finished), 'models_repeated': 0,
                                                 'no_case_deleted': True})


if __name__ == '__main__': main()
