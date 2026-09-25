"""Compatibility gate using a separately installed published AtMem artifact."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--old-package', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    root = args.output.resolve()
    env = {**os.environ, 'PYTHON_DOTENV_DISABLED': '1', 'ATMEM_HOME': str(root / 'home')}
    common = """
from pathlib import Path
from atmem.evidence.service import EvidenceService
v = EvidenceService(Path(sys.argv[2]) / 'vault', vault_id='upgrade')
"""
    create = "import sys; sys.path.insert(0, sys.argv[1]);\n" + common + """
with v._store() as store:
    store.append({'record_type':'upgrade_fixture','text':'published-original-evidence'})
    assert store._conn.execute('SELECT format_version FROM vault_meta').fetchone()[0] == 2
print('published-schema-2-created')
"""
    old = subprocess.run([sys.executable, '-I', '-c', create, str(args.old_package.resolve()), str(root)],
                         env=env, cwd=root, text=True, capture_output=True)
    if old.returncode:
        raise RuntimeError(old.stderr)
    from atmem.evidence.service import EvidenceService
    from atmem.evidence import EvidencePrincipal, EvidenceRole, EvidenceScope
    from atmem.continuity.service import ContinuityService
    os.environ.update(env)
    vault = EvidenceService(root / 'vault', vault_id='upgrade')
    with vault._store() as store:
        if not any(doc.get('text') == 'published-original-evidence' for doc in store.documents()):
            raise ValueError('published evidence lost on opening')
        if store._conn.execute('SELECT format_version FROM vault_meta').fetchone()[0] != 2:
            raise ValueError('opening changed schema before opt-in')
    owner = EvidencePrincipal('owner', EvidenceRole.EVIDENCE_COLLECTOR, EvidenceScope('local', 'student'))
    workflow = ContinuityService(vault).create(owner, 'upgrade-proof', [{'name': 'publish', 'tool': 'publish'}])
    with vault._store() as store:
        if store._conn.execute('SELECT format_version FROM vault_meta').fetchone()[0] != 3:
            raise ValueError('continuity did not advance schema')
        if not any(doc.get('text') == 'published-original-evidence' for doc in store.documents()):
            raise ValueError('published evidence lost during continuity upgrade')
    read = "import sys; sys.path.insert(0, sys.argv[1]);\n" + common + "\nwith v._store() as store: list(store.documents())\n"
    downgrade = subprocess.run([sys.executable, '-I', '-c', read, str(args.old_package.resolve()), str(root)],
                              env=env, cwd=root, text=True, capture_output=True)
    if downgrade.returncode == 0 or 'unsupported encrypted evidence vault version' not in downgrade.stderr:
        raise ValueError('old reader did not explicitly refuse upgraded schema')
    record = next(args.old_package.glob('atmem-*.dist-info/RECORD'))
    report = {'passed': True, 'old_distribution': record.parent.name, 'old_record_sha256': sha256(record.read_bytes()).hexdigest(),
        'old_evidence_preserved': True, 'normal_open_preserves_schema_2': True,
        'continuity_opt_in_schema': 3, 'downgrade_refused': True, 'new_workflow_disabled': workflow['enabled'] is False}
    (root / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
