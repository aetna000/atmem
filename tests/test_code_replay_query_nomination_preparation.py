import pytest

from benchmarks.code_replay import query_nomination_preparation as preparation
from benchmarks.code_replay import run_evidence


def event(kind, payload):
    return {'envelope': {'event_type': kind, 'payload': payload}}


@pytest.mark.parametrize('failed_phase', [None, 'readiness'])
def test_preparation_runs_all_controls_in_order_and_stops_before_models(monkeypatch, failed_phase):
    phases = [
        ('staging', 'external.confirmation_v3_staging_completed', 'all_38_cases_staged'),
        ('readiness', 'external.v3_mcp_readiness_completed', 'all_38_cases_qualified'),
        ('sandbox', 'external.v3_sandbox_completed', 'all_38_cases_qualified'),
        ('process', 'external.v3_process_scope_completed', 'qualified'),
        ('prepare', 'external.v3_execution_preparation_completed', 'all_38_initial_sources_verified'),
    ]
    records = {
        'qualification': [event('external.compatibility_qualification_completed', {
            'qualified': True, 'results': [{'model_calls': 0} for _ in range(5)]})],
        'replay': [event('external.query_nomination_installed_replay_completed', {
            'qualified': True, 'identities': 19})],
    }
    for phase, kind, gate in phases:
        records['phase-' + phase] = [event(kind, {gate: phase != failed_phase, 'model_calls': 0})]
    class Vault:
        def inspect(self, principal, run):
            return records.get(run, [])
        def capture(self, *, run_id, kind, principal, payload):
            records.setdefault(run_id, []).append(event(kind, payload))
            return {}
    monkeypatch.setattr(run_evidence, 'operational_evidence', lambda *a, **k: Vault())
    sources = {phase: "RUN='phase-" + phase + "'\ndef main():pass\n" for phase, _, _ in phases}
    sources['models'] = "raise AssertionError('models must never run during preparation')"
    monkeypatch.setattr(preparation, 'job', {
        'run': 'fresh-preparation', 'qualification': 'qualification', 'replay': 'replay',
        'support': {}, 'sources': sources, 'protocol': 'frozen', 'configuration_source': 'fixed',
    }, raising=False)
    if failed_phase:
        with pytest.raises(ValueError, match='phase failed'):
            preparation.remote()
    else:
        preparation.remote()
    rows = records['fresh-preparation']
    started = [r['envelope']['payload']['phase'] for r in rows
               if r['envelope']['event_type'].endswith('_phase_started')]
    assert started == (['staging', 'readiness'] if failed_phase else [r[0] for r in phases])
    done = [r for r in rows if r['envelope']['event_type'] == 'external.query_nomination_preparation_completed']
    assert len(done) == (0 if failed_phase else 1)
