"""Evaluator-only exact-vector control; never a production retrieval fallback.

An intentionally offline full index scan diagnoses approximation loss separately
from embedding/representation loss. It must not be reported as product latency,
task correctness or a qualified memory profile. Only inspected development data.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct

from atmem.context_engine.semantic import SemanticIndex
from atmem.semantic.providers import OllamaEmbedder
from benchmarks.dolphinbench.driver import AtMemHost
from .qualify import expand_reference


def audit(condition: Path, source: Path) -> dict:
    manifest = json.loads((condition/'manifest.json').read_text())
    if source.name != 'Chat_1_Emi_Elise.json':
        raise ValueError('Only the inspected development conversation is permitted')
    data = json.loads(source.read_text())
    host = AtMemHost(condition/'host', 'realtalk-development', memory_engine='context-v3')
    checkpoint = json.loads((condition/'checkpoint.json').read_text())
    model = manifest['embedding']['identity']
    embedder = OllamaEmbedder(model['model'], model_version=model['revision'], truncate=False)
    if embedder.identity != model:
        raise ValueError('embedding identity changed')
    source_to_turn = {}
    for observation in json.loads((condition/'ingestion.json').read_text()):
        for span in observation['receipt'].get('formation', {}).get('represented_ranges', []):
            source_to_turn[span['source_id']] = observation['turn_id']
    results = []
    try:
        host.verify_checkpoint(checkpoint)
        binding = host.service._binding(host.service._load(host.binding['binding_id']))
        with binding.v3().memory() as (memory, scope):
            generation = memory.context_generation(scope)
            gen = generation['generation_id']
            index = SemanticIndex(memory.store, generation_id=gen, model_identity=model,
                                  dimensions=manifest['embedding']['dimensions'])
            if index.index_id != manifest['embedding']['index_id']:
                raise ValueError('index identity differs from frozen condition')
            rows = memory.store._conn.execute('''SELECT v.unit_id,v.dimensions,v.vector_bytes,r.source_id
                FROM context_vectors v
                JOIN context_unit_ranges ur ON ur.generation_id=v.generation_id AND ur.unit_id=v.unit_id
                JOIN context_source_ranges r ON r.range_id=ur.range_id
                WHERE v.generation_id=? AND v.model_id=? ORDER BY v.unit_id''', (gen, index.index_id)).fetchall()
            vectors = [(r['unit_id'], struct.unpack('<'+'f'*r['dimensions'], r['vector_bytes'])) for r in rows]
            unit_turns = {r['unit_id']: source_to_turn[r['source_id']] for r in rows}
            allowed = frozenset(unit_turns)
            for qid in manifest['selected_qa_indices']:
                embedder.verify_identity()
                query = embedder.embed_query(data['qa'][qid]['question'])
                exact = sorted(((identity, sum(a*b for a,b in zip(query, vector))) for identity, vector in vectors),
                               key=lambda v: (-v[1], v[0]))
                expected = {ref for raw in data['qa'][qid]['evidence'] for ref in expand_reference(raw)}
                approximate = index.nominate(query, allowed_unit_ids=allowed, limit=128, candidate_limit=128)
                row = {'qa_index': qid}
                for k in (32, 128):
                    top_exact = {identity for identity, _ in exact[:k]}
                    top_approx = {hit.unit_id for hit in approximate[:k]}
                    turns_exact = {unit_turns[i] for i in top_exact}
                    turns_approx = {unit_turns[i] for i in top_approx}
                    row[f'ann_recall_at_{k}'] = len(top_exact & top_approx)/len(top_exact)
                    row[f'exact_all_required_turns_at_{k}'] = expected.issubset(turns_exact)
                    row[f'approx_all_required_turns_at_{k}'] = expected.issubset(turns_approx)
                results.append(row)
        host.verify_checkpoint(checkpoint)
        return {'mode': 'offline-approximation-audit-not-product-profile', 'questions': len(results),
                'paid_api_usd': '0', 'ready_for_600': False,
                'mean_ann_recall_at_32': sum(r['ann_recall_at_32'] for r in results)/len(results),
                'mean_ann_recall_at_128': sum(r['ann_recall_at_128'] for r in results)/len(results),
                'exact_all_required_turns_at_32': sum(r['exact_all_required_turns_at_32'] for r in results),
                'exact_all_required_turns_at_128': sum(r['exact_all_required_turns_at_128'] for r in results),
                'approx_all_required_turns_at_128': sum(r['approx_all_required_turns_at_128'] for r in results),
                'results': results}
    finally:
        host.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('condition', type=Path)
    parser.add_argument('source', type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.condition, args.source), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
