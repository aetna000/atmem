import pytest

from benchmarks.code_replay import query_nomination_execution as execution
from benchmarks.code_replay import run_evidence


def event(kind, payload):
    return {'envelope': {'event_type': kind, 'payload': payload}}


@pytest.mark.parametrize('attempts', [37, 38])
def test_private_postprocessing_requires_every_original_model_capture(monkeypatch, attempts):
    sources = {'models': "RUN='models'\ndef main():pass\n",
               'finish': "RUN='post'\ndef main():pass\n",
               'grade': 'grade', 'report': 'report', 'retain': 'retain'}
    records = {
        'preparation': [
            event('external.query_nomination_preparation_completed', {
                'qualified': True, 'model_calls': 0,
                'results': [{'phase': p} for p in ('staging', 'readiness', 'sandbox', 'process', 'prepare')]}),
            event('external.query_nomination_preparation_planned', {'job': {'sources': sources, 'support': {}}}),
        ],
        'external-windows-corrective-development-postprocessing-v1-20261018': [
            event('external.v3_postprocessing_planned', {'bridge_source': 'retained original'})],
        'models': [event('external.v3_models_completed', {'attempts_completed': attempts})],
        'post': [event('external.v3_postprocessing_completed', {'comparison_and_public_recovery': True})],
    }
    class Vault:
        def inspect(self, principal, run):
            return records.get(run, [])
        def capture(self, *, run_id, kind, principal, payload):
            records.setdefault(run_id, []).append(event(kind, payload))
            return {}
    monkeypatch.setattr(run_evidence, 'operational_evidence', lambda *a, **k: Vault())
    monkeypatch.setattr(execution, 'job', {'run': 'fresh', 'preparation': 'preparation', 'program': 'retained'}, raising=False)
    if attempts == 37:
        with pytest.raises(ValueError, match='all 38'):
            execution.remote()
    else:
        execution.remote()
    rows = records['fresh']
    phases = [r['envelope']['payload']['phase'] for r in rows
              if r['envelope']['event_type'] == 'external.query_nomination_execution_phase_started']
    assert phases == (['models', 'postprocess'] if attempts == 38 else ['models'])
    done = [r['envelope']['payload'] for r in rows
            if r['envelope']['event_type'] == 'external.query_nomination_execution_completed']
    if done:
        assert done[0]['goal_complete'] is False
        assert done[0]['archive_acceptance'] == 'still required'
