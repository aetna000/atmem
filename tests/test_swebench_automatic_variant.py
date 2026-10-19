import json
from pathlib import Path
import pytest
from benchmarks.code_replay import swebench_automatic_variant as module


def test_automatic_profile_freezes_delivery_and_does_not_reuse_solver_results(tmp_path, monkeypatch):
    source, target = tmp_path / 'source', tmp_path / 'new-automatic'
    source.mkdir()
    manifest = {'cohort': 'validation', 'selected': [{'instance_id': 'public-task', 'arm_order': ['cognee_structure']}],
                'cognee_runtime': {'pinned': True}, 'context_delivery': 'optional'}
    (source / 'manifest.json').write_text(json.dumps(manifest))
    (source / 'results.json').write_text(json.dumps({'status': 'completed'}))
    calls = []
    class Source:
        def inspect(self, principal, identity):
            if identity == 'pilot':
                return [{'envelope': {'event_type': 'selection.frozen', 'payload': manifest}}]
            return [{'envelope': {'event_type': 'upstream.task', 'payload': {'instance_id': 'public-task'}}}]
    class Target:
        def capture(self, **kwargs):
            calls.append(kwargs)
    monkeypatch.setattr(module, 'vault', lambda root: (Source() if root == source else Target(), object()))
    monkeypatch.setattr(module, 'validate_product_runtime', lambda x: x)
    monkeypatch.setattr(module, 'reuse', lambda a, b: 1)
    result = module.prepare(source, target, {'wheel_sha256': 'pinned'})
    frozen = json.loads((target / 'manifest.json').read_text())
    assert frozen['context_delivery'] == 'automatic' and 'cognee_runtime' not in frozen
    assert frozen['model_graph_tools'] is False
    assert frozen['selected'][0]['arm_order'] == ['no_memory', 'atmem_structure']
    assert result['model_outcomes_reused'] is False
    assert {x['kind'] for x in calls} == {'selection.frozen', 'campaign.additional_protocol', 'upstream.task'}


def test_automatic_profile_refuses_an_incomplete_primary_campaign(tmp_path):
    (tmp_path / 'manifest.json').write_text(json.dumps({'cohort': 'validation'}))
    (tmp_path / 'results.json').write_text(json.dumps({'status': 'running'}))
    with pytest.raises(ValueError, match='complete original'):
        module.prepare(tmp_path, tmp_path / 'new', {})
