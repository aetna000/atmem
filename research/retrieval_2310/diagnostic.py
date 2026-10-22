"""Reader-free *development* diagnostic through the unchanged public V3 path.

Measures source-turn reachability, NOT semantic sufficiency or task correctness.
Gold references are used only after product recall returns. No model calls.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import re
import subprocess
import time

from benchmarks.dolphinbench.driver import AtMemHost
from atmem.context_engine.formation import FormationManager
from atmem.context_engine.contracts import ContextRequestV3
from atmem.context_engine.hybrid import HybridStoredContextEngine
from atmem.context_engine.semantic import SemanticIndex, SQLiteExactSemanticIndex
from atmem.contracts.models import RetrievalBudget
from atmem.semantic.providers import OllamaEmbedder
from .protocol import digest
from .preflight import inventory
from .qualify import expand_reference, qualify_realtalk


def run(source: Path, output: Path, *, seed: int = 2310, limit: int = 30,
        semantic: bool = False, reuse_from: Path | None = None,
        semantic_candidates: int = 32, backend: str = 'lsh') -> dict:
    if source.name != 'Chat_1_Emi_Elise.json':
        raise ValueError('This bounded diagnostic is restricted to the already inspected development conversation')
    if output.exists():
        raise ValueError('New run directory required; never overwrite prior results')
    if not 1 <= limit <= 50:
        raise ValueError('Development diagnostic limit must be 1..50')
    raw = source.read_bytes()
    data = json.loads(raw)
    qualified = qualify_realtalk(source.parent.parent)
    excluded = {v['qa_index'] for v in qualified['exclusions'] if v['file'] == source.name}
    eligible = [i for i in range(len(data['qa'])) if i not in excluded]
    selected = sorted(random.Random(seed).sample(eligible, min(limit, len(eligible))))
    if len(selected) != limit:
        raise ValueError('Insufficient qualified development questions')
    output.mkdir(parents=True)
    repo = Path(__file__).resolve().parents[2]
    manifest = {'mode': 'development-source-turn-diagnostic-no-reader',
                'corpus_sha256': hashlib.sha256(raw).hexdigest(), 'seed': seed,
                'selected_qa_indices': selected, 'query_limit': limit,
                'evidence_annotations_available_to_product': False,
                'model_calls': 0, 'paid_api_usd': '0', 'ready_for_600': False}
    manifest['engine'] = 'semantic-supplement-prototype' if semantic else 'unchanged-v3'
    manifest['semantic_candidates'] = semantic_candidates if semantic else 0
    manifest['semantic_backend'] = backend if semantic else None
    manifest['source_inventory_digest'] = digest(inventory(repo))
    manifest['base_commit'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    subprocess.run(['tar', '-czf', str(output/'source-overlay.tar.gz'),
                    'atmem/context_engine', 'atmem/memory.py', 'atmem/semantic/providers.py',
                    'research/retrieval_2310', 'specs/046-retrieval-performance-2310'], cwd=repo, check=True)
    if reuse_from:
        previous = json.loads((reuse_from/'manifest.json').read_text())
        if not semantic or previous.get('corpus_sha256') != manifest['corpus_sha256'] or previous['selected_qa_indices'] != selected:
            raise ValueError('source/query identity differs; frozen baseline reuse refused')
        manifest['reused_frozen_history'] = str(reuse_from)
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2))
    host = AtMemHost((reuse_from or output)/'host', 'realtalk-development', memory_engine='context-v3')
    source_to_turn = {}
    observations = []
    results = []
    try:
        sessions = sorted((k for k in data if re.fullmatch(r'session_\d+', k)),
                          key=lambda k: int(k.split('_')[1]))
        if reuse_from:
            observations = json.loads((reuse_from/'ingestion.json').read_text())
            host.verify_checkpoint(json.loads((reuse_from/'checkpoint.json').read_text()))
            for observation in observations:
                receipt = observation['receipt']
                if receipt.get('captured'):
                    for span in receipt['formation']['represented_ranges']:
                        source_to_turn[span['source_id']] = observation['turn_id']
        for session in (() if reuse_from else sessions):
            for turn in data[session]:
                # Original released turn fields are preserved, no fact extraction
                # or question-derived rewriting is performed by this adapter.
                text = json.dumps(turn, ensure_ascii=False, sort_keys=True)
                receipt = host.service.dispatch(host.credential, 'observe', {
                    'text': text, 'session_id': session, 'observation_id': turn['dia_id']})
                observations.append({'turn_id': turn['dia_id'], 'receipt': receipt})
                if receipt.get('captured'):
                    for span in receipt['formation']['represented_ranges']:
                        source_to_turn[span['source_id']] = turn['dia_id']
        binding = host.service._binding(host.service._load(host.binding['binding_id']))
        embedder, index_identity, dimensions, generation_id = None, None, None, None
        if semantic:
            embedder = OllamaEmbedder('nomic-embed-text:latest',
                model_version='sha256:0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f',
                truncate=False)
            index_identity = embedder.identity
            # This fresh database belongs solely to this authorized development
            # binding. Query labels and expected source references are not used.
            with binding.v3().memory() as (memory, scope):
                generation_id = observations[-1]['receipt']['formation']['generation_id']
                generation_row = memory.store._conn.execute('SELECT * FROM context_view_generations WHERE generation_id=?',
                                                            (generation_id,)).fetchone()
                if (generation_row['subject_id'], generation_row['agent_id'], generation_row['workspace_id']) != (
                        scope.subject_id, scope.agent_id, scope.workspace_id):
                    raise ValueError('embedding source scope differs from approved binding')
                if reuse_from:
                    dimensions = previous['embedding']['dimensions']
                    if previous['embedding']['identity'] != index_identity:
                        raise ValueError('embedding identity changed; frozen index reuse refused')
                    manifest['embedding'] = previous['embedding']
                rows = [] if reuse_from else memory.store._conn.execute('''SELECT u.unit_id,r.start_offset,r.end_offset,p.content_bytes
                    FROM context_evidence_units u
                    JOIN context_unit_ranges ur ON ur.generation_id=u.generation_id AND ur.unit_id=u.unit_id
                    JOIN context_source_ranges r ON r.range_id=ur.range_id
                    JOIN context_source_parts p ON p.source_id=r.source_id AND p.part_id=r.part_id
                    WHERE u.generation_id=? AND u.kind='raw_state' AND u.lifecycle='active'
                    ORDER BY u.unit_id''', (generation_id,)).fetchall()
                ids, texts = [], []
                for row in rows:
                    ids.append(row['unit_id'])
                    texts.append(bytes(row['content_bytes'])[row['start_offset']:row['end_offset']].decode())
                if len(ids) != len(set(ids)):
                    raise ValueError('multi-range raw units require separately qualified embedding packing')
                vectors = []
                for start in range(0, len(ids), 32):
                    embedder.verify_identity()
                    vectors.extend(embedder.embed_documents(texts[start:start+32]))
                    print(json.dumps({'embedded_units': len(vectors), 'total_units': len(ids)}), flush=True)
                if not reuse_from:
                    dimensions = len(vectors[0])
                    index = SemanticIndex(memory.store, generation_id=generation_id,
                        model_identity=index_identity, dimensions=dimensions)
                    index.build(zip(ids, vectors), allowed_unit_ids=frozenset(ids))
                    manifest['embedding'] = {'identity': index_identity, 'units': len(ids),
                        'dimensions': dimensions, 'index_id': index.index_id,
                        'truncation_permitted': False, 'external_provider_calls': 0}
                manifest['model_calls'] = 'local-embedding-only; no reader calls'
                (output/'manifest.json').write_text(json.dumps(manifest, indent=2))
        checkpoint = json.loads((reuse_from/'checkpoint.json').read_text()) if reuse_from else host.freeze()
        (output/'checkpoint.json').write_text(json.dumps(checkpoint, indent=2))
        (output/'ingestion.json').write_text(json.dumps(observations))
        for index in selected:
            query = data['qa'][index]['question']
            started = time.monotonic()
            if not semantic:
                ruling = host.service.dispatch(host.credential, 'recall', {
                    'query': query, 'session_id': f'question-{index}', 'turn_id': f'question-{index}'})
            else:
                embedder.verify_identity()
                vector = embedder.embed_query(query)
                with binding.v3().memory() as (memory, scope):
                    generation = memory.context_generation(scope)
                    index_type = SQLiteExactSemanticIndex if backend == 'sqlite-vec' else SemanticIndex
                    semantic_index = index_type(memory.store, generation_id=generation_id,
                        model_identity=index_identity, dimensions=dimensions)
                    request = ContextRequestV3(context_id=f'ctx-{index}', request_id=f'req-{index}',
                        scope=scope, query=query, profile_id='context-fast', mode='active',
                        generation=generation['canonical_generation'], turn_id=f'question-{index}',
                        budget=RetrievalBudget(total_candidates=200, context_bytes=32000))
                    package = memory.prepare_context_v3(request, engine=HybridStoredContextEngine(
                        memory.store, generation_id=generation_id, semantic_index=semantic_index,
                        query=query, query_vector=vector, semantic_candidates=semantic_candidates))
                    ruling = {'context': package.context, 'reason': 'authorized' if package.status == 'sufficient' else package.status,
                              'candidate_ids': package.selected_unit_ids, 'engine': 'semantic-supplement-prototype',
                              'reason_codes': package.reason_codes}
            elapsed = (time.monotonic()-started)*1000
            delivered = set()
            if ruling.get('reason') == 'authorized':
                # Evaluator-only mapping after recall; this does not nominate,
                # rank, repackage or add evidence to the product response.
                with binding.v3().memory() as (memory, scope):
                    generation = memory.context_generation(scope)
                    manager = FormationManager(memory.store)
                    for identity in ruling.get('candidate_ids', []):
                        unit = manager.get_unit(identity, generation_id=generation['generation_id'])
                        delivered.update(source_to_turn[r['source_id']] for r in unit['ranges']
                                         if r['source_id'] in source_to_turn)
            expected = {ref for raw_ref in data['qa'][index]['evidence']
                        for ref in expand_reference(raw_ref)}
            results.append({'qa_index': index, 'category': data['qa'][index]['category'],
                            'reason': ruling.get('reason'), 'duration_ms': elapsed,
                            'expected_turns': sorted(expected),
                            'delivered_turns': sorted(delivered),
                            'required_turns_reached': len(expected & delivered),
                            'required_turns': len(expected),
                            'all_required_turns_reached': expected.issubset(delivered),
                            'context_bytes': len(ruling.get('context', '').encode()),
                            'ruling_digest': digest(ruling)})
            # The original full public-query context is retained locally for
            # development diagnosis; no credentials or household keys exported.
            (output/f'question-{index}.json').write_text(json.dumps(ruling))
            print(json.dumps({'completed': len(results), 'total': limit}), flush=True)
        host.verify_checkpoint(checkpoint)
        summary = {**manifest, 'questions': len(results),
                   'all_required_turns_reached': sum(r['all_required_turns_reached'] for r in results),
                   'required_turn_recall': sum(r['required_turns_reached'] for r in results)/sum(r['required_turns'] for r in results),
                   'ruling_counts': dict(Counter(r['reason'] for r in results)),
                   'frozen_memory_verified_after_queries': True,
                   'qualification': 'diagnostic-only; source-turn overlap is not complete semantic support'}
        (output/'results.json').write_text(json.dumps(results, indent=2))
        (output/'summary.json').write_text(json.dumps(summary, indent=2))
        return summary
    finally:
        host.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--seed', type=int, default=2310)
    parser.add_argument('--limit', type=int, default=30)
    parser.add_argument('--semantic', action='store_true', help='Explicit opt-in development prototype; not a qualified profile')
    parser.add_argument('--reuse-from', type=Path, help='Reuse explicitly verified frozen history/index, never answers or outcomes')
    parser.add_argument('--semantic-candidates', type=int, default=32)
    parser.add_argument('--backend', choices=['lsh', 'sqlite-vec'], default='lsh')
    args = parser.parse_args()
    print(json.dumps(run(args.source, args.output, seed=args.seed, limit=args.limit, semantic=args.semantic,
                         reuse_from=args.reuse_from, semantic_candidates=args.semantic_candidates,
                         backend=args.backend), sort_keys=True))


if __name__ == '__main__':
    main()
