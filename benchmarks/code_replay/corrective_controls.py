"""CD1 uses exercised boundary controls on fresh cases, not relaxed checks."""
import ast

PREFIX = 'external-windows-corrective-development-'
CASE_ROOT = '/home/jt/atmem-benchmark-runtime-20261018/corrective-development-stage-v1/block-'
CGROUP = '/sys/fs/cgroup/atmem-code-corrective-development-20261018'


def exact_changes(source, changes):
    for before, after, count in changes:
        if source.count(before) != count:
            raise ValueError('exact exercised control source required: '+before)
        source = source.replace(before, after)
    ast.parse(source, feature_version=(3, 10))
    return source


def readiness_source(source):
    return exact_changes(source, [
        ("RUN='external-windows-confirmation-v3-mcp-readiness-v1-20261018'", 'RUN='+repr(PREFIX+'mcp-readiness-v1-20261018'), 1),
        ("STAGING='external-windows-confirmation-v3-staging-v1-20261018'", 'STAGING='+repr(PREFIX+'staging-v1-20261018'), 1),
        ('/home/jt/atmem-benchmark-runtime-20261018/confirmation-stage-v3/block-', CASE_ROOT, 1),
        ("['all_76_cases_staged']", "['all_38_cases_staged']", 1),
        ('len(blocks)!=38', 'len(blocks)!=19', 1),
        ("len({b['block']['slot'] for b in blocks})!=38", "len({b['block']['slot'] for b in blocks})!=19", 1),
        ("'cases':76", "'cases':38", 1),
        ("'all_76_cases_qualified':len(results)==76", "'all_38_cases_qualified':len(results)==38", 1),
        ('all 76 independently staged v3 cases required', 'all 38 independently staged CD1 cases required', 1),
    ])


def process_source(source):
    return exact_changes(source, [
        ('/sys/fs/cgroup/atmem-code-confirmation-v3-20261018', CGROUP, 2),
        ("RUN='external-windows-confirmation-v3-process-scope-v1-20261018'", 'RUN='+repr(PREFIX+'process-scope-v1-20261018'), 1),
        (r'[12][0-9]|3[0-7]', r'1[0-8]', 1),
    ])


def sandbox_source(source):
    start = '    for row in old_ends[0][\'results\']:\n'
    stop = '    events=vault.inspect(principal,STAGING)'
    if source.count(start) != 1 or source.count(stop) != 1:
        raise ValueError('exact old failure-audit block required')
    a, b = source.index(start), source.index(stop)
    # The fresh control starts from the already corrected, positively qualified
    # probe. Do not pretend that CD1 experienced the historical canary failure.
    source = source[:a]+source[b:]
    source = exact_changes(source, [
        ("PREVIOUS='external-windows-confirmation-v3-sandbox-v1-20261018'", "PREVIOUS='external-windows-confirmation-v3-sandbox-v2-20261018'", 1),
        ("RUN='external-windows-confirmation-v3-sandbox-v2-20261018'", 'RUN='+repr(PREFIX+'sandbox-v1-20261018'), 1),
        ("STAGING='external-windows-confirmation-v3-staging-v1-20261018'", 'STAGING='+repr(PREFIX+'staging-v1-20261018'), 1),
        ("old_plans[0]['worker_source']!=PROGRAM", "old_plans[0]['worker_source']!=hidden_view_program()", 1),
        ("old_ends[0]['all_76_cases_qualified'] is not False", "old_ends[0]['all_76_cases_qualified'] is not True", 1),
        ('exact terminal zero-model canary failures required', 'exact positively qualified zero-model probe required', 1),
        ("ends[0]['all_76_cases_staged']", "ends[0]['all_38_cases_staged']", 1),
        ('len(cases)!=38', 'len(cases)!=19', 1),
        ("'model_prefix':prefix,'cases':76", "'model_prefix':prefix,'cases':38", 1),
        ("'all_76_cases_qualified':len(results)==76", "'all_38_cases_qualified':len(results)==38", 1),
        ("'correction':'accept hidden-view ENOENT after positive unrestricted canary control; policy unchanged'",
         "'probe_semantics':'reuse positively qualified hidden-view denial probe on fresh CD1 cases; policy unchanged'", 1),
    ])
    return source
