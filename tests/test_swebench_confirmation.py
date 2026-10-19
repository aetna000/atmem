from copy import deepcopy
from hashlib import sha256
import json
import pytest
from tools.run_swebench_confirmation import validate_selection
from benchmarks.code_replay.swebench_selection import score
from tests.test_swebench_selection import example


def test_confirmation_requires_unchanged_validation_runtime_and_receipts(tmp_path):
    manifest, result = example()
    manifest.update(product_runtime={'wheel_sha256': 'pinned'}, context_delivery='automatic', model_graph_tools=False)
    m, r = json.dumps(manifest).encode(), json.dumps(result).encode()
    (tmp_path / 'manifest.json').write_bytes(m)
    (tmp_path / 'results.json').write_bytes(r)
    chosen = {'campaign': str(tmp_path), 'manifest_sha256': sha256(m).hexdigest(), 'results_sha256': sha256(r).hexdigest(),
        'score': score(manifest, result), 'product_runtime': manifest['product_runtime'],
        'context_delivery': 'automatic', 'model_graph_tools': False}
    receipt = {'format': 'atmem-validation-profile-selection-v1', 'confirmation_scores_consulted': False,
               'candidates': [chosen], 'selected': chosen}
    assert validate_selection(receipt) == chosen
    for field, value in [('product_runtime', {'wheel_sha256': 'replacement'}), ('context_delivery', 'optional'),
                         ('model_graph_tools', True)]:
        bad = deepcopy(receipt)
        bad['selected'][field] = value
        with pytest.raises(ValueError):
            validate_selection(bad)
    (tmp_path / 'results.json').write_bytes(r + b'\n')
    with pytest.raises(ValueError, match='changed after selection'):
        validate_selection(receipt)


def test_normal_cli_exit_does_not_promote_a_stopped_campaign(tmp_path):
    from tools.run_swebench_confirmation import require_completed
    for status in ('running', 'stopped'):
        (tmp_path / 'results.json').write_text(json.dumps({'status': status}))
        with pytest.raises(RuntimeError, match='not completed'):
            require_completed(tmp_path)
    (tmp_path / 'results.json').write_text(json.dumps({'status': 'completed'}))
    require_completed(tmp_path)
