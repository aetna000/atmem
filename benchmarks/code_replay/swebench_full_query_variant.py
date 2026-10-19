"""Freeze the separately qualified complete-query automatic-context screen."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path

from benchmarks.code_replay.swebench_pilot import vault, validate_product_runtime, validate_frozen_manifest
from benchmarks.code_replay.swebench_qualification_cache import reuse
from benchmarks.code_replay.swebench_context import validated_context

PROTOCOL = 'specs/042-atmem-code/full-query-context-screen-20261019.md'


def validate_qualification(manifest, result, inspect, runtime, tasks):
    if (manifest.get('format') != 'atmem-full-query-context-qualification-v1'
            or manifest.get('product_runtime') != runtime or manifest.get('model_runs') != 0
            or result.get('status') != 'completed' or len(result.get('rows', [])) != len(tasks)
            or [item['instance_id'] for item in manifest['selected']] != list(tasks)):
        raise ValueError('complete matched full-query qualification required')
    plans = [e['envelope']['payload']['manifest'] for e in inspect('pilot')
             if e['envelope']['event_type'] == 'diagnostic.full_query_planned']
    if plans != [manifest]:
        raise ValueError('qualification manifest differs from protected plan')
    rebuilt = []
    for identity, task in tasks.items():
        events = [e['envelope'] for e in inspect(identity)]
        requests = [e['payload'] for e in events if e['event_type'] == 'diagnostic.full_query_request']
        replies = [e['payload'] for e in events if e['event_type'] == 'diagnostic.full_query_response']
        if len(requests) != 1 or len(replies) != 1:
            raise ValueError('one actual full-query qualification per source required')
        request, raw = requests[0], replies[0]
        query = task['problem_statement']
        prefix = query.encode()[:1000].decode(errors='ignore')
        if (request['runtime'] != runtime or request['query_bytes'] != [len(prefix.encode()), len(query.encode())]
                or len(query.encode()) > 4000 or len(raw['responses']) != 3):
            raise ValueError('qualification query/runtime binding differs')
        for i, text in ((1, prefix), (2, query)):
            expected = {'jsonrpc': '2.0', 'id': i + 1, 'method': 'tools/call', 'params': {
                'name': 'code_context', 'arguments': {'query': text, 'budget': 4096}}}
            if request['requests'][i] != expected:
                raise ValueError('qualification omitted or changed full issue text')
        pack = validated_context(raw['responses'][2])
        if pack is None or pack['snapshot_id'] != raw['snapshot_id']:
            raise ValueError('qualified full source pack is unavailable')
        packs = [json.loads(answer['result']['content'][0]['text']) for answer in raw['responses'][1:]]
        if any(p['status'] != 'current' or p['snapshot_id'] != pack['snapshot_id']
               or sha256(p['content'].encode()).hexdigest() != p['content_sha256'] for p in packs):
            raise ValueError('qualification source changed or lost integrity')
        if (raw['context_bytes'] != [len(p['content'].encode()) for p in packs]
                or raw['context_sha256'] != [p['content_sha256'] for p in packs]
                or type(raw['installed_package_files']) is not int or raw['installed_package_files'] < 1):
            raise ValueError('qualification response metadata differs')
        rebuilt.append({'instance_id': identity, 'status': 'passed', 'query_bytes': request['query_bytes'],
            **{key: raw[key] for key in ('snapshot_id', 'installed_package_files', 'context_bytes', 'context_sha256')}})
    if rebuilt != result['rows']:
        raise ValueError('qualification projection differs from protected responses')
    return rebuilt


def prepare(source_root, destination_root, runtime, qualification_root):
    source_root, destination_root, qualification_root = map(Path, (source_root, destination_root, qualification_root))
    parent = json.loads((source_root / 'manifest.json').read_text())
    if (json.loads((source_root / 'results.json').read_text())['status'] != 'completed'
            or parent.get('cohort') != 'validation' or len(parent['selected']) != 5):
        raise ValueError('complete original five-task validation required')
    runtime = validate_product_runtime(runtime)
    os.environ['ATMEM_HOME'] = str(source_root / 'home')
    original, principal = vault(source_root)
    validate_frozen_manifest(original.inspect(principal, 'pilot'), parent)
    tasks = {}
    for item in parent['selected']:
        rows = [e['envelope']['payload'] for e in original.inspect(principal, item['instance_id'])
                if e['envelope']['event_type'] == 'upstream.task']
        if len(rows) != 1:
            raise ValueError('one original task required')
        tasks[item['instance_id']] = rows[0]
    q_manifest = json.loads((qualification_root / 'manifest.json').read_text())
    q_result_raw = (qualification_root / 'results.json').read_bytes()
    if q_manifest.get('source_campaign') != source_root.name:
        raise ValueError('qualification source campaign differs')
    os.environ['ATMEM_HOME'] = str(qualification_root / 'home')
    qualification, access = vault(qualification_root)
    validate_qualification(q_manifest, json.loads(q_result_raw), lambda key: qualification.inspect(access, key), runtime, tasks)
    manifest = {key: value for key, value in parent.items() if key != 'cognee_runtime'}
    manifest.update(format='atmem-swebench-full-query-screen-v1', arms=['no_memory', 'atmem_structure'],
        context_delivery='automatic', full_context_query=True, model_graph_tools=False,
        product_runtime=runtime, parent_campaign=source_root.name, governing_protocol=PROTOCOL,
        prior_exposure='all five validation tasks previously inspected; this is reused-task engineering evidence',
        claim='full-query automatic context versus native; not untouched confirmation or paired Cognee comparison',
        full_query_qualification_sha256=sha256(q_result_raw).hexdigest(),
        selected=[{**item, 'arm_order': ['no_memory', 'atmem_structure'] if i % 2 == 0
                   else ['atmem_structure', 'no_memory']} for i, item in enumerate(parent['selected'])])
    destination_root.mkdir(parents=True, mode=0o700, exist_ok=False)
    os.environ['ATMEM_HOME'] = str(destination_root / 'home')
    target, access = vault(destination_root)
    (destination_root / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    target.capture(run_id='pilot', kind='selection.frozen', principal=access, payload=manifest)
    target.capture(run_id='pilot', kind='campaign.additional_protocol', principal=access,
        payload={'protocol': Path(PROTOCOL).read_text(), 'source': Path(__file__).read_text(),
            'qualification_manifest': q_manifest, 'qualification_result_sha256': sha256(q_result_raw).hexdigest(),
            'eligibility_cache_source': Path(__file__).with_name('swebench_qualification_cache.py').read_text()})
    for identity, task in tasks.items():
        target.capture(run_id=identity, kind='upstream.task', principal=access, payload=task)
    count = reuse(source_root, destination_root)
    return {'selected': len(tasks), 'full_query_qualified': True, 'eligibility_proofs_reused': count,
            'model_outcomes_reused': False, 'held_out': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--qualification', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, args.root, json.loads(args.runtime.read_text()), args.qualification)), flush=True)


if __name__ == '__main__':
    main()
