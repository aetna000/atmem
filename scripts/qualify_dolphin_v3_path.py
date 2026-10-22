"""No-paid-call qualification of the historical public V3 memory path.

Uses only the first history messages, never test requests, facts or rubrics.
This checks source retention, frozen retrieval and authority boundaries, not
task accuracy or a native Hermes integration. Existing stores stay untouched.
"""
import argparse
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--histories-per-persona', type=int, default=5)
    args = parser.parse_args()
    if not 1 <= args.histories_per_persona <= 25:
        parser.error('This is a bounded qualification, not a full ingestion run')
    root = args.output.resolve()
    root.relative_to(Path('/Volumes/AtMemDolphin'))
    root.mkdir(mode=0o700)
    # Run using the installed candidate with -I; repo code is orchestration only.
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from atmem import Memory
    import atmem
    if Path(atmem.__file__).resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise RuntimeError('Qualification requires an installed product artifact')
    from atmem.contracts import AuthorityScope, EpisodeIngestRequest, EpisodePart, RetrievalBudget
    from atmem.context_engine import ContextRequestV3
    from atmem.service.household import HouseholdApplication
    from benchmarks.dolphinbench.gateway import save_new

    results = {}
    for persona in ('morgan', 'alex', 'riley'):
        # Read only the actual history file; do not load the release's tests.
        import yaml
        upstream = Path('/Volumes/AtMemDolphin/upstream')
        path = upstream / 'registry' / 'personas' / persona / 'life_sim.yaml'
        manifest = json.loads((upstream / 'manifest.json').read_text())
        if hashlib.sha256(path.read_bytes()).hexdigest() != manifest['files'][str(path.relative_to(upstream))]:
            raise ValueError('Public history does not match the released hash')
        raw = yaml.load(path.read_text(), Loader=yaml.CSafeLoader)
        save_new(root / f'{persona}-history-shape.json', {'container_type': type(raw).__name__,
            'top_level_keys': list(raw) if isinstance(raw, dict) else [],
            'history_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        # The schema is checked explicitly instead of guessing message fields.
        sessions = raw['sessions'] if isinstance(raw, dict) and 'sessions' in raw else raw
        if not isinstance(sessions, list):
            raise ValueError('History schema differs; do not infer or rewrite sources')
        database = root / f'{persona}.db'
        HouseholdApplication.initialize(database, encrypted=True, backend='file')
        scope = AuthorityScope(f'qualification:{persona}', 'agent', f'qualification:{persona}')
        authority = {'principal_id': 'history-import', 'subject_id': scope.subject_id,
                     'agent_id': scope.agent_id, 'workspace_id': scope.workspace_id,
                     'scopes': ('history_import:review', 'procedure:review'),
                     'assurance': 'explicit_benchmark_operator_configuration'}
        memory = Memory(database, auto_vectors=False, retain_query_text=False,
                        review_authorities=(authority,))
        try:
            receipts, messages = [], []
            for index, session in enumerate(sessions[:args.histories_per_persona]):
                if len(session['messages']) != 1:
                    raise ValueError('Expected the authenticated single-message release')
                text = f"[{session['narrative_date']}] {session['messages'][0].strip()}"
                messages.append(text)
                request = EpisodeIngestRequest(episode_id=f'history-{index}',
                    idempotency_key=f'history-{index}', scope=scope,
                    parts=(EpisodePart(part_id='dated-message', ordinal=0, kind='text',
                        source_type='user_message', content=text,
                        content_sha256='sha256:' + hashlib.sha256(text.encode()).hexdigest()),),
                    binding_method='host_asserted', binding_assurance='host_asserted',
                    session_id=str(index), retain_body=True,
                    source_observation_granularity='sentence')
                receipts.append(memory.form_context_episode(request, history_import_principal='history-import'))
            frozen = memory.freeze_context_engine(scope)
            generation = memory.context_generation(scope)
            before = memory.memory_checkpoint(scope)
            package = memory.prepare_context_v3(ContextRequestV3(
                context_id='qualification', request_id='qualification', scope=scope,
                query=messages[0], profile_id='context-fast', mode='active',
                generation=int(generation['canonical_generation']),
                budget=RetrievalBudget(total_candidates=200, context_bytes=32000)))
            after = memory.memory_checkpoint(scope)
            if before != after or frozen['source_count'] != len(messages) or not package.context:
                raise RuntimeError('Source retention or read-only retrieval qualification failed')
            results[persona] = {'ingestion_receipts': receipts, 'frozen': frozen,
                'checkpoint_before': before, 'checkpoint_after': after,
                'retrieval': package.to_dict(), 'canonical_unchanged': before == after}
        finally:
            memory.close()
    save_new(root / 'result.json', {'diagnostic_only': True, 'paid_model_calls': 0,
        'test_requests_or_labels_used': False, 'native_hermes_qualified': False,
        'atmem_version': version('atmem'), 'history_import_authority': 'explicit scoped operator',
        'by_persona': results})
    print(json.dumps({'diagnostic_only': True, 'paid_model_calls': 0,
        'sources_by_persona': {p: row['frozen']['source_count'] for p, row in results.items()}}))


if __name__ == '__main__':
    main()
