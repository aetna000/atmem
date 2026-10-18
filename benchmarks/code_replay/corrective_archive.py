"""CD1 full evidence collection using the existing encrypted archive protocol."""
import ast
import inspect

from benchmarks.code_replay.corrective_controls import exact_changes, PREFIX

QUALIFICATION_IDENTITIES = ('pylint-dev__pylint-6358', 'pylint-dev__pylint-6517',
    'pylint-dev__pylint-6820', 'pylint-dev__pylint-7277', 'pyvista__pyvista-4853')
QUALIFICATIONS = ('external-windows-source-storage-qualification-v1-20261018',
    'external-windows-typed-query-qualification-v1-20261018',
    'external-windows-typed-query-qualification-v1-20261018-local-transport',
    'external-windows-typed-query-qualification-v1-20261018-mcp-import-continuation',
    'external-windows-typed-query-qualification-v1-20261018-owned-state-continuation')


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
            raise ValueError('all fresh CD1 boundary qualifications required')
        runs.add(root); runs.update(r['task_run'] for r in rows)
    for root in QUALIFICATIONS:
        rows = of(read(root), 'external.compatibility_case_result')
        if (len(rows) != 5 or {r['identity'] for r in rows} != set(QUALIFICATION_IDENTITIES)
                or any(r['model_calls'] != 0 for r in rows)):
            raise ValueError('all real-source outcomes required, including setup failures')
        runs.add(root); runs.update(r['task_run'] for r in rows)
    prior = lock['staging_manifest']['prior_manifest_run']
    original, = of(read(prior), 'external.confirmation_manifest_frozen')
    if len(original['blocks']) != 38:
        raise ValueError('full original staging history required')
    # New slot order differs: retain the original manifest's slots, never map
    # new slots onto old issues or silently omit prior failed staging cases.
    runs.add(prior)
    runs.update(prior+'-block-'+str(b['slot']) for b in original['blocks'])
    runs.update({PREFIX+'preparation-v1-20261018', PREFIX+'execution-waiter-v1-20261018',
        'external-windows-product-build-typed-query-v1-20261018',
        'external-windows-typed-query-mcp-continuation-waiter-v1-20261018'})
    return runs


def archive_source(original):
    node = next(n for n in ast.parse(original).body if isinstance(n, ast.FunctionDef) and n.name == 'required_runs')
    old = ast.get_source_segment(original, node)
    source = original.replace(old, inspect.getsource(required_runs).rstrip(), 1)
    changes = [
        ("RUN = 'external-windows-confirmation-v3-archive-v1-20261018'", 'RUN = '+repr(PREFIX+'archive-v1-20261018'), 1),
        ("COLLECTION = 'atmem-code-confirmation-v3-protected-collection-v1'", "COLLECTION = 'atmem-code-corrective-development-protected-collection-v1'", 1),
        ("LOCK = 'external-windows-confirmation-v3-execution-lock-v1-20261018'", 'LOCK = '+repr(PREFIX+'execution-lock-v1-20261018'), 1),
        ("MODELS = 'external-windows-confirmation-v3-models-v1-20261018'", 'MODELS = '+repr(PREFIX+'models-v1-20261018'), 1),
        ("GRADING = 'external-windows-confirmation-v3-grading-v1-20261018'", 'GRADING = '+repr(PREFIX+'grading-v1-20261018'), 1),
        ("PUBLIC = 'external-windows-confirmation-v3-public-recovery-v1-20261018'", 'PUBLIC = '+repr(PREFIX+'public-recovery-v1-20261018'), 1),
        ("REPORT = 'external-windows-confirmation-v3-comparison-v1-20261018'", 'REPORT = '+repr(PREFIX+'comparison-v1-20261018'), 1),
        ("FINISH = 'external-windows-confirmation-v3-postprocessing-v1-20261018'", 'FINISH = '+repr(PREFIX+'postprocessing-v1-20261018'), 1),
        ("'external-windows-confirmation-v3-staging-v1-20261018'", repr(PREFIX+'staging-v1-20261018'), 1),
        ("'external-windows-confirmation-v3-process-scope-v1-20261018'", repr(PREFIX+'process-scope-v1-20261018'), 1),
        ('len(expected) != 76', 'len(expected) != 38', 1),
        ('len(rows) != 76', 'len(rows) != 38', 1),
        ("len({(r['slot'], r['arm']) for r in rows}) != 76", "len({(r['slot'], r['arm']) for r in rows}) != 38", 1),
        ('!= (76, 76, 76)', '!= (38, 38, 38)', 1),
    ]
    source = exact_changes(source, changes)
    constants = ('PREFIX='+repr(PREFIX)+'\nQUALIFICATIONS='+repr(QUALIFICATIONS)
                 +'\nQUALIFICATION_IDENTITIES='+repr(QUALIFICATION_IDENTITIES)+'\n')
    marker = "if __name__ == '__main__': main()"
    if source.count(marker) != 1:
        raise ValueError('exact archive entry point required')
    source = source.replace(marker, constants+'\n'+marker)
    ast.parse(source, feature_version=(3, 10))
    return source


def request_audit_source(original):
    """Use the unchanged original-request verifier, with CD1's complete count."""
    nodes = {n.name: n for n in ast.parse(original).body if isinstance(n, ast.FunctionDef)}
    names = ('recover_dispatch', 'bound_request', 'audit_collection')
    if any(name not in nodes for name in names):
        raise ValueError('exact original request-audit functions required')
    source = 'from hashlib import sha256\nimport json,re\n\n'+'\n\n'.join(
        ast.get_source_segment(original, nodes[name]) for name in names)
    return exact_changes(source, [
        ('len(grades)!=76', 'len(grades)!=38', 1),
        ('len(by_cell)!=76', 'len(by_cell)!=38', 1),
        ("'verified_original_requests':76", "'verified_original_requests':38", 1),
    ])
