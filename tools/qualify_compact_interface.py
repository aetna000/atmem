"""Installed public-Click transport equivalence; interface bytes, not billed tokens.

Uses an existing explicit public-source qualification, with its isolated encrypted
household. No solver, hidden test, egress, owner memory or smaller context budget.
"""
import argparse
from hashlib import sha256
from io import StringIO
import json
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('choose a new report path')
    if not (args.state_root / 'qualification.json').is_file():
        raise ValueError('existing public-source qualification required')
    os.environ['ATMEM_HOME'] = str(args.state_root / 'home')
    import atmem
    from atmem.memory import Memory
    from atmem.code.application import CodeApplication
    from atmem.code.identity import CodeIdentity
    from atmem.knowledge.code.mcp import CodeKnowledgeMCP
    from atmem.code.knowledge_setup import mcp_configuration
    if '/site-packages/atmem/' not in str(Path(atmem.__file__).resolve()):
        raise ValueError('installed interpreter required')
    memory = Memory(args.state_root / 'memory.db', auto_vectors=False)
    try:
        root = args.state_root / 'click-source'
        scope = CodeIdentity(memory.store).resolve(root, subject_id='qualification', profile_id='shared', agent_id='claude')
        app = CodeApplication(memory, subject_id=scope.subject_id)
        expanded = CodeKnowledgeMCP(app, scope, str(root), experience=True)
        compact = CodeKnowledgeMCP(app, scope, str(root), experience=True, tool_profile='compact')
        generation = expanded.knowledge.current(str(root))
        assert generation is not None
        seed = next(obj['object_id'] for obj in generation['objects'] if obj['name'].endswith('get_help_option'))
        calls = [('context', 'code_context', {'query': 'get_help_option', 'budget': 4096}),
            ('search', 'code_search', {'query': 'get_help_option'}),
            ('source', 'code_source', {'path': 'src/click/core.py', 'start_line': 1, 'line_count': 3}),
            ('experience', 'code_experience', {'limit': 3}),
            ('query_facts', 'code_search', {'name': 'get_help_option', 'limit': 3}),
            ('explore', 'code_search', {'id': seed, 'max_nodes': 8}),
            ('traverse', 'code_search', {'node_ids': [seed], 'max_depth': 3, 'max_nodes': 8}),
            ('find_path', 'code_search', {'source_id': seed, 'target_id': seed, 'max_nodes': 8}),
            ('impact_analysis', 'code_search', {'id': seed, 'max_depth': 2, 'max_nodes': 8}),
            ('architecture', 'code_search', {'max_nodes': 8}), ('delta', 'code_search', {}),
            ('insights', 'code_search', {'limit': 3})]
        catalog = {}
        for name, instance in [('expanded', expanded), ('compact', compact)]:
            replies = [instance.handle({'id': 1, 'method': 'initialize'}), instance.handle({'id': 2, 'method': 'tools/list'})]
            raw = json.dumps(replies, ensure_ascii=False, separators=(',', ':')).encode()
            catalog[name] = {'utf8_bytes': len(raw), 'sha256': sha256(raw).hexdigest(), 'responses': replies}
        rows = []
        for index, (operation, target, config) in enumerate(calls, 3):
            old_args = ({'operation': operation, 'arguments': config, 'budget': 131072}
                        if operation not in {'context', 'search', 'source', 'experience'} else config)
            new_args = {'operation': operation, 'arguments': config}
            if 'operation' in old_args:
                new_args['budget'] = old_args['budget']
            outputs = []
            for instance, tool, payload in [(expanded, target, old_args), (compact, 'code_query', new_args)]:
                reply = instance._call_tool(index, tool, payload)
                stream = StringIO()
                instance._write(stream, reply)
                response = json.loads(stream.getvalue())
                assert 'error' not in response and not response['result']['isError'], (operation, response)
                outputs.append(response)
            assert outputs[0] == outputs[1], operation
            rows.append({'operation': operation, 'exact_stdio_response_equal': True,
                         'response_sha256': sha256(json.dumps(outputs[0], sort_keys=True).encode()).hexdigest(),
                         'expanded_arguments': old_args, 'compact_arguments': new_args})
        config = mcp_configuration(app, scope, str(root), tool_profile='compact')
        assert config['tools'] == ['code_query'] and config['tool_profile'] == 'compact'
        report = {'status': 'passed', 'installed_package': str(atmem.__file__), 'python': sys.version,
            'snapshot_id': generation['snapshot_id'], 'objects': len(generation['objects']),
            'relations': len(generation['relations']), 'catalogs': catalog, 'operations': rows,
            'interface_byte_reduction_fraction': 1 - catalog['compact']['utf8_bytes'] / catalog['expanded']['utf8_bytes'],
            'model_runs': 0, 'billed_tokens_measured': False,
            'classification': 'Installed transport/interface control, not end-to-end coding quality, token saving or latency evidence'}
        args.output.write_text(json.dumps(report, indent=2))
        print(json.dumps({key: report[key] for key in ('status', 'interface_byte_reduction_fraction', 'model_runs',
            'billed_tokens_measured')}) + '\n' + str(args.output), flush=True)
    finally:
        memory.close()


if __name__ == '__main__':
    main()
