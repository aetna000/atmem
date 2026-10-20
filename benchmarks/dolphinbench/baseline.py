"""Adopt an explicitly identified, already-frozen history baseline, never task outputs."""
import hashlib
import json
import os
from pathlib import Path

from .gateway import save_new


def adopt(source, destination, release, adapter):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    source.relative_to(Path('/Volumes/AtMemDolphin'))
    assert source != destination
    prior = json.loads((source / 'run.json').read_text())['configuration']['campaign']
    assert prior['wheel_sha256'] == adapter.campaign_identity['wheel_sha256']
    assert prior['corpus_digest'] == adapter.campaign_identity['corpus_digest']
    previous_archive = json.loads((source / 'archive-index.json').read_text())
    adopted = {}
    for persona, data in release.items():
        checkpoint = json.loads((source / 'checkpoints' / (persona + '.json')).read_text())
        adapter.verify_checkpoint(persona, checkpoint)
        for spec in data['sessions']:
            for relative in (f'ingestion/{persona}/{spec["id"]}.json',
                             f'native/ingestion/{persona}/{spec["id"]}/product-observe.json'):
                assert relative in previous_archive['files'], 'Baseline input is not cloud-verified'
                original, target = source / relative, destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                os.link(original, target)
                assert original.stat().st_ino == target.stat().st_ino
                adopted[relative] = previous_archive['files'][relative]
        save_new(destination / 'checkpoints' / (persona + '.json'), checkpoint)
    cost = json.loads((source / 'costs/ingestion.json').read_text())
    assert cost['total_cost_usd'] == 0
    save_new(destination / 'costs/ingestion.json', cost)
    index_path = destination / 'archive-index.json'
    target_archive = json.loads(index_path.read_text()) if index_path.exists() else {'files': {}, 'verified_batches': []}
    # A qualification-only failure may already have archived run metadata.
    # Retain that verified recovery chain while adopting source-only artifacts.
    if index_path.exists():
        save_new(destination / 'repairs/pre-adoption-archive-index.json', target_archive)
    from .driver import private_json
    private_json(index_path, {'files': {**target_archive['files'], **adopted},
        'verified_batches': previous_archive['verified_batches'] + target_archive['verified_batches'],
        'adopted_prefixes': ['ingestion/', 'native/ingestion/'], 'baseline_origin': str(source)})
    save_new(destination / 'repairs/frozen-baseline-adoption.json', {
        'source_run': str(source), 'original_manifest_sha256': hashlib.sha256((source / 'run.json').read_bytes()).hexdigest(),
        'histories': sum(len(data['sessions']) for data in release.values()),
        'source_records_reused_without_regeneration': True, 'task_outputs_adopted': False,
        'frozen_product_checkpoints_verified': True,
        'source_cost_and_ingestion_durations_inherited_not_independent_rerun': True})
