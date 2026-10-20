"""Real upstream Cognee CODE qualification on an explicit public source snapshot.

Uses the supported snapshot_dir API and full SDK/backend, never AtMem's vendored
query implementation. This is preparation evidence, not a coding-task score.
Run with a clean environment supplied by the benchmark's provider launcher.
"""
import argparse
import asyncio
from hashlib import sha256
import importlib.metadata
import json
from pathlib import Path
import time
from uuid import uuid4


def serializable(value):
    if hasattr(value, 'model_dump'):
        return value.model_dump()
    return str(value)


def has_nodes(value):
    if isinstance(value, dict):
        return any(isinstance(value.get(key), list) and bool(value[key]) for key in ('nodes', 'facts')) or any(has_nodes(v) for v in value.values())
    if isinstance(value, list):
        return any(has_nodes(v) for v in value)
    if isinstance(value, str) and value.startswith(('{', '[')) and len(value) <= 1_000_000:
        try:
            return has_nodes(json.loads(value))
        except ValueError:
            return False
    return False


async def qualify(args):
    import cognee
    from cognee import SearchType
    from cognee.tasks.code_graph import get_code_graph_tasks
    started = time.monotonic()
    result = {'provider': 'actual_upstream_cognee', 'version': importlib.metadata.version('cognee'),
              'module': cognee.__file__, 'mode': 'CODE_graph_only', 'index_vectors': False,
              'dataset': args.dataset, 'query_only_recheck': args.query_only,
              'extraction': 'common_pinned_enola_snapshot', 'status': 'started'}
    try:
        if not args.query_only:
            await cognee.run_custom_pipeline(tasks=get_code_graph_tasks(str(args.source),
                snapshot_dir=str(args.snapshot), index_vectors=False), data=str(args.source),
                dataset=args.dataset, pipeline_name='swebench_code_qualification', skip_connection_test=True)
            result['load_seconds'] = time.monotonic() - started
        value = await cognee.search(query_type=SearchType.CODE, query_text=args.query,
            datasets=[args.dataset], top_k=3,
            code_query={'operation': 'query_facts', 'name': args.query, 'limit': 3})
        raw = json.dumps(value, default=serializable, ensure_ascii=False)
        if len(raw.encode()) > 1_000_000:
            raise RuntimeError('upstream probe exceeded qualification response bound')
        response_file = 'query-response-recheck-' + uuid4().hex + '.json' if args.query_only else 'query-response.json'
        (args.state / response_file).write_text(raw)
        result['query'] = {'bytes': len(raw.encode()), 'sha256': sha256(raw.encode()).hexdigest(),
                           'contains_graph_items': has_nodes(json.loads(raw)), 'response_file': response_file}
        if not result['query']['contains_graph_items']:
            raise RuntimeError('upstream graph probe did not return graph items')
        result['status'] = 'passed'
    except Exception as exc:
        result.update(status='failed', error_type=type(exc).__name__, error=str(exc)[:1200])
    finally:
        result['elapsed_seconds'] = time.monotonic() - started
        name = 'summary-recheck-' + uuid4().hex + '.json' if args.query_only else 'summary.json'
        (args.state / name).write_text(json.dumps(result, indent=2))
        print(json.dumps(result), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--dataset', required=True)
    parser.add_argument('--query', required=True)
    parser.add_argument('--query-only', action='store_true', help='explicitly recheck the already loaded graph without reindexing')
    args = parser.parse_args()
    if (not args.state.is_dir() or not args.state.name.startswith('cognee-')
            or (args.state / 'summary.json').exists() != args.query_only):
        raise ValueError('fresh dedicated Cognee benchmark state required')
    asyncio.run(qualify(args))


if __name__ == '__main__':
    main()
