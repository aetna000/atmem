"""Owner-only encrypted SWE evidence retention on MEM, including failed setup."""
import argparse
import base64
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

from atmem.core.canonical import canonical_json
from atmem.evidence.crypto import generate_recipient_keypair, generate_signing_keypair
from benchmarks.code_replay.archive import seal
from benchmarks.code_replay.discovery_swebench import evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--root', type=Path, action='append', required=True)
    args = parser.parse_args()
    if not Path('/Volumes/MEM').is_mount() or not args.destination.is_relative_to(Path('/Volumes/MEM')):
        raise ValueError('benchmark-only MEM destination required')
    args.destination.mkdir(parents=True, mode=0o700, exist_ok=False)
    private = Path('/Users/javadtaghia/Library/Application Support/AtMem Benchmarks/discovery-044-swe-recovery-20261020')
    private.mkdir(mode=0o700, exist_ok=False)
    public, secret = generate_recipient_keypair()
    signing_public, signing_secret = generate_signing_keypair()
    keyfile = private / 'recovery.json'
    keyfile.write_text(json.dumps({'recipient_secret': base64.b64encode(secret).decode(),
        'signing_public': base64.b64encode(signing_public).decode()})); keyfile.chmod(0o600)
    rows = []
    for root in args.root:
        if not root.name.startswith('discovery-044-'):
            raise ValueError('exact campaign-owned root required')
        vault, principal = evidence(root)
        for run in ['campaign', 'verified-manifest', 'claude-native', 'claude-cognee', 'claude-atmem',
                    'codex-cognee', 'codex-atmem', 'codex-native']:
            retained = vault.inspect(principal, run)
            if not retained:
                continue
            raw = canonical_json(retained).encode()
            bundle = seal(raw, run_id=run, recipient_public_key=public,
                signing_public_key=signing_public, signing_secret_key=signing_secret)
            name = root.name + '--' + run + '.encrypted.json'
            with (args.destination / name).open('x') as stream:
                json.dump(bundle, stream)
            rows.append({'path': name, 'run_id': run, 'events': len(retained), 'events_sha256': sha256(raw).hexdigest()})
    manifest = args.destination / 'manifest.json'
    manifest.write_text(json.dumps({'runs': rows, 'publication': 'owner-only; evaluator material not uploaded'}, indent=2))
    verifier = ('import json,sys,base64;from pathlib import Path;from hashlib import sha256;'
        'from atmem.evidence.service import EvidenceService;'
        'EvidenceService.__init__=lambda *a,**k:(_ for _ in ()).throw(PermissionError("original vault denied"));'
        'from benchmarks.code_replay.archive import open_archive;'
        'root=Path(sys.argv[1]);key=json.loads(Path(sys.argv[2]).read_text());'
        'rows=json.loads((root/"manifest.json").read_text())["runs"];'
        'checks=[sha256(open_archive(json.loads((root/r["path"]).read_text()),run_id=r["run_id"],'
        'recipient_secret_key=base64.b64decode(key["recipient_secret"]),trusted_signing_public_key=base64.b64decode(key["signing_public"]))).hexdigest()==r["events_sha256"] for r in rows];'
        'assert all(checks);print(json.dumps({"verified_runs":len(checks),"original_vault_access":"denied"}))')
    checked = subprocess.run([sys.executable, '-c', verifier, str(args.destination), str(keyfile)], capture_output=True, text=True, timeout=180)
    if checked.returncode:
        raise RuntimeError('independent private recovery failed: ' + checked.stderr[-1000:])
    (args.destination / 'verification.json').write_text(checked.stdout)
    print(json.dumps({'status': 'archived_verified_owner_only', 'destination': str(args.destination), **json.loads(checked.stdout)}))


if __name__ == '__main__':
    main()
