"""Complete CD2 evidence membership, using the existing encrypted archive format."""
import ast
import inspect

from benchmarks.code_replay import corrective_archive
from benchmarks.code_replay import query_nomination_screen as screen


def required_runs(lock, cases, grades, public, read):
    runs = core_runs(lock, cases, grades, public)
    expected = {(b['slot'], a): (b['instance_id'], b['repeat'])
                for b in lock['staging_manifest']['blocks'] for a in b['order']}
    for root, kind in [(PREFIX+'mcp-readiness-v1-20261018', 'external.v3_mcp_case_summary'),
                       (PREFIX+'sandbox-v1-20261018', 'external.v3_sandbox_case_summary')]:
        rows = of(read(root), kind)
        if (len(rows) != 38 or len({(r['slot'], r['arm']) for r in rows}) != 38
                or any(expected.get((r['slot'], r['arm'])) != (r['instance_id'], r['repeat'])
                       or r['qualified'] is not True or r['model_calls'] != 0 for r in rows)):
            raise ValueError('all fresh CD2 boundary controls required')
        runs.add(root); runs.update(r['task_run'] for r in rows)
    qualification = 'external-windows-query-nomination-qualification-v1-20261018'
    rows = of(read(qualification), 'external.compatibility_case_result')
    end, = of(read(qualification), 'external.compatibility_qualification_completed')
    if (end['qualified'] is not True or len(rows) != 5
            or {r['identity'] for r in rows} != set(QUALIFICATION_IDENTITIES)
            or any(r['qualified'] is not True or r['model_calls'] != 0
                   or r['foreign_scope_denied'] is not True for r in rows)):
        raise ValueError('five actual fresh installed repository controls required')
    runs.add(qualification); runs.update(r['task_run'] for r in rows)
    replay = 'external-windows-query-nomination-installed-replay-v1-20261018'
    end, = of(read(replay), 'external.query_nomination_installed_replay_completed')
    rows = of(read(replay), 'external.query_nomination_installed_replay_case')
    if (end['qualified'] is not True or end['model_calls'] != 0 or end['identities'] != 19
            or len(rows) != 19 or len({r['identity'] for r in rows}) != 19
            or any(r['matches'] is not True for r in rows)):
        raise ValueError('all actual installed query replays required')
    runs.add(replay)
    prior = lock['staging_manifest']['prior_manifest_run']
    original, = of(read(prior), 'external.confirmation_manifest_frozen')
    if len(original['blocks']) != 38:
        raise ValueError('complete original source staging history required')
    runs.add(prior)
    runs.update(prior+'-block-'+str(b['slot']) for b in original['blocks'])
    # The candidate build plan contains all full Mac-produced static records,
    # clearly labelled by origin, as well as its complete frozen source job.
    runs.update({PREFIX+'preparation-v1-20261018', PREFIX+'execution-v1-20261018',
                 PREFIX+'archive-waiter-v1-20261018',
                 'external-windows-product-build-query-nomination-v1-20261018'})
    return runs


def archive_source(original):
    source = screen.reprofile(corrective_archive.archive_source(original))
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == 'required_runs')
    old = ast.get_source_segment(source, node)
    source = source.replace(old, inspect.getsource(required_runs).rstrip(), 1)
    before = 'atmem-code-corrective-development-protected-collection-v1'
    if source.count(before) != 1:
        raise ValueError('exact previous archive collection constant required')
    source = source.replace(before, 'atmem-code-query-nomination-development-protected-collection-v1')
    ast.parse(source, feature_version=(3, 10))
    return source
