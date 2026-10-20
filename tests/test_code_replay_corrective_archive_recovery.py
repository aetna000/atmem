import pytest

from benchmarks.code_replay import corrective_archive_recovery as recovery


def test_empty_export_refuses_partial_keys_and_wrong_journal(tmp_path, monkeypatch):
    monkeypatch.setattr(recovery, 'ROOT', tmp_path)
    output = tmp_path/'corrective-development-archive-v1'; output.mkdir()
    keys = tmp_path/'corrective-development-archive-keys-v1'; keys.mkdir()
    plan = {'output': str(output), 'internal_key_root': str(keys)}
    rows = [{'envelope': {'event_type': 'external.v3_archive_planned', 'payload': plan}}]
    assert recovery.empty_export(rows, output, keys) == plan
    with pytest.raises(ValueError): recovery.empty_export(rows+rows, output, keys)
    (keys/'partial-key').touch()
    with pytest.raises(ValueError): recovery.empty_export(rows, output, keys)


def test_recovery_loads_only_original_sources_and_preserves_exact_membership():
    import inspect
    source = inspect.getsource(recovery.main)
    assert "post_plan['postprocess_programs']" in source
    assert "plan['driver_source']" in source
    assert "sorted(runs) != plan['runs']" in source
    assert 'subprocess' not in source
    assert "'private_grades_repeated': 0" in source
