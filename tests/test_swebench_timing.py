from benchmarks.code_replay.swebench_timing import context_stage


def event(kind, time, arm='atmem_structure'):
    return {'envelope': {'event_type': kind, 'event_time': time, 'payload': {'arm': arm}}}


def test_context_preparation_is_not_hidden_in_solve_only_timing():
    rows = [event('trial.transport_control', '2026-10-19T10:00:00+00:00'),
            event('trial.context_prepared', '2026-10-19T10:00:12+00:00'),
            event('trial.started', '2026-10-19T10:00:13+00:00')]
    assert context_stage(rows, 'atmem_structure') == 12
    assert context_stage(rows, 'no_memory') is None
    assert context_stage(rows[:-1], 'atmem_structure') is None
    assert context_stage([rows[0], rows[-1]], 'atmem_structure') == 0
    assert context_stage([rows[0], rows[-1]], 'atmem_structure', automatic_expected=True) is None
    assert context_stage([rows[1], rows[-1]], 'atmem_structure') is None
    assert context_stage([rows[0], rows[1], rows[-1], rows[-1]], 'atmem_structure') is None
