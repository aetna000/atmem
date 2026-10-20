import ast
from pathlib import Path

import pytest

from benchmarks.code_replay import query_nomination_qualification as qualification


def test_fresh_controls_bind_exact_installed_candidate_and_full_evidence():
    original = Path('benchmarks/code_replay/compatibility_qualification.py').read_text()
    source = qualification.driver_source(original)
    ast.parse(source, feature_version=(3, 10))
    namespace = {'__name__': 'qualification_definition'}
    exec(compile(source, '<qualification-definition>', 'exec'), namespace)
    assert namespace['RUN'] == qualification.RUN
    assert len(namespace['IDENTITIES']) == 5
    worker = namespace['PROGRAM']
    assert qualification.CANDIDATE in worker
    assert 'is_relative_to(Path(sys.prefix).resolve())' in worker
    assert 'foreign_scope_denied' in worker
    assert 'encrypted bundle lost original generation data' in worker
    assert 'changed source was not withheld' in worker
    assert 'user=1000,group=1000' in worker
    assert source.count("'configuration_source':job['configuration_source'],") == 2
    assert qualification.WHEEL in source
    assert 'fresh installed controls failed' in source
    assert 'owned-state-continuation' not in source


def test_adapter_rejects_changed_control_boundary():
    original = Path('benchmarks/code_replay/compatibility_qualification.py').read_text()
    with pytest.raises(ValueError):
        qualification.driver_source(original.replace("'worker_source':PROGRAM,", "'worker_source':'omitted',"))
