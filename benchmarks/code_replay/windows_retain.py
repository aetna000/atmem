"""Recover full protected public-test evidence after the completed Windows cohort.

No solver invocation, grading retry, source mutation, credential export or cleanup.
Each case uses a fresh process so installation key paths cannot leak across cases.
"""
import base64
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import zlib

from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.windows_execute import ROOT, RUN
from benchmarks.code_replay.windows_transport import command


PROGRAM = r'''
import base64,hashlib,json,os,zlib
from pathlib import Path
case=job['case'];operator=Path(case['operator'])
preset=json.loads((operator/'preset.json').read_text())
if Path(preset['evidence_root'])!=operator/'protected/vault':
 raise RuntimeError('unexpected protected evidence root')
os.environ['ATMEM_HOME']=case['atmem_home'] or str(operator/'protected')
from atmem.evidence import EvidenceScope,EvidencePrincipal,EvidenceRole
namespace={};exec(compile(job['bridge_source'],'benchmark_bridge.py','exec'),namespace)
run_id=preset['run_id'];scope=EvidenceScope('benchmark','local-operator',run_id)
principal=EvidencePrincipal('local-benchmark-operator',EvidenceRole.ADMINISTRATOR,scope)
evidence=namespace['ReplayEvidence'](Path(preset['evidence_root']),vault_id=run_id,scope=scope)
result={'public_run_id':run_id,'status':evidence.service.protection_status(),
 'public_test_events':evidence.inspect(principal,run_id)}
if case['database']:
 from atmem.memory import Memory
 memory=Memory(case['database'],auto_vectors=False)
 try:
  result['code_audit_events']=memory.store.list_audit_events(case['scope']['subject_id'])
  result['code_audit_chain_verified']=memory.store.verify_audit_chain(case['scope']['subject_id'])
 finally:memory.close()
raw=json.dumps(result,sort_keys=True,separators=(',',':')).encode()
print(json.dumps({'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
 'zlib_base64':base64.b64encode(zlib.compress(raw)).decode()}))
'''


def decode_recovery(raw):
    transport = json.loads(raw)
    recovered = zlib.decompress(base64.b64decode(transport['zlib_base64'], validate=True))
    if len(recovered) != transport['bytes'] or sha256(recovered).hexdigest() != transport['sha256']:
        raise ValueError('protected evidence recovery digest differs')
    result = json.loads(recovered)
    if result['status']['at_rest_state'] != 'encrypted' or result['status']['capture_mode'] != 'full':
        raise ValueError('full encrypted upstream evidence required')
    if result.get('code_audit_chain_verified', True) is not True:
        raise ValueError('Code audit chain verification failed')
    return transport, result


def main():
    scope = EvidenceScope('benchmark', 'local-operator', 'click-20261017')
    principal = EvidencePrincipal('local-benchmark-operator', EvidenceRole.ADMINISTRATOR, scope)
    vault = ReplayEvidence(ROOT / 'vault', vault_id='click-20261017', scope=scope)
    events = vault.inspect(principal, RUN)
    def rows(kind):
        return [e['envelope']['payload'] for e in events if e['envelope']['event_type'] == kind]
    if len(rows('external.cohort_comparison')) != 1:
        raise ValueError('completed comparison required before evidence recovery')
    if rows('external.cohort_public_recovery_planned'):
        raise ValueError('recovery already dispatched; inspect its handle, never silently retry')
    frozen = rows('external.cohort_manifest_frozen')[0]
    verified = {(r['slot'], r['arm']): r for r in rows('external.cohort_descriptors_verified')[-1]['verified']}
    def save(kind, payload):
        return vault.capture(run_id=RUN, kind=kind, principal=principal, payload=payload)
    bridge = Path('benchmarks/code_replay/atmem_bridge.py').read_text()
    transport_command = command()
    transport_command[-1] = transport_command[-1].replace('python3 -c', frozen['build']['python'] + ' -I -c')
    save('external.cohort_public_recovery_planned', {'program': PROGRAM,
        'driver_source': Path(__file__).read_text(), 'bridge_source': bridge,
        'transport': transport_command, 'models_repeated': 0, 'credential_export': False})
    completed = 0
    for stage in rows('external.cohort_staged'):
        for arm, original in stage['cases'].items():
            case = {k: original[k] for k in ('operator', 'atmem_home', 'database', 'scope')}
            if arm != 'native':
                corrected = verified[(stage['slot'], arm)]
                case.update(atmem_home=corrected['atmem_home'], database=corrected['database'])
            identity = {'slot': stage['slot'], 'arm': arm}
            job = {'program': PROGRAM, 'case': case, 'bridge_source': bridge}
            proc = subprocess.run(transport_command, input=json.dumps(job).encode(), capture_output=True, timeout=120)
            receipts = {}
            for name, raw in [('stdout', proc.stdout), ('stderr', proc.stderr)]:
                chunks = []
                for offset in range(0, len(raw), 3_000_000):
                    chunks.append(save('external.cohort_public_recovery_chunk', {**identity, 'stream': name,
                        'offset': offset, 'total_bytes': len(raw), 'sha256': sha256(raw).hexdigest(),
                        'content_base64': base64.b64encode(raw[offset:offset + 3_000_000]).decode()}))
                receipts[name] = {'bytes': len(raw), 'sha256': sha256(raw).hexdigest(), 'receipts': chunks}
            save('external.cohort_public_recovery_transport', {**identity, 'exit_code': proc.returncode, 'streams': receipts})
            if proc.returncode:
                raise RuntimeError('protected evidence transport failed; retained, no automatic retry')
            compressed, result = decode_recovery(proc.stdout)
            completed += 1
            metadata = {**identity, 'recovered_bytes': compressed['bytes'], 'recovered_sha256': compressed['sha256'],
                'public_run_id': result['public_run_id'], 'public_event_count': len(result['public_test_events']),
                'code_audit_events': len(result.get('code_audit_events', [])),
                'code_audit_chain_verified': result.get('code_audit_chain_verified'),
                'streams': receipts, 'cases_recovered': completed}
            save('external.cohort_public_evidence_recovered', metadata)
            print(json.dumps(metadata), flush=True)
    if completed != 30:
        raise RuntimeError('all thirty protected case vaults required')
    save('external.cohort_public_recovery_completed', {'cases_recovered': completed,
        'models_repeated': 0, 'no_case_deleted': True})


if __name__ == '__main__':
    main()
