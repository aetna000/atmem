import json
import pytest
from benchmarks.code_replay import swebench_compact_variant as module


def test_fresh_compact_profile_freezes_all_reused_tasks_and_no_old_model_outcomes(tmp_path, monkeypatch):
    source, target = tmp_path / 'original', tmp_path / 'new'
    source.mkdir()
    manifest = {'cohort': 'validation', 'selected': [{'instance_id': str(i), 'arm_order': ['cognee_structure']}
                                                   for i in range(5)], 'cognee_runtime': {'old': True}}
    (source / 'manifest.json').write_text(json.dumps(manifest))
    (source / 'results.json').write_text(json.dumps({'status': 'completed'}))
    events = []
    class Original:
        def inspect(self, principal, identity):
            if identity == 'pilot':
                return [{'envelope': {'event_type': 'selection.frozen', 'payload': manifest}}]
            return [{'envelope': {'event_type': 'upstream.task', 'payload': {'instance_id': identity}}}]
    class Target:
        def capture(self, **kwargs):
            events.append(kwargs)
    monkeypatch.setattr(module, 'vault', lambda root: (Original() if root == source else Target(), object()))
    monkeypatch.setattr(module, 'validate_product_runtime', lambda value: value)
    monkeypatch.setattr(module, 'reuse', lambda old, new: 5)
    result = module.prepare(source, target, {'wheel_sha256': 'pinned'})
    frozen = json.loads((target / 'manifest.json').read_text())
    assert frozen['atmem_tool_profile'] == 'compact' and frozen['context_delivery'] == 'optional'
    assert frozen['model_graph_tools'] is True and 'cognee_runtime' not in frozen
    assert len(frozen['selected']) == 5 and result['held_out'] is False
    assert result['model_outcomes_reused'] is False
    assert frozen['selected'][0]['arm_order'] == ['no_memory', 'atmem_structure']
    assert frozen['selected'][1]['arm_order'] == ['atmem_structure', 'no_memory']
    assert len([event for event in events if event['kind'] == 'upstream.task']) == 5


def test_incomplete_original_is_not_reused(tmp_path):
    (tmp_path / 'manifest.json').write_text(json.dumps({'cohort': 'validation'}))
    (tmp_path / 'results.json').write_text(json.dumps({'status': 'running'}))
    with pytest.raises(ValueError, match='complete original'):
        module.prepare(tmp_path, tmp_path / 'new', {})
