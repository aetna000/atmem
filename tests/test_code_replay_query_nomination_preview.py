from copy import deepcopy
from hashlib import sha256

import pytest

from benchmarks.code_replay import query_nomination_preview as preview


def reports(monkeypatch):
    source = 'candidate'
    monkeypatch.setattr(preview, 'CANDIDATE', sha256(source.encode()).hexdigest())
    result = {}
    for root in preview.ROOTS:
        kind = 'external.layout_diagnostic_completed' if root == preview.ROOTS[0] else 'external.nomination_diagnostic_completed'
        payload = {'summary': {'identities': 19, 'all_original_packs_reproduced': True,
            'source_vault_opened': False, 'models_repeated': 0, 'private_grades_repeated': 0},
            'cases': [{'identity': str(i), 'stage_run': 'stage-'+str(i), 'baseline_pack': 'original',
                       'candidate_pack': 'counterfactual', 'original_pack_reproduced': True} for i in range(19)]}
        result[root] = [{'envelope': {'event_type': kind, 'payload': payload}}]
    result[preview.ROOTS[-1]].append({'envelope': {'event_type': 'external.nomination_diagnostic_started',
        'payload': {'candidate_source': source, 'candidate_sha256': preview.CANDIDATE}}})
    return source, result


def test_preview_requires_exact_source_and_complete_original_cohort(monkeypatch):
    source, proof = reports(monkeypatch)
    assert preview.static_ready(proof, source)
    with pytest.raises(ValueError): preview.static_ready(proof, source+'changed')
    bad = deepcopy(proof); bad[preview.ROOTS[1]][0]['envelope']['payload']['cases'].pop()
    with pytest.raises(ValueError): preview.static_ready(bad, source)
    bad = deepcopy(proof); bad[preview.ROOTS[1]][0]['envelope']['payload']['cases'][0]['baseline_pack'] = 'different'
    with pytest.raises(ValueError): preview.static_ready(bad, source)


def test_preview_rejects_over_budget_or_model_rerun_static_proofs(monkeypatch):
    source, proof = reports(monkeypatch)
    bad = deepcopy(proof); bad[preview.ROOTS[0]][0]['envelope']['payload']['cases'][0]['candidate_pack'] = 'x'*4097
    with pytest.raises(ValueError): preview.static_ready(bad, source)
    bad = deepcopy(proof); bad[preview.ROOTS[1]][0]['envelope']['payload']['summary']['models_repeated'] = 1
    with pytest.raises(ValueError): preview.static_ready(bad, source)
