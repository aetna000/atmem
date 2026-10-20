"""Retain public base-commit/tree metadata for the complete original pool."""
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess

from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.windows_execute import ROOT


PREFLIGHT = Path('/Volumes/MEM/AtMem-Code-Replay-20261017/cross-repository-confirmation-eligibility-v2')
TARGET = Path('/Volumes/MEM/AtMem-Code-Replay-20261017/confirmation-public-git-v1')
RUN = 'external-confirmation-public-git-v1-20261018'


def public_path(repo, kind, identity):
    if (repo not in {'pallets/flask', 'mwaskom/seaborn', 'pydata/xarray',
                     'pylint-dev/pylint', 'pyvista/pyvista'}
        or kind not in {'commits', 'trees'} or re.fullmatch('[0-9a-f]{40}', identity) is None):
        raise ValueError('allowlisted public Git object endpoint required')
    return 'repos/' + repo + '/git/' + kind + '/' + identity + ('?recursive=1' if kind == 'trees' else '')


def fetch(repo, base):
    replies = {}
    for kind, identity in [('commits', base), ('trees', None)]:
        if identity is None:
            identity = replies['commits']['parsed']['tree']['sha']
        endpoint = public_path(repo, kind, identity)
        proc = subprocess.run(['gh', 'api', endpoint], capture_output=True, timeout=45)
        if proc.returncode or len(proc.stdout) > 16_000_000:
            raise ValueError('public object fetch failed or exceeded byte cap')
        value = json.loads(proc.stdout)
        if value.get('sha') != identity:
            raise ValueError('public object identity mismatch')
        if kind == 'trees' and (value.get('truncated') is not False
                                or not isinstance(value.get('tree'), list)
                                or len(value['tree']) > 20_000):
            raise ValueError('complete bounded recursive tree required')
        replies[kind] = {'endpoint': endpoint, 'raw_base64': base64.b64encode(proc.stdout).decode(),
                         'sha256': sha256(proc.stdout).hexdigest(), 'parsed': value}
    return replies


def main():
    selection_raw = (PREFLIGHT / 'selection.json').read_bytes()
    selection = json.loads(selection_raw)
    metadata = json.loads((PREFLIGHT / 'metadata.json').read_bytes())
    rows = {r['instance_id']: r for r in metadata['reports']}
    selected = selection['selected']
    if len(selected) != 40 or len(rows) != 40 or {r['instance_id'] for r in selected} != set(rows):
        raise ValueError('complete original forty-candidate pool required')
    scope = EvidenceScope('benchmark', 'local-operator', 'click-20261017')
    principal = EvidencePrincipal('local-benchmark-operator', EvidenceRole.ADMINISTRATOR, scope)
    vault = ReplayEvidence(ROOT / 'public-git-v1/vault', vault_id='public-git-v1', scope=scope)
    if vault.inspect(principal, RUN):
        raise ValueError('public metadata run exists; inspect original process, never restart')
    TARGET.mkdir(mode=0o700, exist_ok=False)
    def save(kind, payload):
        vault.capture(run_id=RUN, kind=kind, principal=principal, payload=payload)
    save('external.public_git_planned', {'selection_sha256': sha256(selection_raw).hexdigest(),
        'identities': [r['instance_id'] for r in selected], 'driver_source': Path(__file__).read_text(),
        'endpoints': 'public base commit and recursive tree only', 'model_calls': 0,
        'gold_test_hints_opened': False, 'max_workers': 4})
    results = []
    def one(item):
        identity = item['instance_id']; meta = rows[identity]['metadata']
        if meta['repo'] != item['repo']:
            raise ValueError('public repository differs from selection')
        try:
            objects = fetch(item['repo'], meta['base_commit'])
            payload = {'instance_id': identity, 'repo': item['repo'],
                       'base_commit': meta['base_commit'], 'objects': objects, 'qualified': True}
        except Exception as exc:
            payload = {'instance_id': identity, 'qualified': False,
                       'failure': type(exc).__name__ + ': ' + str(exc)}
        return payload
    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(one, item) for item in selected]):
            payload = future.result()
            raw = json.dumps(payload, sort_keys=True).encode()
            with (TARGET / (payload['instance_id'] + '.json')).open('xb') as output:
                output.write(raw)
            save('external.public_git_result', payload)
            result = {'instance_id': payload['instance_id'], 'qualified': payload['qualified'],
                      'bytes': len(raw), 'sha256': sha256(raw).hexdigest()}
            results.append(result)
            print(json.dumps(result), flush=True)
    summary = {'original_candidates': 40, 'results': sorted(results, key=lambda r:r['instance_id']),
               'model_calls': 0, 'gold_test_hints_opened': False}
    with (TARGET / 'manifest.json').open('x') as output:
        json.dump(summary, output, sort_keys=True)
    save('external.public_git_completed', summary)
    print(json.dumps({'completed': len(results), 'qualified': sum(r['qualified'] for r in results)}), flush=True)


if __name__ == '__main__':
    main()
