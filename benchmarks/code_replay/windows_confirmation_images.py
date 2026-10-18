"""Pin and qualify the frozen confirmation images on Windows; zero solver calls."""
import ast
import base64
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess

from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.external_catalog import digest, CONFIRMATION_REPOSITORIES, CONFIRMATION_SEED
from benchmarks.code_replay.external_qualify_worker import CONFIRMATION_BINDINGS, task_binding
from benchmarks.code_replay.external_runtime import command as runtime_command
from benchmarks.code_replay.windows_execute import ROOT
from benchmarks.code_replay.windows_transport import command

PREFLIGHT = Path('/Volumes/MEM/AtMem-Code-Replay-20261017/cross-repository-confirmation-preflight-v1')
RUN = 'external-windows-confirmation-images-v1-20261018'
EVIDENCE_ROOT = ROOT / 'confirmation-v1/vault'

REGISTRY = r'''
import base64,json,subprocess
image=job['image']
process=subprocess.run(['docker','manifest','inspect','--verbose',image],capture_output=True,timeout=60)
print(json.dumps({'exit_code':process.returncode,'stdout_base64':base64.b64encode(process.stdout).decode(),
 'stderr_base64':base64.b64encode(process.stderr).decode()}))
'''


def bound_descriptor(raw):
    value = json.loads(raw)
    if type(value) is not dict or len(raw) > 2_000_000:
        raise ValueError('bounded single-image descriptor required')
    descriptor = value['Descriptor']
    manifest = base64.b64decode(value['Raw'], validate=True)
    if descriptor['platform'] != {'architecture': 'amd64', 'os': 'linux'}:
        raise ValueError('native amd64 manifest required')
    if descriptor['digest'] != 'sha256:' + sha256(manifest).hexdigest() or descriptor['size'] != len(manifest):
        raise ValueError('registry manifest digest/size differs')
    decoded = json.loads(manifest)
    if decoded != value['SchemaV2Manifest'] or decoded['schemaVersion'] != 2:
        raise ValueError('manifest representation differs')
    configuration = decoded['config']['digest']
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', configuration):
        raise ValueError('exact image configuration digest required')
    return {'digest': descriptor['digest'], 'configuration_digest': configuration,
        'platform': descriptor['platform'], 'compressed_layer_bytes': sum(layer['size'] for layer in decoded['layers'])}


def validate_preflight(selection, metadata):
    if (selection['seed'] != CONFIRMATION_SEED or selection['per_repo'] != 4
        or set(selection['ordered_candidate_pools']) != set(CONFIRMATION_REPOSITORIES)
        or len(selection['selected']) != 20 or metadata['selection_sha256'] != digest(selection)
        or {r['instance_id'] for r in selection['selected']} != set(CONFIRMATION_BINDINGS)
        or len(metadata['reports']) != 20
        or {r['instance_id'] for r in metadata['reports']} != set(CONFIRMATION_BINDINGS)):
        raise ValueError('exact prospectively frozen confirmation pool required')
    for row in metadata['reports']:
        task = row['metadata']
        if row['status'] != 'metadata_verified_environment_not_executed':
            raise ValueError('complete metadata qualification required')
        if task_binding(task['instance_id'], task['base_commit'])[1] != task['log_parser']:
            raise ValueError('confirmation parser differs')


def runtime_evidence_qualifies(record, descriptor):
    """Interpret retained bytes without pulling an image or repeating a control.

    Docker's classic store exposes the config digest as image Id; the tested
    Docker 29 containerd store exposes the manifest digest. Both are verified
    content identities in the same pinned registry manifest, not mutable tags.
    """
    if record.get('transport_exit') != 0:
        return False
    raw = base64.b64decode(record['transport_stdout_base64'], validate=True)
    result = json.loads(raw)
    if result != record.get('result'):
        raise ValueError('runtime metadata differs from retained raw transport')
    runtime = result.get('runtime', {})
    output = base64.b64decode(runtime.get('stdout_base64', ''), validate=True).decode(errors='replace')
    image = runtime.get('image', {})
    return bool(result['pull']['passed'] and not result['pull'].get('reason')
        and runtime.get('exit_code') == 0
        and re.fullmatch(r'x86_64\nPYTHON 3\.\d+\.\d+ linux\n', output)
        and image.get('Id') in {descriptor['digest'], descriptor['configuration_digest']}
        and image.get('Architecture') == 'amd64' and image.get('Os') == 'linux')


def runtime_program():
    source = Path(__file__).with_name('external_runtime.py').read_text()
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == 'guarded_pull')
    pull = ast.get_source_segment(source, node).replace('shutil.disk_usage("/private/tmp").free',
        'min(shutil.disk_usage("/tmp").free,shutil.disk_usage("/mnt/c").free)')
    pull = pull.replace('tempfile.TemporaryFile()', 'tempfile.TemporaryFile(dir="/dev/shm")')
    return 'import base64,json,shutil,signal,subprocess,tempfile,time\n' + pull + r'''
result={'pull':guarded_pull(job['image']),'solver_calls':0}
if result['pull']['passed']:
 process=subprocess.run(job['runtime_command'],capture_output=True,timeout=30)
 inspected=subprocess.run(['docker','image','inspect',job['image']],capture_output=True,timeout=20,check=True)
 actual=json.loads(inspected.stdout)[0]
 result['runtime']={'exit_code':process.returncode,'stdout_base64':base64.b64encode(process.stdout).decode(),
  'stderr_base64':base64.b64encode(process.stderr).decode(),
  'image':{k:actual[k] for k in ('Id','Architecture','Os','Size')}}
result['free_physical_windows_bytes']=shutil.disk_usage('/mnt/c').free
print(json.dumps(result))
'''


def main():
    from uuid import uuid4
    selection = json.loads((PREFLIGHT / 'selection.json').read_bytes())
    metadata = json.loads((PREFLIGHT / 'metadata.json').read_bytes())
    validate_preflight(selection, metadata)
    scope = EvidenceScope('benchmark', 'local-operator', 'click-20261017')
    principal = EvidencePrincipal('local-benchmark-operator', EvidenceRole.ADMINISTRATOR, scope)
    vault = ReplayEvidence(EVIDENCE_ROOT, vault_id='confirmation-v1', scope=scope)
    if vault.inspect(principal, RUN):
        raise ValueError('image qualification already dispatched; no implicit retries')
    def save(kind, payload):
        return vault.capture(run_id=RUN, kind=kind, principal=principal, payload=payload)
    program = runtime_program()
    save('external.confirmation_images_planned', {'selection': selection, 'metadata': metadata,
        'driver_source': Path(__file__).read_text(), 'registry_program': REGISTRY,
        'runtime_program': program, 'protocol': Path('specs/042-atmem-code/windows-confirmation-v1.md').read_text(),
        'transport': command(), 'solver_calls': 0, 'automatic_replacement': False})
    registry = []
    for row in metadata['reports']:
        task = row['metadata']; identity = task['instance_id']
        proc = subprocess.run(command(), input=json.dumps({'program': REGISTRY, 'image': task['image']}).encode(), capture_output=True, timeout=75)
        record = {'instance_id': identity, 'image_tag': task['image'], 'transport_exit': proc.returncode,
            'transport_stdout_base64': base64.b64encode(proc.stdout).decode(),
            'transport_stderr_base64': base64.b64encode(proc.stderr).decode()}
        try:
            if proc.returncode:
                raise RuntimeError('registry transport failed')
            result = json.loads(proc.stdout)
            if result['exit_code']:
                raise RuntimeError('registry inspection failed')
            descriptor = bound_descriptor(base64.b64decode(result['stdout_base64'], validate=True))
            record.update(descriptor=descriptor, image=task['image'].rsplit(':', 1)[0] + '@' + descriptor['digest'])
        except Exception as exc:
            record['failure'] = type(exc).__name__ + ': ' + str(exc)
        registry.append(record)
        save('external.confirmation_registry_descriptor', record)
        print(json.dumps({'instance_id': identity, 'phase': 'registry', 'passed': 'descriptor' in record}), flush=True)
    save('external.confirmation_registry_completed', {'rows': registry, 'solver_calls': 0})
    qualified = 0
    for row in registry:
        if 'descriptor' not in row:
            continue
        identity = row['instance_id']; name = 'atmem-runtime-control-' + uuid4().hex
        job = {'program': program, 'image': row['image'], 'runtime_command': runtime_command(row['image'], name)}
        save('external.confirmation_runtime_dispatch', {'instance_id': identity, 'job': job})
        proc = subprocess.run(command(), input=json.dumps(job).encode(), capture_output=True, timeout=240)
        record = {'instance_id': identity, 'image': row['image'], 'transport_exit': proc.returncode,
            'transport_stdout_base64': base64.b64encode(proc.stdout).decode(),
            'transport_stderr_base64': base64.b64encode(proc.stderr).decode(), 'qualified': False}
        if proc.returncode == 0:
            result = json.loads(proc.stdout); record['result'] = result
            runtime = result.get('runtime', {})
            output = base64.b64decode(runtime.get('stdout_base64', '')).decode(errors='replace')
            record['qualified'] = bool(result['pull']['passed'] and runtime.get('exit_code') == 0
                and re.fullmatch(r'x86_64\nPYTHON 3\.\d+\.\d+ linux\n', output)
                and runtime.get('image', {}).get('Id') == row['descriptor']['configuration_digest']
                and runtime.get('image', {}).get('Architecture') == 'amd64')
        save('external.confirmation_runtime_result', record)
        qualified += int(record['qualified'])
        print(json.dumps({'instance_id': identity, 'phase': 'runtime', 'qualified': record['qualified'],
            'reason': record.get('result', {}).get('pull', {}).get('reason')}), flush=True)
    save('external.confirmation_images_completed', {'selected': 20, 'runtime_qualified': qualified,
        'solver_calls': 0, 'task_environment_qualified': False})


if __name__ == '__main__':
    main()
