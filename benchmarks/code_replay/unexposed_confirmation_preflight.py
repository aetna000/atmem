"""Freeze metadata only for all remaining unexposed pinned repository groups."""
from hashlib import sha256
import json
import os
from pathlib import Path

from benchmarks.code_replay import external_catalog as catalog
from benchmarks.code_replay.query_nomination_preview import evidence

RUN = 'external-unexposed-confirmation-pool-v4-preflight-20261018'
SEED = 'atmem-unexposed-repository-confirmation-pool-20261018-v4'
REPOSITORIES = ('astropy/astropy', 'django/django', 'matplotlib/matplotlib',
                'scikit-learn/scikit-learn', 'sympy/sympy')
EXCLUDED = tuple(catalog.REPOSITORIES)+tuple(catalog.CONFIRMATION_REPOSITORIES)+tuple(catalog.ELIGIBILITY_REPOSITORIES)


def selection(tree):
    observed = {row['path'].rsplit('-', 1)[0].replace('__', '/')
                for row in tree['tree'] if row.get('type') == 'tree'}
    if observed != set(EXCLUDED) | set(REPOSITORIES) or len(set(EXCLUDED)) != 13:
        raise ValueError('exact pinned eighteen-group catalog and thirteen prior groups required')
    # Reuse the original identity-only ordering; this profile explicitly freezes
    # eight feasibility candidates, not four presumed runnable model tasks.
    original = catalog.catalog(tree, seed=SEED, per_repo=4, repositories=REPOSITORIES)
    selected = []
    entries = {row['path']: row['sha'] for row in tree['tree'] if row.get('type') == 'tree'}
    for repo in REPOSITORIES:
        ordered = original['ordered_candidate_pools'][repo]
        if len(ordered) < 8:
            raise ValueError('eight fixed feasibility identities required per new group')
        selected.extend({'instance_id': identity, 'repo': repo, 'task_tree': entries[identity]}
                        for identity in ordered[:8])
    return {**original, 'format': 'atmem-unexposed-confirmation-pool-v4',
            'per_repo': 8, 'selected': selected, 'excluded_repository_groups': sorted(EXCLUDED),
            'sampling_stage': 'feasibility_candidates_not_final_model_tasks',
            'final_model_tasks_per_repository': 4,
            'content_paths_permitted': sorted(catalog.ALLOWED_FILES)}


def metadata(item, fetch=catalog.api):
    tree = fetch('git/trees/'+item['task_tree'])
    if tree.get('sha') != item['task_tree'] or tree.get('truncated') is not False:
        raise ValueError('complete pinned task subtree required')
    entries = [r for r in tree['tree'] if r['path'] in catalog.ALLOWED_FILES]
    if len(entries) != 2 or {r['path'] for r in entries} != catalog.ALLOWED_FILES:
        raise ValueError('exact metadata and recipe entries required')
    blobs = {row['path']: catalog.checked_blob(row, fetch=fetch) for row in entries}
    return {'metadata': catalog.task_metadata(blobs['task.yaml'], item), 'task_tree': tree,
            'files': {name: {'git_blob': next(r['sha'] for r in entries if r['path'] == name),
                             'sha256': sha256(raw).hexdigest(),
                             'content_utf8': raw.decode('utf-8')}
                      for name, raw in blobs.items()}}


def main():
    os.environ['ATMEM_BENCHMARK_PER_RUN_VAULTS'] = '1'
    vault, principal = evidence(RUN)
    if vault.inspect(principal, RUN):
        raise ValueError('preflight already attempted; inspect original evidence')
    def save(kind, payload):
        return vault.capture(run_id=RUN, kind=kind, principal=principal, payload=payload)
    save('external.unexposed_preflight_planned', {'driver_source': Path(__file__).read_text(),
        'protocol': Path('specs/042-atmem-code/unexposed-confirmation-pool-v4.md').read_text(),
        'model_calls': 0, 'permitted_files': sorted(catalog.ALLOWED_FILES)})
    root = catalog.api('git/trees/'+catalog.REVISION)
    tasks = [r for r in root['tree'] if r['path'] == 'tasks' and r['type'] == 'tree']
    if root.get('truncated') is not False or len(tasks) != 1 or tasks[0]['sha'] != catalog.TASK_TREE:
        raise ValueError('task tree must match pinned revision')
    tree = catalog.api('git/trees/'+catalog.TASK_TREE)
    selected = selection(tree)
    save('external.unexposed_selection_frozen', {'selection': selected,
        'selection_sha256': catalog.digest(selected), 'catalog_root': root, 'catalog_tree': tree,
        'model_calls': 0, 'individual_task_content_opened': False})
    results = []
    for item in selected['selected']:
        try:
            result = {**item, **metadata(item), 'metadata_verified': True, 'environment_qualified': False}
        except Exception as exc:
            result = {**item, 'metadata_verified': False, 'environment_qualified': False,
                      'failure': type(exc).__name__+': '+str(exc)}
        save('external.unexposed_metadata_result', result)
        results.append(result)
        print(json.dumps({'instance_id': item['instance_id'], 'metadata_verified': result['metadata_verified']}), flush=True)
    summary = {'selection_sha256': catalog.digest(selected), 'selected': len(results),
        'metadata_verified': sum(r['metadata_verified'] for r in results),
        'environment_qualified': 0, 'model_calls': 0, 'content_paths_opened': sorted(catalog.ALLOWED_FILES),
        'confirmation_complete': False}
    save('external.unexposed_metadata_completed', summary)
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
