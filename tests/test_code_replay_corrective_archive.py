import inspect
import ast

import pytest

from benchmarks.code_replay import confirmation_v3_archive
from benchmarks.code_replay.corrective_archive import archive_source, PREFIX, QUALIFICATIONS, QUALIFICATION_IDENTITIES
from benchmarks.code_replay.corrective_archive import request_audit_source
from tests.test_code_replay_confirmation_v3_report import fixture


def archive_namespace():
    scope = {'__name__': 'corrective_archive_test'}
    exec(compile(archive_source(inspect.getsource(confirmation_v3_archive)), '<CD1-archive>', 'exec'), scope)
    return scope


def test_all_current_cells_and_original_failures_are_required_after_reordering():
    scope = archive_namespace()
    rows, blocks = fixture(); rows, blocks = rows[:38], blocks[:19]
    rows = [{**r, 'task_run': f"case-{r['slot']}-{r['arm']}", 'qualified': True, 'model_calls': 0} for r in rows]
    lock = {'staging_manifest': {'blocks': blocks, 'source_descriptors': {}, 'prior_manifest_run': 'original'},
            'staged_blocks': [], 'grade_plans': {}}
    records = {'original': [{'envelope': {'event_type': 'external.confirmation_manifest_frozen', 'payload': {
        'blocks': [{'slot': i} for i in reversed(range(38))]}}}]}
    for root, kind in [(PREFIX+'mcp-readiness-v1-20261018', 'external.v3_mcp_case_summary'),
                       (PREFIX+'sandbox-v1-20261018', 'external.v3_sandbox_case_summary')]:
        records[root] = [{'envelope': {'event_type': kind, 'payload': r}} for r in rows]
    for root in QUALIFICATIONS:
        records[root] = [{'envelope': {'event_type': 'external.compatibility_case_result', 'payload': {
            'identity': identity, 'task_run': root+'-'+identity, 'model_calls': 0, 'qualified': False}}}
            for identity in QUALIFICATION_IDENTITIES]
    runs = scope['required_runs'](lock, rows, rows, rows, records.__getitem__)
    assert 'original-block-37' in runs
    assert all(root+'-'+QUALIFICATION_IDENTITIES[0] in runs for root in QUALIFICATIONS)
    assert PREFIX+'execution-waiter-v1-20261018' in runs
    with pytest.raises(ValueError):
        scope['required_runs'](lock, rows[:-1], rows, rows, records.__getitem__)
    records[QUALIFICATIONS[1]].pop()
    with pytest.raises(ValueError):
        scope['required_runs'](lock, rows, rows, rows, records.__getitem__)


def test_recovery_keeps_original_full_stream_verifiers_and_existing_crypto():
    source = archive_source(inspect.getsource(confirmation_v3_archive))
    scope = archive_namespace()
    def function(text, name):
        node = next(n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef) and n.name == name)
        return ast.get_source_segment(text, node)
    assert function(source, 'validate_run') == function(inspect.getsource(confirmation_v3_archive), 'validate_run')
    assert "!= (38, 38, 38)" in source
    assert "from benchmarks.code_replay.windows_archive import recover_snapshot" in source
    assert "principal.authorize(EvidenceOperation.ENCRYPTED_EXPORT, target)" in source
    assert "source_vault_opened': False" in source
    with pytest.raises((ValueError, StopIteration)):
        archive_source('unknown')


def test_original_dispatch_binding_and_crypto_helpers_are_not_redefined():
    from benchmarks.code_replay import confirmation_v3_dispatch_audit
    source = request_audit_source(inspect.getsource(confirmation_v3_dispatch_audit))
    namespace = {'__name__': 'request_audit_test'}
    exec(compile(source, '<CD1-request-audit>', 'exec'), namespace)
    assert "'verified_original_requests':38" in source
    assert 'operational_evidence' not in source
    assert 'def main' not in source
    for name in ('recover_dispatch', 'bound_request'):
        original_node = next(n for n in ast.parse(inspect.getsource(confirmation_v3_dispatch_audit)).body
                             if isinstance(n, ast.FunctionDef) and n.name == name)
        assert ast.get_source_segment(inspect.getsource(confirmation_v3_dispatch_audit), original_node) in source
