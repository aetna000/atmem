"""Freeze a separate automatic-AtMem validation campaign before its inference.

The original three-way optional-tool experiment is preserved. This profile
tests the actual product source pack in the model prompt, not forced tool uptake.
"""
import argparse
import json
import os
from pathlib import Path

from benchmarks.code_replay.swebench_pilot import vault, validate_product_runtime, validate_frozen_manifest
from benchmarks.code_replay.swebench_qualification_cache import reuse


def prepare(source_root, destination_root, runtime):
    source_root, destination_root = Path(source_root), Path(destination_root)
    parent = json.loads((source_root / 'manifest.json').read_text())
    status = json.loads((source_root / 'results.json').read_text())
    if status['status'] != 'completed' or parent.get('cohort') != 'validation':
        raise ValueError('complete original validation required')
    runtime = validate_product_runtime(runtime)
    os.environ['ATMEM_HOME'] = str(source_root / 'home')
    original, source_principal = vault(source_root)
    validate_frozen_manifest(original.inspect(source_principal, 'pilot'), parent)
    tasks = {}
    for row in parent['selected']:
        values = [e['envelope']['payload'] for e in original.inspect(source_principal, row['instance_id'])
                  if e['envelope']['event_type'] == 'upstream.task']
        if len(values) != 1:
            raise ValueError('one original task definition required')
        tasks[row['instance_id']] = values[0]
    manifest = {key: value for key, value in parent.items() if key != 'cognee_runtime'}
    manifest.update(format='atmem-swebench-automatic-validation-v1', arms=['no_memory', 'atmem_structure'],
        context_delivery='automatic', model_graph_tools=False, product_runtime=runtime, parent_campaign=source_root.name,
        governing_protocol='specs/042-atmem-code/swebench-threeway-20261019.md',
        delivery_comparison='native tools versus automatic AtMem source pack with native tools; no additional model-visible graph schemas; not the original equal-optional comparison',
        selected=[{**row, 'arm_order': ['no_memory', 'atmem_structure'] if i % 2 == 0 else ['atmem_structure', 'no_memory']}
                  for i, row in enumerate(parent['selected'])])
    destination_root.mkdir(parents=True, mode=0o700, exist_ok=False)
    os.environ['ATMEM_HOME'] = str(destination_root / 'home')
    target, principal = vault(destination_root)
    (destination_root / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    target.capture(run_id='pilot', kind='selection.frozen', payload=manifest, principal=principal)
    target.capture(run_id='pilot', kind='campaign.additional_protocol', principal=principal,
        payload={'protocol': Path('specs/042-atmem-code/swebench-threeway-20261019.md').read_text(),
                 'source': Path(__file__).read_text(), 'eligibility_cache_source':
                 Path(__file__).with_name('swebench_qualification_cache.py').read_text()})
    for identity, task in tasks.items():
        target.capture(run_id=identity, kind='upstream.task', payload=task, principal=principal)
    count = reuse(source_root, destination_root)
    return {'selected': len(tasks), 'eligibility_proofs_reused': count, 'model_outcomes_reused': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, args.root, json.loads(args.runtime.read_text()))), flush=True)


if __name__ == '__main__':
    main()
