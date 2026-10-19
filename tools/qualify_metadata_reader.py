"""Installed-only all-operation equivalence on an actual public Click generation.

The baseline algorithms are read from the retained exact previous wheel, not
reimplemented. Pure-query times exclude source checks, indexing and inference.
"""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import time
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-root', type=Path, required=True)
    parser.add_argument('--baseline-wheel', type=Path, required=True)
    parser.add_argument('--baseline-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('choose a fresh report path')
    if sha256(args.baseline_wheel.read_bytes()).hexdigest() != args.baseline_sha256:
        raise ValueError('baseline wheel digest differs')
    os.environ['ATMEM_HOME'] = str(args.state_root / 'home')
    import atmem
    from atmem.memory import Memory
    from atmem.code.identity import CodeIdentity
    from atmem.code.application import CodeApplication
    from atmem.knowledge.projections import CodeKnowledge
    from atmem.knowledge.code.queries import query_generation
    from atmem.core.canonical import canonical_json
    if '/site-packages/atmem/' not in str(Path(atmem.__file__).resolve()):
        raise ValueError('installed candidate interpreter required')
    package = Path(atmem.__file__).parent
    with zipfile.ZipFile(args.baseline_wheel) as baseline:
        # Dependencies and unchanged renderer/contracts must not stand in for a
        # silently altered old algorithm in this in-process differential.
        for name in ('knowledge/_vendor/code_graph_diagram.py', 'knowledge/contracts.py', 'code/contracts.py'):
            assert (package / name).read_bytes() == baseline.read('atmem/' + name)
        old_vendor = {'__name__': 'retained_vendor_baseline', '__package__': 'atmem.knowledge._vendor'}
        exec(compile(baseline.read('atmem/knowledge/_vendor/code_retriever.py'), '<retained-vendor>', 'exec'), old_vendor)
        old_query = {'__name__': 'retained_query_baseline', '__package__': 'atmem.knowledge.code'}
        exec(compile(baseline.read('atmem/knowledge/code/queries.py'), '<retained-query>', 'exec'), old_query)
        old_query['CodeRetriever'] = old_vendor['CodeRetriever']
    memory = Memory(args.state_root / 'memory.db', auto_vectors=False)
    try:
        root = args.state_root / 'click-source'
        scope = CodeIdentity(memory.store).resolve(root, subject_id='qualification', profile_id='shared', agent_id='claude')
        knowledge = CodeKnowledge(CodeApplication(memory, subject_id=scope.subject_id), scope)
        generation = knowledge.current(str(root))
        assert generation is not None
        seed = next(obj['object_id'] for obj in generation['objects'] if obj['name'].endswith('get_help_option'))
        operations = [('query_facts', {'name': 'get_help_option', 'limit': 3}), ('explore', {'id': seed, 'max_nodes': 8}),
            ('traverse', {'node_ids': [seed], 'max_depth': 3, 'max_nodes': 8}),
            ('find_path', {'source_id': seed, 'target_id': seed, 'max_nodes': 8}),
            ('impact_analysis', {'id': seed, 'max_depth': 2, 'max_nodes': 8}),
            ('architecture', {'max_nodes': 8}), ('delta', {}), ('insights', {'limit': 3})]
        rows = []
        for index, (operation, config) in enumerate(operations):
            readers = [('retained_baseline', old_query['query_generation']), ('metadata_reader', query_generation)]
            measured = {}
            for name, reader in (readers if index % 2 == 0 else list(reversed(readers))):
                tick = time.perf_counter()
                result = reader(generation, operation=operation, config=config, max_bytes=1_000_000)
                elapsed = time.perf_counter() - tick
                raw = canonical_json(result).encode()
                assert result['status'] == 'current'
                measured[name] = {'seconds': elapsed, 'canonical_result_sha256': sha256(raw).hexdigest(),
                                  'bytes': len(raw), 'response': result}
            equal = measured['retained_baseline']['canonical_result_sha256'] == measured['metadata_reader']['canonical_result_sha256']
            rows.append({'operation': operation, 'config': config, 'exact_canonical_result_equal': equal, 'readers': measured})
            assert equal, 'query output changed: ' + operation
        assert knowledge.current(str(root))['snapshot_id'] == generation['snapshot_id']
        report = {'status': 'passed', 'installed_package': str(atmem.__file__), 'python': sys.version,
            'baseline_wheel_sha256': args.baseline_sha256, 'snapshot_id': generation['snapshot_id'],
            'objects': len(generation['objects']), 'relations': len(generation['relations']), 'operations': rows,
            'classification': 'actual public Click generation, installed query differential; not coding-task or end-user latency evidence'}
        args.output.write_text(json.dumps(report, indent=2))
        print(json.dumps({'status': 'passed', 'operations': len(rows), 'all_results_equal': True,
            'report': str(args.output), 'pure_query_seconds': {row['operation']: {name: value['seconds']
                for name, value in row['readers'].items()} for row in rows}}), flush=True)
    finally:
        memory.close()


if __name__ == '__main__':
    main()
