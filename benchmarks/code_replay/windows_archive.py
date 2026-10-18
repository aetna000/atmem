"""Segment large evidence snapshots using the existing protected-export framing.

No evidence is dropped, no cryptographic bound is raised, and keys stay internal.
Recovery reads only archive files and supplied internal keys, not the live vault.
"""
import argparse
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import zlib

from atmem.core.canonical import canonical_json
from atmem.evidence.crypto import generate_recipient_keypair, generate_signing_keypair
from benchmarks.code_replay.archive import seal, open_archive
from benchmarks.code_replay.windows_metrics import recover_stream

FORMAT = 'atmem-code-segmented-protected-evidence-v1'
SEGMENT_BYTES = 32_000_000
MAX_RAW_BYTES = 1_024_000_000
MAX_SEGMENTS = 1024


def decompress_exact(packed, expected_size):
    if type(expected_size) is not int or not 1 <= expected_size <= SEGMENT_BYTES:
        raise ValueError('bounded original segment size required')
    decoder = zlib.decompressobj()
    raw = decoder.decompress(packed, expected_size + 1)
    if len(raw) != expected_size or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise ValueError('compressed segment framing differs')
    return raw


def write_exclusive(path, raw):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(raw)
        stream.flush(); os.fsync(stream.fileno())


def export_snapshot(raw, *, run_id, output, key_root, segment_bytes=SEGMENT_BYTES):
    if (not 1 <= len(raw) <= MAX_RAW_BYTES or not 1 <= segment_bytes <= SEGMENT_BYTES
        or (len(raw) + segment_bytes - 1) // segment_bytes > MAX_SEGMENTS):
        raise ValueError('bounded full snapshot required')
    if key_root.resolve().is_relative_to(Path('/Volumes')):
        raise ValueError('private export keys must remain internal')
    if output.exists() or key_root.exists():
        raise ValueError('new export/key directories required; never overwrite')
    key_root.mkdir(mode=0o700, parents=True)
    output.mkdir(mode=0o700, parents=True)
    public, secret = generate_recipient_keypair()
    signing_public, signing_secret = generate_signing_keypair()
    for name, value in [('recipient.public', public), ('recipient.secret', secret),
        ('signing.public', signing_public), ('signing.secret', signing_secret)]:
        write_exclusive(key_root / name, value)
    manifest = {'format': FORMAT, 'run_id': run_id, 'codec': 'independent-zlib-segments',
        'raw_bytes': len(raw), 'raw_sha256': sha256(raw).hexdigest(), 'segments': []}
    for ordinal, offset in enumerate(range(0, len(raw), segment_bytes)):
        part = raw[offset:offset + segment_bytes]
        packed = zlib.compress(part)
        identity = run_id + ':segment:' + str(ordinal)
        bundle = seal(packed, run_id=identity, recipient_public_key=public,
            signing_public_key=signing_public, signing_secret_key=signing_secret)
        encoded = canonical_json(bundle).encode()
        filename = f'part-{ordinal:04d}.encrypted.json'
        write_exclusive(output / filename, encoded)
        manifest['segments'].append({'ordinal': ordinal, 'offset': offset, 'file': filename,
            'run_id': identity, 'raw_bytes': len(part), 'raw_sha256': sha256(part).hexdigest(),
            'packed_bytes': len(packed), 'packed_sha256': sha256(packed).hexdigest(),
            'archive_bytes': len(encoded), 'archive_sha256': sha256(encoded).hexdigest()})
        print(json.dumps({'segments_written': ordinal + 1, 'raw_bytes': offset + len(part)}), flush=True)
    sealed_manifest = seal(canonical_json(manifest).encode(), run_id=run_id + ':manifest',
        recipient_public_key=public, signing_public_key=signing_public, signing_secret_key=signing_secret)
    write_exclusive(output / 'manifest.encrypted.json', canonical_json(sealed_manifest).encode())
    return manifest


def recover_snapshot(*, run_id, output, key_root):
    secret = (key_root / 'recipient.secret').read_bytes()
    signing_public = (key_root / 'signing.public').read_bytes()
    manifest = json.loads(open_archive(json.loads((output / 'manifest.encrypted.json').read_bytes()),
        run_id=run_id + ':manifest', recipient_secret_key=secret, trusted_signing_public_key=signing_public))
    if (manifest['format'] != FORMAT or manifest['run_id'] != run_id
        or manifest['codec'] != 'independent-zlib-segments'
        or type(manifest['raw_bytes']) is not int or not 1 <= manifest['raw_bytes'] <= MAX_RAW_BYTES
        or not 1 <= len(manifest['segments']) <= MAX_SEGMENTS):
        raise ValueError('invalid authenticated snapshot manifest')
    parts, offset = [], 0
    for ordinal, row in enumerate(manifest['segments']):
        if (row['ordinal'] != ordinal or row['offset'] != offset
            or row['file'] != f'part-{ordinal:04d}.encrypted.json'
            or row['run_id'] != run_id + ':segment:' + str(ordinal)):
            raise ValueError('segment ordering or binding differs')
        encoded = (output / row['file']).read_bytes()
        if len(encoded) != row['archive_bytes'] or sha256(encoded).hexdigest() != row['archive_sha256']:
            raise ValueError('encrypted segment bytes differ')
        packed = open_archive(json.loads(encoded), run_id=row['run_id'],
            recipient_secret_key=secret, trusted_signing_public_key=signing_public)
        if len(packed) != row['packed_bytes'] or sha256(packed).hexdigest() != row['packed_sha256']:
            raise ValueError('compressed segment identity differs')
        raw = decompress_exact(packed, row['raw_bytes'])
        if sha256(raw).hexdigest() != row['raw_sha256']:
            raise ValueError('original segment identity differs')
        parts.append(raw); offset += len(raw)
    raw = b''.join(parts)
    if len(raw) != manifest['raw_bytes'] or sha256(raw).hexdigest() != manifest['raw_sha256']:
        raise ValueError('full snapshot identity differs')
    return raw, manifest


def validate_cohort_evidence(events):
    counts = Counter(e['envelope']['event_type'] for e in events)
    for kind in ('cohort_model_result', 'cohort_candidate_capture', 'cohort_private_grade', 'cohort_public_evidence_recovered'):
        if counts['external.' + kind] != 30:
            raise ValueError('all thirty evidence records required: ' + kind)
    for kind in ('cohort_comparison', 'cohort_models_completed', 'cohort_grading_completed', 'cohort_public_recovery_completed'):
        if counts['external.' + kind] != 1:
            raise ValueError('exact terminal evidence required: ' + kind)
    by_id = {e['object_id']: e for e in events}
    verified_streams = 0
    for event in events:
        kind, payload = event['envelope']['event_type'], event['envelope']['payload']
        if kind == 'external.cohort_model_result':
            streams = payload['raw_response_transport']['streams']
        elif kind in {'external.cohort_private_grade', 'external.cohort_public_evidence_recovered'}:
            streams = payload['streams']
        else:
            continue
        for stream in streams.values():
            recover_stream(by_id, stream)
            verified_streams += 1
    return {'events': len(events), 'verified_full_streams': verified_streams,
        'models': counts['external.cohort_model_result'], 'private_grades': counts['external.cohort_private_grade'],
        'public_case_vaults': counts['external.cohort_public_evidence_recovered']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--key-root', type=Path, required=True)
    parser.add_argument('--recover-only', action='store_true')
    args = parser.parse_args()
    from benchmarks.code_replay.windows_execute import ROOT, RUN
    if args.recover_only:
        raw, manifest = recover_snapshot(run_id=RUN, output=args.output, key_root=args.key_root)
        proof = validate_cohort_evidence(json.loads(raw))
        print(json.dumps({**proof, 'raw_bytes': len(raw), 'raw_sha256': manifest['raw_sha256'],
            'segments': len(manifest['segments']), 'source_vault_opened': False}), flush=True)
        return
    from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole, EvidenceOperation
    from benchmarks.code_replay.atmem_bridge import ReplayEvidence
    scope = EvidenceScope('benchmark', 'local-operator', 'click-20261017')
    principal = EvidencePrincipal('local-benchmark-operator', EvidenceRole.ADMINISTRATOR, scope)
    vault = ReplayEvidence(ROOT / 'vault', vault_id='click-20261017', scope=scope)
    target = EvidenceScope(scope.tenant_id, scope.subject_id, scope.workspace_id, RUN)
    principal.authorize(EvidenceOperation.ENCRYPTED_EXPORT, target)
    events = vault.inspect(principal, RUN)
    validate_cohort_evidence(events)
    raw = canonical_json(events).encode()
    manifest = export_snapshot(raw, run_id=RUN, output=args.output, key_root=args.key_root)
    vault.service._record_access(principal, 'encrypted_export', target, True)
    del raw, events
    proc = subprocess.run([sys.executable, '-m', __spec__.name, '--recover-only',
        '--output', str(args.output), '--key-root', str(args.key_root)], capture_output=True, timeout=600)
    result = {'output': str(args.output), 'segments': len(manifest['segments']),
        'raw_sha256': manifest['raw_sha256'], 'raw_bytes': manifest['raw_bytes'],
        'fresh_process_exit': proc.returncode, 'fresh_process_stdout': proc.stdout.decode(errors='replace'),
        'fresh_process_stderr': proc.stderr.decode(errors='replace'), 'no_source_deleted': True}
    vault.capture(run_id=RUN, kind='external.cohort_archive_verified' if proc.returncode == 0 else 'external.cohort_archive_recovery_failed',
        principal=principal, payload=result)
    print(json.dumps(result), flush=True)
    if proc.returncode:
        raise RuntimeError('fresh process recovery failed; all files retained')


if __name__ == '__main__':
    main()
