"""Run explicit CD3 profiles through unchanged CD2 preparation/execution."""
import ast
import inspect
import linecache
import os
from pathlib import Path
import sys

from benchmarks.code_replay import literal_anchor_screen as screen
from benchmarks.code_replay import public_selector_audit
from benchmarks.code_replay import query_nomination_preparation, query_nomination_execution
from benchmarks.code_replay.literal_anchor_controls import QUALIFY, REPLAY
from benchmarks.code_replay.query_nomination_preview import evidence, of


def controller_source(mode):
    if mode in ('archive', 'transfer'):
        from benchmarks.code_replay.literal_anchor_archive import controller_source as archive_controller
        return archive_controller(mode)
    if mode not in ('prepare', 'execute'):
        raise ValueError('explicit preparation or execution required')
    module = query_nomination_preparation if mode == 'prepare' else query_nomination_execution
    source = inspect.getsource(module)
    source = screen.replace_once(source,
        'from benchmarks.code_replay import query_nomination_screen as screen',
        'from benchmarks.code_replay import literal_anchor_screen as screen')
    if mode == 'prepare':
        source = screen.replace_once(source, 'screen.QUALIFICATION,', 'screen.controls.QUALIFY,')
        source = screen.replace_once(source, 'screen.REPLAY,', 'screen.controls.REPLAY,')
        source = screen.replace_once(source,
            'specs/042-atmem-code/query-nomination-development-screen-v1.md',
            'specs/042-atmem-code/literal-anchor-development-screen-v1.md')
    else:
        source = screen.replace_once(source,
            'from benchmarks.code_replay.query_nomination_preparation import RUN as PREPARATION',
            'PREPARATION='+repr(screen.PREFIX+'preparation-v1-20261018'))
    ast.parse(source, feature_version=(3, 10))
    return source


def controller_namespace(source):
    filename = '<retained-CD3-controller>'
    linecache.cache[filename] = (len(source), None, source.splitlines(keepends=True), filename)
    namespace = {'__name__': 'explicit_literal_anchor_study', '__file__': __file__}
    exec(compile(source, filename, 'exec'), namespace)
    return namespace


def main():
    if sys.argv[1:] not in (['prepare'], ['execute'], ['archive'], ['transfer']):
        raise ValueError('choose prepare, execute, archive or transfer; no automatic model phase')
    mode = sys.argv[1]; run = screen.PREFIX+'profile-'+mode+'-v1-20261018'
    os.environ['ATMEM_BENCHMARK_PER_RUN_VAULTS'] = '1'
    vault, principal = evidence(run)
    if vault.inspect(principal, run):
        raise ValueError('profile already submitted; inspect original process and evidence')
    audit, = of(vault.inspect(principal, public_selector_audit.RUN),
                'external.public_selector_template_audit_completed')
    if audit['summary'] != {'identities': 19, 'programs': 38, 'validator_only_delta': True,
                            'template_programs_executed': 0, 'model_calls': 0,
                            'private_grades_repeated': 0, 'source_vault_opened': False,
                            'runtime_qualified': False}:
        raise ValueError('all archived server/worker templates must pass before staging')
    for control in (QUALIFY, REPLAY):
        terminal, = of(vault.inspect(principal, control+'-submission'),
                      'external.literal_anchor_control_submission_result')
        if terminal['exit_code'] != 0:
            raise ValueError('terminal installed qualification required')
    if mode == 'execute':
        from benchmarks.code_replay.public_selector_runtime import RUN as PUBLIC_RUNTIME
        terminal, = of(vault.inspect(principal, PUBLIC_RUNTIME+'-submission'),
                      'external.public_selector_runtime_submission_result')
        if terminal['exit_code'] != 0:
            raise ValueError('actual unchanged/candidate nested-root runtime gate required')
    source = controller_source(mode)
    # Generate and validate the complete frozen profiles before any SSH dispatch.
    sources = screen.sources(); support = screen.supporting_sources()
    vault.capture(run_id=run, kind='external.literal_anchor_study_profile_planned', principal=principal,
        payload={'mode': mode, 'controller_source': source, 'profile_source': inspect.getsource(screen),
                 'driver_source': Path(__file__).read_text(), 'sources': sources, 'support': support,
                 'protocol': Path('specs/042-atmem-code/literal-anchor-development-screen-v1.md').read_text(),
                 'template_audit_run': public_selector_audit.RUN, 'outcome_retries': 0})
    namespace = controller_namespace(source)
    namespace['main']()


if __name__ == '__main__':
    main()
