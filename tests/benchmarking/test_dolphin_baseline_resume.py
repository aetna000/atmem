"""Qualification-resume bookkeeping; fixtures are not benchmark/training data."""
from pathlib import Path
import json
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def test_adoption_preserves_prior_verified_archive_chain(monkeypatch, tmp_path):
    from benchmarks.dolphinbench import baseline
    from benchmarks.dolphinbench.driver import private_json
    # The real helper deliberately limits operations to the external run root.
    monkeypatch.setattr(baseline.Path, 'relative_to', lambda self, other: self)
    source, target = tmp_path / 'source', tmp_path / 'target'
    identity = {'wheel_sha256': 'fixture-wheel', 'corpus_digest': 'fixture-corpus'}
    private_json(source / 'run.json', {'configuration': {'campaign': identity}})
    paths = ['ingestion/morgan/000001.json', 'native/ingestion/morgan/000001/product-observe.json']
    for path in paths:
        private_json(source / path, {'fixture': True})
    private_json(source / 'checkpoints/morgan.json', {'frozen': True})
    private_json(source / 'costs/ingestion.json', {'total_cost_usd': 0})
    private_json(source / 'archive-index.json', {'files': {p: 'fixture-sha' for p in paths},
        'verified_batches': [{'path': 'source-cloud'}]})
    private_json(target / 'archive-index.json', {'files': {'run.json': 'prior-run-sha'},
        'verified_batches': [{'path': 'target-cloud'}]})
    verified = []
    adapter = SimpleNamespace(campaign_identity=identity,
        verify_checkpoint=lambda persona, checkpoint: verified.append((persona, checkpoint)))
    baseline.adopt(source, target, {'morgan': {'sessions': [{'id': '000001'}]}}, adapter)
    index = json.loads((target / 'archive-index.json').read_text())
    assert index['verified_batches'] == [{'path': 'source-cloud'}, {'path': 'target-cloud'}]
    assert set(index['files']) == set(paths) | {'run.json'}
    assert verified == [('morgan', {'frozen': True})]
    assert (target / 'repairs/pre-adoption-archive-index.json').exists()
    assert (source / paths[0]).stat().st_ino == (target / paths[0]).stat().st_ino
