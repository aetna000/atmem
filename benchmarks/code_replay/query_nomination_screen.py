"""CD2 profiles reuse CD1's exercised controls with a fresh frozen candidate."""
import ast
import inspect

from benchmarks.code_replay import corrective_controls as controls
from benchmarks.code_replay import corrective_execution as execution
from benchmarks.code_replay import corrective_staging as staging
from benchmarks.code_replay.query_nomination_preview import RUN as BUILD
from benchmarks.code_replay.query_nomination_qualification import RUN as QUALIFICATION
from benchmarks.code_replay.query_nomination_installed_replay import RUN as REPLAY

PREFIX = 'external-windows-query-nomination-development-'
CASE_ROOT = '/home/jt/atmem-benchmark-runtime-20261018/query-nomination-development-stage-v1/block-'
SEED = 'atmem-query-nomination-development-screen-20261018-v1'
CLUSTER_SEED = 'atmem-query-nomination-cluster-audit-20261018-v1'


def reprofile(source):
    """Change only declared run/storage identities, seeds and honest scope labels."""
    replacements = (
        (controls.PREFIX, PREFIX),
        ('/home/jt/atmem-benchmark-runtime-20261018/corrective-development-stage-v1',
         CASE_ROOT.removesuffix('/block-')),
        (controls.CGROUP, '/sys/fs/cgroup/atmem-code-query-nomination-development-20261018'),
        (staging.SEED, SEED),
        ('atmem-corrective-development-cluster-audit-20261018-v1', CLUSTER_SEED),
        ('corrective-development19-', 'query-nomination-development19-'),
        ('atmem-corrective-development19-staging-v1', 'atmem-query-nomination-development19-staging-v1'),
        ('atmem-corrective-development-execution-lock-v1', 'atmem-query-nomination-development-execution-lock-v1'),
        ('CD1', 'CD2'),
    )
    for before, after in replacements:
        source = source.replace(before, after)
    ast.parse(source, feature_version=(3, 10))
    return source


def staging_source(original):
    source = reprofile(staging.staging_source(original))
    replacements = {
        "'external-windows-product-build-typed-query-v1-20261018','external.corrective_build_completed'":
            repr(BUILD) + ",'external.query_nomination_build_completed'",
        "'external-windows-typed-query-qualification-v1-20261018-owned-state-continuation'": repr(QUALIFICATION),
        "    old=only(OLD,'external.confirmation_manifest_frozen')":
            "    installed_replay=only(" + repr(REPLAY) + ",'external.query_nomination_installed_replay_completed')\n"
            "    if installed_replay['qualified'] is not True or installed_replay['identities']!=19 or installed_replay['model_calls']!=0:raise ValueError('all installed pack replays required')\n"
            "    old=only(OLD,'external.confirmation_manifest_frozen')",
    }
    for before, after in replacements.items():
        if source.count(before) != 1:
            raise ValueError('exact exercised CD1 staging prerequisite required: ' + before)
        source = source.replace(before, after)
    ast.parse(source, feature_version=(3, 10))
    return source


def sources():
    from benchmarks.code_replay import confirmation_v3_staging, confirmation_v3_readiness
    from benchmarks.code_replay import confirmation_v3_sandbox, confirmation_v3_process_scope
    from benchmarks.code_replay import confirmation_v3_prepare, confirmation_v3_execute
    from benchmarks.code_replay import confirmation_v3_grade, confirmation_v3_report
    from benchmarks.code_replay import confirmation_v3_retain, confirmation_v3_finish
    pairs = {
        'staging': (staging_source, confirmation_v3_staging),
        'readiness': (lambda s: reprofile(controls.readiness_source(s)), confirmation_v3_readiness),
        'sandbox': (lambda s: reprofile(controls.sandbox_source(s)), confirmation_v3_sandbox),
        'process': (lambda s: reprofile(controls.process_source(s)), confirmation_v3_process_scope),
        'prepare': (lambda s: reprofile(execution.preparation_source(s)), confirmation_v3_prepare),
        'models': (lambda s: reprofile(execution.model_source(s)), confirmation_v3_execute),
        'grade': (lambda s: reprofile(execution.grading_source(s)), confirmation_v3_grade),
        'report': (lambda s: reprofile(execution.report_source(s)), confirmation_v3_report),
        'retain': (lambda s: reprofile(execution.recovery_source(s)), confirmation_v3_retain),
        'finish': (lambda s: reprofile(execution.finish_source(s)), confirmation_v3_finish),
    }
    return {name: adapt(inspect.getsource(module)) for name, (adapt, module) in pairs.items()}


def supporting_sources():
    return {name: reprofile(source) for name, source in execution.supporting_sources().items()}
