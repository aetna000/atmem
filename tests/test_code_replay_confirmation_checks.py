import ast
from hashlib import sha256
import pytest

from benchmarks.code_replay.windows_confirmation_checks import MODULES, isolation_probe, retained_grader


def test_fixed_public_probe_checks_actual_source_and_denies_private_state():
    for module in MODULES.values():
        code=isolation_probe(module)
        ast.parse(code,feature_version=(3,9))
        assert "is_relative_to(Path('/work'))" in code
        assert '/testbed/.git' in code and '/opt/atmem-evaluator' in code
        assert "('1.1.1.1',443)" in code
    with pytest.raises(ValueError): isolation_probe('arbitrary_module')


def test_actual_retained_worker_is_extracted_and_hash_verified():
    from benchmarks.code_replay.external_source_boundary import bootstrap_source
    worker='qualified_grader = True\n'
    plan={'program':bootstrap_source(worker,result_transport='lzma-v2',runtime_projection=True),
          'projection_registration':{'projected_worker_sha256':sha256(worker.encode()).hexdigest()}}
    assert retained_grader(plan)==worker
    plan['projection_registration']['projected_worker_sha256']='0'*64
    with pytest.raises(ValueError): retained_grader(plan)
