"""Bind fresh CD1 execution to the exercised source, scope and budget gates."""
from benchmarks.code_replay.corrective_controls import exact_changes, PREFIX, CASE_ROOT

SUPPORT_NAMES = ('benchmarks.code_replay.confirmation_v3_process_scope',
                 'benchmarks.code_replay.confirmation_v3_capture',
                 'benchmarks.code_replay.confirmation_v3_lock')


def supporting_sources():
    import inspect
    from benchmarks.code_replay import confirmation_v3_process_scope, confirmation_v3_capture, confirmation_v3_lock
    from benchmarks.code_replay.corrective_controls import process_source
    return dict(zip(SUPPORT_NAMES, (
        process_source(inspect.getsource(confirmation_v3_process_scope)),
        source_capture(inspect.getsource(confirmation_v3_capture)),
        case_lock(inspect.getsource(confirmation_v3_lock)),
    )))


def load_support(sources):
    """Operator-process-only modules; full sources must be retained in its lock."""
    import sys
    import types
    if set(sources) != set(SUPPORT_NAMES):
        raise ValueError('exact three CD1 operator boundary modules required')
    for name in SUPPORT_NAMES:
        module = types.ModuleType(name)
        module.__file__ = '<protected-CD1-support:'+name+'>'
        sys.modules[name] = module
        exec(compile(sources[name], module.__file__, 'exec'), module.__dict__)
        parent, attribute = name.rsplit('.', 1)
        setattr(sys.modules[parent], attribute, module)


def source_capture(source):
    return exact_changes(source, [
        ('/home/jt/atmem-benchmark-runtime-20261018/confirmation-stage-v3/block-', CASE_ROOT, 1),
        ('exact fresh v3 source origin required', 'exact fresh CD1 source origin required', 1),
    ])


def case_lock(source):
    return exact_changes(source, [
        ('len(expected)!=76', 'len(expected)!=38', 1),
        ('len(rows)!=76', 'len(rows)!=38', 1),
        ("len({(r['slot'],r['arm']) for r in rows})!=76", "len({(r['slot'],r['arm']) for r in rows})!=38", 1),
        ('all seventy-six distinct frozen cells required', 'all thirty-eight distinct frozen CD1 cells required', 1),
    ])


def preparation_source(source):
    source = exact_changes(source, [
        ("RUN='external-windows-confirmation-v3-execution-lock-v1-20261018'", 'RUN='+repr(PREFIX+'execution-lock-v1-20261018'), 1),
        ("'external-windows-confirmation-v3-staging-v1-20261018'", repr(PREFIX+'staging-v1-20261018'), 1),
        ("'external-windows-confirmation-v3-mcp-readiness-v1-20261018'", repr(PREFIX+'mcp-readiness-v1-20261018'), 1),
        ("'external-windows-confirmation-v3-sandbox-v2-20261018'", repr(PREFIX+'sandbox-v1-20261018'), 1),
        ("'external-windows-confirmation-v3-process-scope-v1-20261018'", repr(PREFIX+'process-scope-v1-20261018'), 1),
        ("end['all_76_cases_staged']", "end['all_38_cases_staged']", 1),
        ('len(stages)!=38', 'len(stages)!=19', 1),
        ("'atmem-confirmation-v3-execution-lock-v1'", "'atmem-corrective-development-execution-lock-v1'", 1),
        ("'model_attempts':76", "'model_attempts':38", 2),
        ("'readiness_cases':76", "'readiness_cases':38", 1),
        ("'all_76_initial_sources_verified'", "'all_38_initial_sources_verified'", 1),
    ])
    return source


def model_source(source):
    return exact_changes(source, [
        ("RUN='external-windows-confirmation-v3-models-v1-20261018'", 'RUN='+repr(PREFIX+'models-v1-20261018'), 1),
        ("LOCK='external-windows-confirmation-v3-execution-lock-v1-20261018'", 'LOCK='+repr(PREFIX+'execution-lock-v1-20261018'), 1),
        ("['all_76_initial_sources_verified']", "['all_38_initial_sources_verified']", 1),
        ("lock['model_attempts']!=76", "lock['model_attempts']!=38", 1),
        ("'attempts':76", "'attempts':38", 1),
        ("'expected_attempts':76", "'expected_attempts':38", 1),
    ])


def grading_source(source):
    return exact_changes(source, [
        ("RUN='external-windows-confirmation-v3-grading-v1-20261018'", 'RUN='+repr(PREFIX+'grading-v1-20261018'), 1),
        ("MODELS='external-windows-confirmation-v3-models-v1-20261018'", 'MODELS='+repr(PREFIX+'models-v1-20261018'), 1),
        ("LOCK='external-windows-confirmation-v3-execution-lock-v1-20261018'", 'LOCK='+repr(PREFIX+'execution-lock-v1-20261018'), 1),
        ('len(expected)!=76', 'len(expected)!=38', 1),
        ('len(rows)!=76', 'len(rows)!=38', 1),
        ("terminal[0]['attempts_completed']!=76", "terminal[0]['attempts_completed']!=38", 1),
        ("len({(r['slot'],r['arm']) for r in rows})!=76", "len({(r['slot'],r['arm']) for r in rows})!=38", 1),
        ('all seventy-six model/capture cells required before private grading', 'all thirty-eight CD1 model/capture cells required before private grading', 1),
        ("'cases':76", "'cases':38", 1),
    ])


def report_source(source):
    return exact_changes(source, [
        ("RUN = 'external-windows-confirmation-v3-comparison-v1-20261018'", 'RUN = '+repr(PREFIX+'comparison-v1-20261018'), 1),
        ("SEED = 'atmem-windows-confirmation-cluster-audit-20261018-v2'", "SEED = 'atmem-corrective-development-cluster-audit-20261018-v1'", 1),
        ('len(expected) != 76', 'len(expected) != 38', 1),
        ('len(rows) != 76', 'len(rows) != 38', 1),
        ("len({(r['slot'], r['arm']) for r in rows}) != 76", "len({(r['slot'], r['arm']) for r in rows}) != 38", 1),
        ('exact frozen seventy-six cells required; no subset comparison', 'exact frozen thirty-eight CD1 cells required; no subset comparison', 1),
        ('required_pairs=38', 'required_pairs=19', 2),
        ("'scope': 'repository-disjoint qualification-informed confirmation'", "'scope': 'reused-issue CD1 development screen; not independent confirmation'", 1),
        ("terminal['cases'] != 76", "terminal['cases'] != 38", 1),
        ('len(grade_rows) != 76', 'len(grade_rows) != 38', 1),
        ('len(by_cell) != 76', 'len(by_cell) != 38', 1),
        ("'required_pairs': 38", "'required_pairs': 19", 1),
    ])


def recovery_source(source):
    return exact_changes(source, [
        ("RUN = 'external-windows-confirmation-v3-public-recovery-v1-20261018'", 'RUN = '+repr(PREFIX+'public-recovery-v1-20261018'), 1),
        ("'cases': 76", "'cases': 38", 1),
    ])


def finish_source(source):
    return exact_changes(source, [
        ("RUN = 'external-windows-confirmation-v3-postprocessing-v1-20261018'", 'RUN = '+repr(PREFIX+'postprocessing-v1-20261018'), 1),
        ("['attempts_completed'] != 76", "['attempts_completed'] != 38", 1),
        ("'external-windows-confirmation-v3-grading-v1-20261018'", repr(PREFIX+'grading-v1-20261018'), 1),
        ("'external-windows-confirmation-v3-models-v1-20261018'", repr(PREFIX+'models-v1-20261018'), 1),
        ("'grading_only_after_all_76_models'", "'grading_only_after_all_38_models'", 1),
    ])
