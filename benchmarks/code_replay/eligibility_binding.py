"""Operator-bound registration over the existing private worker, not a new grader."""
from hashlib import sha256
from pathlib import Path
import re

from benchmarks.code_replay.windows_eligibility_images import validate_pool

SOURCE_PROFILES = {
    'pallets/flask': (('src/flask/',), ('tests/',)),
    'mwaskom/seaborn': (('seaborn/',), ('seaborn/tests/', 'tests/')),
    'pydata/xarray': (('xarray/',), ('xarray/tests/', 'tests/')),
    'pylint-dev/pylint': (('pylint/',), ('tests/',)),
    'pyvista/pyvista': (('pyvista/',), ('tests/',)),
}
PUBLIC_LAYOUTS = {
    'pallets/flask': (('tests',), 'src'),
    'mwaskom/seaborn': (('seaborn/tests', 'tests'), '.'),
    'pydata/xarray': (('xarray/tests', 'tests'), '.'),
    'pylint-dev/pylint': (('tests',), '.'),
    'pyvista/pyvista': (('tests',), '.'),
}


def registered_public_settings(task, registration):
    """Trusted operator bootstrap only; this is never a model payload field."""
    from benchmarks.code_replay.source_policy import path_name
    if not isinstance(task, dict) or set(task) != {'instance_id', 'base_commit', 'image_extras_sha256'}:
        raise ValueError('exact pinned public task settings required')
    identity = task['instance_id']
    binding = registration['bindings'].get(identity)
    if binding is None or binding[0] != task['base_commit']:
        raise ValueError('operator-registered task/base identity required')
    repo = identity.rsplit('-', 1)[0].replace('__', '/')
    if repo not in SOURCE_PROFILES or tuple(map(tuple, registration['source_profiles'][identity])) != SOURCE_PROFILES[repo]:
        raise ValueError('fixed registered source profile required')
    extras = task['image_extras_sha256']
    if not isinstance(extras, dict) or len(extras) > 10000:
        raise ValueError('bounded image artifact map required')
    for name, value in extras.items():
        path_name(name)
        if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value):
            raise ValueError('exact image artifact identity required')
    roots, tests = SOURCE_PROFILES[repo]
    paths, source_subdir = PUBLIC_LAYOUTS[repo]
    return {'PINNED_TASK_ID': identity, 'PINNED_BASE': task['base_commit'],
        'PINNED_SOURCE_ROOTS': roots, 'PINNED_TEST_ROOTS': tests,
        'PINNED_TEST_PATHS': paths, 'PINNED_DEFAULT_TEST_PATHS': paths[:1],
        'PINNED_SOURCE_SUBDIR': source_subdir, 'PINNED_IMAGE_EXTRAS': extras,
        'PINNED_RUNTIME_EXCLUSIONS': ()}


def bound_worker_source(selection, metadata):
    validate_pool(selection, metadata)
    selected = {r['instance_id']: r for r in selection['selected']}
    bindings, profiles = {}, {}
    for row in metadata['reports']:
        task = row['metadata']; identity = row['instance_id']
        if (task['repo'] != selected[identity]['repo']
            or not re.fullmatch(r'[0-9a-f]{40}', task['base_commit'])
            or not re.fullmatch(r'parse_log_[A-Za-z0-9_]+', task['log_parser'])):
            raise ValueError('exact repository/base/parser metadata required')
        bindings[identity] = (task['base_commit'], task['log_parser'])
        profiles[identity] = SOURCE_PROFILES[task['repo']]
    original = Path(__file__).with_name('external_qualify_worker.py').read_text()
    marker = '\nif __name__ == "__main__":\n'
    if original.count(marker) != 1:
        raise ValueError('review private worker registration boundary')
    registration = (
        '\n# Operator-frozen eligibility metadata; never model request fields.\n'
        'ELIGIBILITY_BINDINGS = ' + repr(bindings) + '\n'
        'ELIGIBILITY_SOURCE_PROFILES = ' + repr(profiles) + '\n'
        'TASK_BINDINGS.update(ELIGIBILITY_BINDINGS)\n'
        '_prior_task_source_roots = task_source_roots\n'
        'def task_source_roots(instance_id, base_commit):\n'
        '    task_binding(instance_id, base_commit)\n'
        '    if instance_id in ELIGIBILITY_SOURCE_PROFILES:\n'
        '        return ELIGIBILITY_SOURCE_PROFILES[instance_id]\n'
        '    return _prior_task_source_roots(instance_id, base_commit)\n'
    )
    source = original.replace(marker, registration + marker)
    return source, {'original_worker_sha256': sha256(original.encode()).hexdigest(),
        'registered_worker_sha256': sha256(source.encode()).hexdigest(),
        'registration_source': registration, 'bindings': bindings, 'source_profiles': profiles,
        'upstream_grading_logic_changed': False, 'model_selected_settings': False}
