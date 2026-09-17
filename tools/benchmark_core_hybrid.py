"""Prebuilt, frozen calibration comparison with independent graph ablation.

Copies fixture databases; never touches live user memory. No answer generation.
"""
import argparse
import json
import math
from pathlib import Path
import shutil
import statistics
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from atmem import Memory
from atmem.contracts import AuthorityScope, RecallRequest
from run_longmemeval_retrieval import _load_manifest_cases, _corpus

PROFILES = {
    'legacy_without_graph': ('legacy', ('lexical', 'semantic')),
    'legacy_graph': ('legacy', ('lexical', 'semantic', 'graph')),
    'core_without_graph': ('core-rrf-v1', ('lexical', 'semantic')),
    'core_with_graph': ('core-rrf-v1', ('lexical', 'semantic', 'graph')),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, default=Path('atmem/benchmark/data/mem0-head-to-head-2.3.3b1-v1.json'))
    parser.add_argument('--output', type=Path, help='New report only; never overwrite existing evidence')
    args = parser.parse_args()
    cases, digest = _load_manifest_cases(args.dataset, args.manifest, 'calibration')
    results = []
    with tempfile.TemporaryDirectory(prefix='atmem-core-hybrid-') as directory:
        work = Path(directory) / 'corpus'
        shutil.copytree(args.source, work)
        for case_index, case in enumerate(cases):
            memory = Memory(work / f"{case['question_id']}.db", auto_vectors=False)
            try:
                records = memory.store.list_records('longmemeval-user')
                expected = _corpus(case, 1600, matched_inputs=True)
                assert {(r['source_session_id'], r['content']) for r in records} == set(expected)
                sessions = {r['id']: r['source_session_id'] for r in records}
                row = {'case_id': case['question_id'], 'records': len(records)}
                for profile in PROFILES:
                    row[profile] = {'times_ms': []}
                for repetition in range(3):
                    names = list(PROFILES)
                    offset = (case_index + repetition) % len(names)
                    for profile in names[offset:] + names[:offset]:
                        strategy, signals = PROFILES[profile]
                        req = RecallRequest(request_id=f'q{repetition}', scope=AuthorityScope('longmemeval-user', 'benchmark', 'benchmark'),
                            query=case['question'], limit=100, candidate_limit=100, min_score=0,
                            signals=signals, retrieval_strategy=strategy)
                        start = time.perf_counter()
                        candidates = memory.eligible_candidates(req)
                        row[profile]['times_ms'].append((time.perf_counter() - start) * 1000)
                        top_sessions = list(dict.fromkeys(sessions[r.record_id] for r in candidates.candidates))[:5]
                        answer_sessions = set(case['answer_session_ids'])
                        positions = [i + 1 for i, s in enumerate(top_sessions) if s in answer_sessions]
                        row[profile].update(retrieved_sessions=top_sessions,
                            recall_any=bool(positions), recall_all=answer_sessions.issubset(top_sessions),
                            reciprocal_rank=1 / min(positions) if positions else 0)
                        if profile == 'core_with_graph':
                            event = next(e for e in memory.store.list_audit_events('longmemeval-user')
                                         if e['event_id'] == candidates.audit_event_id)
                            metadata = event['payload']['retrieval_fusion']
                            row[profile]['graph_coverage'] = {k: v for k, v in metadata.items()
                                if k.startswith('graph_') and k != 'graph_support_record_ids'}
                results.append(row)
                print(f"completed {case['question_id']}", file=sys.stderr, flush=True)
            finally:
                memory.close()
    aggregate = {}
    for profile in PROFILES:
        times = [t for row in results for t in row[profile]['times_ms']]
        aggregate[profile] = {'median_ms': statistics.median(times), 'p95_ms': sorted(times)[math.ceil(len(times)*.95)-1],
            **{metric: statistics.mean(row[profile][metric] for row in results) for metric in ('recall_any', 'recall_all', 'reciprocal_rank')}}
    report = json.dumps({'profile': 'core-graph-calibration-v3', 'manifest_sha256': digest,
        'profiles': {k: {'strategy': v[0], 'signals': v[1]} for k, v in PROFILES.items()},
        'order': 'rotated_by_case_and_repetition', 'samples_per_case': 3,
        'results': results, 'aggregate': aggregate}, indent=2)
    if args.output:
        with args.output.open('x') as output:
            output.write(report + '\n')
    print(report)


if __name__ == '__main__':
    main()
