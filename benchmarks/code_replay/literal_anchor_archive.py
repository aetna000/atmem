"""CD3 archive profiles retain the exercised encrypted collection/recovery code."""
import ast
import inspect

from benchmarks.code_replay import query_nomination_archive as previous
from benchmarks.code_replay import query_nomination_archive_waiter, query_nomination_transfer
from benchmarks.code_replay import literal_anchor_screen as screen
from benchmarks.code_replay.literal_anchor_controls import QUALIFY, REPLAY

REMOTE = '/home/jt/atmem-benchmark-runtime-20261018'
EXPORT_OUTPUT = REMOTE+'/literal-anchor-development-archive-v1'
EXPORT_KEYS = REMOTE+'/literal-anchor-development-archive-keys-v1'
OUTPUT = '/Volumes/MEM/AtMem-Code-Replay-20261017/literal-anchor-development-protected-20261018'
KEYS = '/Users/javadtaghia/Library/Application Support/AtMem Benchmarks/click-20261017/keys-literal-anchor-development-archive-20261018'


def archive_source(original):
    source = screen.reprofile(previous.archive_source(original))
    for old, new in (
        ('external-windows-query-nomination-qualification-v1-20261018', QUALIFY),
        ('external-windows-query-nomination-installed-replay-v1-20261018', REPLAY),
        ('external-windows-product-build-query-nomination-v1-20261018', screen.BUILD),
        ('atmem-code-query-nomination-development-protected-collection-v1',
         'atmem-code-literal-anchor-development-protected-collection-v1'),
    ):
        source = screen.replace_once(source, old, new)
    marker = "    runs.update({PREFIX+'preparation-v1-20261018', PREFIX+'execution-v1-20261018',"
    source = screen.replace_once(source, marker,
        "    supplementary=PREFIX+'public-selector-runtime-v1-20261018'\n"
        "    terminal,=of(read(supplementary),'external.public_selector_runtime_completed')\n"
        "    if terminal['qualified'] is not True or terminal['model_calls']!=0:raise ValueError('actual unchanged/candidate public selector control required')\n"
        "    runs.add(supplementary)\n"+marker)
    ast.parse(source, feature_version=(3, 10))
    return source


def controller_source(mode):
    if mode not in ('archive', 'transfer'):
        raise ValueError('explicit archive or transfer required')
    module = query_nomination_archive_waiter if mode == 'archive' else query_nomination_transfer
    source = inspect.getsource(module)
    source = screen.replace_once(source,
        'from benchmarks.code_replay.query_nomination_screen import PREFIX',
        'from benchmarks.code_replay.literal_anchor_screen import PREFIX')
    if mode == 'archive':
        source = screen.replace_once(source,
            'from benchmarks.code_replay import confirmation_v3_archive, query_nomination_archive',
            'from benchmarks.code_replay import confirmation_v3_archive\n'
            'from benchmarks.code_replay import literal_anchor_archive as query_nomination_archive')
        source = screen.replace_once(source,
            "OUTPUT = REMOTE + '/query-nomination-development-archive-v1'", 'OUTPUT = '+repr(EXPORT_OUTPUT))
        source = screen.replace_once(source,
            "KEYS = REMOTE + '/query-nomination-development-archive-keys-v1'", 'KEYS = '+repr(EXPORT_KEYS))
    else:
        source = screen.replace_once(source,
            'from benchmarks.code_replay.query_nomination_archive_waiter import REMOTE, OUTPUT as REMOTE_OUTPUT, KEYS as REMOTE_KEYS',
            'from benchmarks.code_replay.literal_anchor_archive import REMOTE, EXPORT_OUTPUT as REMOTE_OUTPUT, EXPORT_KEYS as REMOTE_KEYS')
        source = screen.replace_once(source, repr(query_nomination_transfer.OUTPUT), repr(OUTPUT))
        source = screen.replace_once(source, repr(query_nomination_transfer.KEYS), repr(KEYS))
        source = screen.replace_once(source,
            'from benchmarks.code_replay import query_nomination_archive, corrective_archive',
            'from benchmarks.code_replay import literal_anchor_archive as query_nomination_archive\n'
            '    from benchmarks.code_replay import corrective_archive')
        source = screen.replace_once(source,
            'from benchmarks.code_replay.query_nomination_preparation import SUBMIT as PREPARATION_SUBMIT',
            'PREPARATION_SUBMIT='+repr(screen.PREFIX+'preparation-v1-20261018-submission'))
    ast.parse(source, feature_version=(3, 10))
    return source
