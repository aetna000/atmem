import base64
from copy import deepcopy
from hashlib import sha256
import pytest
from benchmarks.code_replay import corrective_build as build


def test_only_one_source_changes_and_builder_dependencies_remain_identical(monkeypatch):
    old=b'old = True\n';new=b'def corrected():\n    return True\n'
    monkeypatch.setattr(build,'BASELINE_SHA',sha256(old).hexdigest())
    original={'files':{build.PATH:base64.b64encode(old).decode(),'other.py':base64.b64encode(b'preserved').decode()},
        'manifest':{build.PATH:sha256(old).hexdigest(),'other.py':sha256(b'preserved').hexdigest()},
        'program':'unchanged builder','constraints':'unchanged versions','cache':'unchanged cache'}
    saved=deepcopy(original);result=build.candidate_job(original,new)
    assert original==saved
    assert {k for k in result['manifest'] if result['manifest'][k]!=original['manifest'][k]}=={build.PATH}
    assert all(result[k]==original[k] for k in ('program','constraints','cache'))
    corrupt=deepcopy(original);corrupt['files']['other.py']=base64.b64encode(b'changed').decode()
    with pytest.raises(ValueError):build.candidate_job(corrupt,new)
    with pytest.raises(ValueError):build.candidate_job(original,old)


def test_ordinary_user_probe_executes_the_intended_alias_query(capsys):
    import ast
    import inspect
    import json
    tree=ast.parse(inspect.getsource(build))
    checks=[node.value.value for node in ast.walk(tree) if isinstance(node,ast.Assign)
            and isinstance(node.value,ast.Constant) and isinstance(node.value.value,str)
            and 'corrective_import' in node.value.value]
    assert len(checks)==1
    exec(compile(checks[0],'<ordinary-user-probe-fixture>','exec'),{})
    assert json.loads(capsys.readouterr().out)=={'corrective_import':True}
