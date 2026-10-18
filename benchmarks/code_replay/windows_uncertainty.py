"""Paired cluster sensitivity, preserving repeats and all complete selected cells."""
from hashlib import sha256
import json
from pathlib import Path
import random

from atmem.core.canonical import canonical_json
from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.windows_execute import ROOT, RUN as COHORT_RUN
from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT

RUN = 'external-windows-validation-uncertainty-v1-20261018'
SEED = 'atmem-windows-validation-cluster-audit-20261018-v1'


def point(pairs):
    native = sum(a['usage']['input_tokens'] for a, b in pairs)
    candidate = sum(b['usage']['input_tokens'] for a, b in pairs)
    if native <= 0 or not pairs:
        raise ValueError('positive complete native denominator required')
    a = sum(row['quality']['task_pass'] for row, other in pairs)
    b = sum(row['quality']['task_pass'] for other, row in pairs)
    return {'attempts_per_arm': len(pairs), 'native_input_tokens': native,
        'candidate_input_tokens': candidate, 'input_reduction_percent': 100 * (native - candidate) / native,
        'native_task_passes': a, 'candidate_task_passes': b,
        'task_pass_rate_difference': (b - a) / len(pairs)}


def percentile(values, fraction):
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lower = int(index); upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def paired_uncertainty(rows, *, candidate_arm, required_pairs, resamples=10000, seed=SEED):
    if candidate_arm == 'native':
        raise ValueError('candidate must be distinct from native control')
    if type(resamples) is not int or not 100 <= resamples <= 100000:
        raise ValueError('bounded prospective resample count required')
    def key(row):
        return row['instance_id'], row['repeat'], row['slot']
    controls = [r for r in rows if r['arm'] == 'native']
    candidates = [r for r in rows if r['arm'] == candidate_arm]
    a, b = {key(r): r for r in controls}, {key(r): r for r in candidates}
    if (len(controls) != len(a) or len(candidates) != len(b) or len(a) != required_pairs
        or a.keys() != b.keys()):
        raise ValueError('identical complete paired cells required; no exclusions')
    pairs = [(a[k], b[k]) for k in sorted(a)]
    for left, right in pairs:
        for row in (left, right):
            usage, quality = row.get('usage'), row.get('quality', {})
            if (usage is None or type(usage.get('input_tokens')) is not int or usage['input_tokens'] < 0
                or quality.get('grade_available') is not True or type(quality.get('task_pass')) is not bool):
                raise ValueError('complete usage and private grade required before uncertainty analysis')
    output = {'candidate_arm': candidate_arm, 'point': point(pairs), 'resamples': resamples, 'seed': seed,
        'analysis_scope': 'paired cluster percentile sensitivity; not proof of equivalence, causality or confirmation',
        'paired_task_outcomes': {
            'both_pass': sum(x['quality']['task_pass'] and y['quality']['task_pass'] for x, y in pairs),
            'native_only': sum(x['quality']['task_pass'] and not y['quality']['task_pass'] for x, y in pairs),
            'candidate_only': sum(not x['quality']['task_pass'] and y['quality']['task_pass'] for x, y in pairs),
            'neither_pass': sum(not x['quality']['task_pass'] and not y['quality']['task_pass'] for x, y in pairs)},
        'clustered': {}}
    for kind in ('issue', 'repository'):
        groups = {}
        for pair in pairs:
            identity = pair[0]['instance_id']
            cluster = identity if kind == 'issue' else identity.rsplit('-', 1)[0]
            groups.setdefault(cluster, []).append(pair)
        units = sorted(groups)
        if len(units) < 2:
            raise ValueError('at least two declared clusters required')
        rng = random.Random(int.from_bytes(sha256((seed + ':' + kind).encode()).digest(), 'big'))
        samples = []
        for _ in range(resamples):
            chosen = rng.choices(units, k=len(units))
            samples.append(point([pair for unit in chosen for pair in groups[unit]]))
        reduction = [r['input_reduction_percent'] for r in samples]
        quality = [r['task_pass_rate_difference'] for r in samples]
        output['clustered'][kind] = {'clusters': len(units),
            'input_reduction_percent_interval_95': [percentile(reduction, .025), percentile(reduction, .975)],
            'task_pass_rate_difference_interval_95': [percentile(quality, .025), percentile(quality, .975)],
            'degenerate_task_pass_interval': min(quality) == max(quality),
            'small_cluster_warning': len(units) < 10,
            'leave_one_cluster_out': [{'omitted': unit, **point([p for other in units if other != unit for p in groups[other]])}
                for unit in units]}
    return output


def main():
    scope = EvidenceScope('benchmark', 'local-operator', 'click-20261017')
    principal = EvidencePrincipal('local-benchmark-operator', EvidenceRole.ADMINISTRATOR, scope)
    vault = ReplayEvidence(EVIDENCE_ROOT, vault_id='confirmation-v1', scope=scope)
    if vault.inspect(principal, RUN):
        raise ValueError('sensitivity analysis already retained; do not resample until favorable')
    original = ReplayEvidence(ROOT / 'vault', vault_id='click-20261017', scope=scope)
    source = next(e for e in original.inspect(principal, COHORT_RUN) if e['envelope']['event_type'] == 'external.cohort_comparison')
    comparison = source['envelope']['payload']
    vault.capture(run_id=RUN, kind='external.validation_uncertainty_planned', principal=principal,
        payload={'driver_source': Path(__file__).read_text(), 'input_comparison': comparison,
            'source_object_id': source['object_id'],
            'source_payload_sha256': sha256(canonical_json(comparison).encode()).hexdigest(),
            'seed': SEED, 'resamples': 10000, 'candidate_arm': 'tools', 'required_pairs': 10,
            'changes_frozen_candidate_or_acceptance_gate': False})
    result = paired_uncertainty(comparison['rows'], candidate_arm='tools', required_pairs=10)
    vault.capture(run_id=RUN, kind='external.validation_uncertainty_result', principal=principal, payload=result)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
