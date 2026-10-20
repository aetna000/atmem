"""Pin official Verified identities without displaying issue/gold fields.

Full evaluator parquet stays in encrypted AtMem evidence, not solver files.
Only identity/source metadata and partition membership are publicly emitted.
"""
import argparse
import base64
from hashlib import sha256
import io
import json
from pathlib import Path
import urllib.request

DATASET = 'SWE-bench/SWE-bench_Verified'
REVISION = '78f471bf655a3137b2e8a75af1501690ec009ec3'
SEED = 'atmem-discovery-044-verified-20261020-v1'
# Repo-level conservative exclusions: earlier AtMem tuning, plus the official
# dataset card examples opened during resource research. Not a clean-room claim.
EXPOSED_REPOS = {'django/django', 'sympy/sympy', 'matplotlib/matplotlib',
    'scikit-learn/scikit-learn', 'sphinx-doc/sphinx', 'astropy/astropy'}


def partition(rows):
    ids = [row['instance_id'] for row in rows]
    if len(set(ids)) != len(ids) or len(ids) != 500:
        raise ValueError('expected complete unique 500-row Verified target')
    eligible = [r for r in rows if r['repo'] not in EXPOSED_REPOS]
    eligible.sort(key=lambda r: sha256((SEED + '\0' + r['instance_id']).encode()).hexdigest())
    pilot_ids = {r['instance_id'] for r in eligible[:5]}
    return [{**row, 'partition': 'prior_repository_exposure' if row['repo'] in EXPOSED_REPOS else
        'qualification' if row['instance_id'] in pilot_ids else 'confirmation'} for row in rows]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.evidence_root.exists() or args.output.exists():
        raise ValueError('new manifest/evidence targets required')
    url = f'https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/data/test-00000-of-00001.parquet'
    with urllib.request.urlopen(url, timeout=90) as response:
        raw = response.read(20_000_001)
    if len(raw) > 20_000_000:
        raise ValueError('upstream parquet exceeds declared bound')
    import pyarrow.parquet as pq
    metadata = pq.read_table(io.BytesIO(raw), columns=['instance_id', 'repo', 'base_commit', 'image']).to_pylist()
    selected = partition(metadata)
    from collections import Counter
    manifest = {'format': 'atmem-discovery-verified-manifest-v1', 'dataset': DATASET, 'revision': REVISION,
        'split': 'test', 'full_target_count': 500, 'parquet_sha256': sha256(raw).hexdigest(), 'seed': SEED,
        'license': 'No license declared in the fetched HF card metadata; upstream repository licenses apply. Full data redistribution requires review.',
        'exposure_policy': 'Earlier tuning repositories and opened dataset-card examples excluded from confirmation.',
        'exposed_repositories': sorted(EXPOSED_REPOS), 'partition_counts': dict(Counter(r['partition'] for r in selected)),
        'scoring_hosts': ['claude', 'codex', 'copilot'], 'backends': ['native', 'cognee', 'atmem'],
        'full_target_cells': 4500, 'rental_cap_usd': 6, 'rows': selected,
        'execution': 'not_started; requires Click, grader/reference, quota, resource and cost gates'}
    from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
    from benchmarks.code_replay.atmem_bridge import ReplayEvidence
    scope = EvidenceScope('benchmark', 'local-operator', 'discovery-044')
    principal = EvidencePrincipal('discovery-044-operator', EvidenceRole.ADMINISTRATOR, scope)
    evidence = ReplayEvidence(args.evidence_root / 'vault', vault_id='discovery-044', scope=scope)
    for index, start in enumerate(range(0, len(raw), 2_000_000)):
        evidence.capture(run_id='verified-manifest', kind='discovery.evaluator_parquet_chunk', principal=principal,
            payload={'index': index, 'source_url': url, 'data_base64': base64.b64encode(raw[start:start+2_000_000]).decode()})
    evidence.capture(run_id='verified-manifest', kind='discovery.verified_manifest', principal=principal, payload=manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Generated machine manifest, not hand-authored research labels or code.
    with args.output.open('x') as stream:
        json.dump(manifest, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k: manifest[k] for k in ('dataset', 'revision', 'full_target_count', 'full_target_cells', 'partition_counts', 'execution')}))


if __name__ == '__main__':
    main()
