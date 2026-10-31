"""Offline safety checks for the full-campaign recovery path."""
import json
import shutil
import sys
import time
from types import ModuleType

import pytest

from benchmarks.dolphinbench import full_recovery_020 as recovery
from benchmarks.dolphinbench.readiness import pin, save
from benchmarks.dolphinbench.recording import BudgetLedger
from benchmarks.dolphinbench.recording import fingerprint
from benchmarks.dolphinbench.pilot_recovery import execute_once


def test_source_transition_allows_only_explicit_repair_and_preserves_science(tmp_path, monkeypatch):
    old, new = tmp_path / 'old', tmp_path / 'new'
    for root, content in ((old, 'old exporter'), (new, 'new exporter')):
        path = root / 'benchmarks/dolphinbench/export.py'
        path.parent.mkdir(parents=True)
        path.write_text(content)
    for name in ('test_dolphinbench_export.py', 'test_dolphin_full_recovery_020.py'):
        path = new / 'tests/benchmarking' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('fixture test')
    before, after = tmp_path / 'before.json', tmp_path / 'after.json'
    save(before, [pin(old / 'benchmarks/dolphinbench/export.py')])
    new_pins = [pin(new / 'benchmarks/dolphinbench/export.py'),
                *(pin(p) for p in (new / 'tests/benchmarking').glob('*.py'))]
    save(after, new_pins)
    common = {'settings': {'model': 'fixed'}, 'inputs': {'options': {'path': '/fixed', 'sha256': 'a'}}}
    first = {**common, 'inputs': {**common['inputs'], 'source_manifest': pin(before)}}
    second = {**common, 'inputs': {**common['inputs'], 'source_manifest': pin(after)}}
    monkeypatch.setattr(recovery, 'ROOT', new)
    assert recovery.source_transition(first, second)[0]['path'] == 'benchmarks/dolphinbench/export.py'
    second['settings'] = {'model': 'changed'}
    with pytest.raises(ValueError, match='scientific'):
        recovery.source_transition(first, second)
    second['settings'] = common['settings']
    unrelated = new / 'unrelated.py'; unrelated.write_text('unexpected')
    after.unlink(); save(after, [*new_pins, pin(unrelated)])
    second['inputs']['source_manifest'] = pin(after)
    with pytest.raises(ValueError, match='outside bounded'):
        recovery.source_transition(first, second)


def test_budget_enforces_original_cap_and_immutable_inherited_rows(tmp_path):
    campaign = {'id': 'fixture', 'cap_usd': 20}
    current = tmp_path / 'budget.db'
    book = BudgetLedger(current, cap_usd=20, identity=campaign)
    book.reserve('original', phase='judge', request={'fixture': True}, maximum_usd=1)
    book.complete('original', actual_usd=.25, usage={'prompt_tokens': 1, 'completion_tokens': 1}, response={'ok': True})
    book.close()
    inherited = tmp_path / 'inherited.db'; shutil.copyfile(current, inherited)
    assert recovery.check_budget(current, campaign, inherited=inherited) == 250000
    book = BudgetLedger(current, cap_usd=20, identity=campaign)
    book.reserve('pending', phase='judge', request={'fixture': 2}, maximum_usd=1)
    book.close()
    with pytest.raises(ValueError, match='Unresolved inherited'):
        recovery.check_budget(current, campaign, inherited=inherited)
    assert recovery.check_budget(current, campaign, inherited=inherited, inflight_since=time.time()-60) == 1250000
    with pytest.raises(ValueError, match='identity or cap'):
        recovery.check_budget(current, {**campaign, 'cap_usd': 21})


def test_preflight_rejects_unfinished_actions_and_never_resets_workspace(tmp_path, monkeypatch):
    ledger = tmp_path / 'docs/benchmarks/evidence/dolphin-execution-audit-20261025/task-ledger.jsonl'
    ledger.parent.mkdir(parents=True)
    ledger.write_text(''.join(json.dumps({'id': f'morgan/{i:03}'}) + '\n' for i in range(600)))
    monkeypatch.setattr(recovery, 'ROOT', tmp_path)
    output = tmp_path / 'epoch'; output.mkdir()
    recovery.preflight_resume(output)
    marker = output / 'tests/morgan/020.inflight'; marker.parent.mkdir(parents=True); marker.write_text('{}')
    with pytest.raises(ValueError, match='Uncertain saved interaction'):
        recovery.preflight_resume(output)
    assert marker.exists()
    marker.unlink()
    workspace = output / 'apps/morgan/021'; workspace.mkdir(parents=True); (workspace / 'state.json').write_text('{}')
    with pytest.raises(ValueError, match='workspace cannot be reset'):
        recovery.preflight_resume(output)
    assert (workspace / 'state.json').exists()


def test_epoch_preserves_completed_rows_and_grades_interrupted_task_without_replay(tmp_path, monkeypatch):
    parent, output = tmp_path / 'parent', tmp_path / 'epoch'; parent.mkdir()
    specs = [{'id': i, 'grade': {'config': {'assertions': [{}]}}} for i in range(1, 601)]
    release = {'morgan': {'tests': specs}}
    submission, runner = ModuleType('harness.submission'), ModuleType('harness.runner')
    submission.read_release = lambda _: release
    runner.digest = fingerprint
    monkeypatch.setitem(sys.modules, 'harness.submission', submission)
    monkeypatch.setitem(sys.modules, 'harness.runner', runner)
    old = {'inputs': {}, 'profile': 'fixed'}
    save(parent / 'execution-condition.json', old)
    options = tmp_path / 'options.json'; save(options, {'campaign_identity': {'fixture': True}})
    condition = {'inputs': {'options': pin(options)}, 'bindings': {'upstream_root': str(tmp_path)},
                 'budget': {'caps_usd': {'full': 20}}}
    condition_path = tmp_path / 'condition.json'; save(condition_path, condition)
    monkeypatch.setattr(recovery, 'admit', lambda *args: condition)
    monkeypatch.setattr(recovery, 'load_condition', lambda *args: condition)
    monkeypatch.setattr(recovery, 'source_transition', lambda *args: [{'path': 'fixture'}])
    for i in range(1, 20):
        key = f'morgan/{i:03}'
        execution = parent / 'tests' / (key + '.json'); save(execution, {'fixture': i})
        save(parent / 'grades' / (key + '.json'), {'checks': [{'check': 0, 'passed': i != 2}]})
        save(parent / 'dispatch-intents' / (key + '.json'), {'fixture': True})
        save(parent / 'grade-intents' / (key + '.json'), {'execution': pin(execution)})
        directory = parent / 'native/tests' / key / 'app-evidence'
        save(directory / 'state.json', {'fixture': i}); save(directory / 'calls.jsonl', {'fixture': i})
        save(directory / 'outcome.json', {'completed': True, 'artifacts': [pin(directory / 'state.json'), pin(directory / 'calls.jsonl')]})
    save(parent / 'dispatch-intents/morgan/020.json', {'condition': pin(parent / 'execution-condition.json')})
    save(parent / 'tests/morgan/020.inflight', {'source_sha256': fingerprint(specs[19])})
    witness = tmp_path / 'witness.json'; save(witness, {'fixture': True})
    campaign = {'fixture': True, 'cap_usd': 20}
    book = BudgetLedger(parent / 'budget.db', cap_usd=20, identity=campaign); book.close()
    proof_file = pin(witness)
    reconstructed = {'row': {'persona': 'morgan', 'test_id': '020'}, 'attempts': []}
    proof = {'task': recovery.TASK, 'model_or_app_replay': False, 'execution_sha256': fingerprint(reconstructed),
             **{name: proof_file for name in ('api_witness', 'process', 'context_delivery', 'app_intent', 'app_outcome', 'state', 'log')},
             'snapshots': [proof_file]}
    monkeypatch.setattr(recovery, 'reconstruct', lambda *args: (reconstructed, proof.copy()))
    transition = recovery.prepare(parent, output, condition_path, tmp_path / 'receipts', witness)
    assert len(transition['imported_grade_ids']) == 19
    assert recovery.progress(output) == {'graded': 19, 'total': 600, 'passed': 18, 'failed': 1}
    assert not (output / 'tests/morgan/020.inflight').exists()
    assert (parent / 'tests/morgan/020.inflight').exists()
    assert (output / 'grades/morgan/002.json').read_bytes() == (parent / 'grades/morgan/002.json').read_bytes()
    class FakeRunner:
        def _execute(self, *args): raise AssertionError('Saved interaction must never be replayed')
        def _grade(self, spec, evidence):
            assert evidence == reconstructed
            return {'checks': [{'check': 0, 'passed': True}]}
    execute_once(FakeRunner(), output, 'morgan', specs[19], boundary=lambda: recovery.verify_epoch(output, condition_path))
    assert (output / 'grades/morgan/020.json').exists()
    assert not (parent / 'grades/morgan/020.json').exists()
    assert recovery.progress(output) == {'graded': 20, 'total': 600, 'passed': 19, 'failed': 1}
    recovery.verify_epoch(output, condition_path)
