"""Freeze a separately declared reused-task compact-interface screen.

Fresh native and candidate outcomes; no changes to any completed confirmation.
"""
import argparse
import json
import os
from pathlib import Path

from benchmarks.code_replay.swebench_pilot import vault, validate_product_runtime, validate_frozen_manifest
from benchmarks.code_replay.swebench_qualification_cache import reuse

PROTOCOL = 'specs/042-atmem-code/compact-interface-screen-20261019.md'


def prepare(source_root, destination_root, runtime):
    source_root, destination_root = Path(source_root), Path(destination_root)
    parent = json.loads((source_root / 'manifest.json').read_text())
    status = json.loads((source_root / 'results.json').read_text())
    if status['status'] != 'completed' or parent.get('cohort') != 'validation' or len(parent['selected']) != 5:
        raise ValueError('complete original five-task validation required')
    runtime = validate_product_runtime(runtime)
    os.environ['ATMEM_HOME'] = str(source_root / 'home')
    original, principal = vault(source_root)
    validate_frozen_manifest(original.inspect(principal, 'pilot'), parent)
    tasks = {}
    for row in parent['selected']:
        values = [event['envelope']['payload'] for event in original.inspect(principal, row['instance_id'])
                  if event['envelope']['event_type'] == 'upstream.task']
        if len(values) != 1:
            raise ValueError('one retained original task required')
        tasks[row['instance_id']] = values[0]
    manifest = {key: value for key, value in parent.items() if key != 'cognee_runtime'}
    manifest.update(format='atmem-swebench-compact-interface-screen-v1',
        arms=['no_memory', 'atmem_structure'], product_runtime=runtime,
        context_delivery='optional', model_graph_tools=True, atmem_tool_profile='compact',
        governing_protocol=PROTOCOL, parent_campaign=source_root.name,
        prior_exposure='all five tasks reused after inspected validation; not held-out confirmation',
        claim='reused-task engineering screen; no paired Cognee or held-out superiority claim',
        selected=[{**row, 'arm_order': ['no_memory', 'atmem_structure'] if i % 2 == 0
                   else ['atmem_structure', 'no_memory']} for i, row in enumerate(parent['selected'])])
    destination_root.mkdir(parents=True, mode=0o700, exist_ok=False)
    os.environ['ATMEM_HOME'] = str(destination_root / 'home')
    target, target_principal = vault(destination_root)
    (destination_root / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    target.capture(run_id='pilot', kind='selection.frozen', principal=target_principal, payload=manifest)
    target.capture(run_id='pilot', kind='campaign.additional_protocol', principal=target_principal,
        payload={'protocol': Path(PROTOCOL).read_text(), 'source': Path(__file__).read_text(),
                 'eligibility_cache_source': Path(__file__).with_name('swebench_qualification_cache.py').read_text()})
    for identity, task in tasks.items():
        target.capture(run_id=identity, kind='upstream.task', principal=target_principal, payload=task)
    count = reuse(source_root, destination_root)
    return {'selected': len(tasks), 'eligibility_proofs_reused': count, 'model_outcomes_reused': False,
            'atmem_tool_profile': 'compact', 'held_out': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, args.root, json.loads(args.runtime.read_text()))), flush=True)


if __name__ == '__main__':
    main()
