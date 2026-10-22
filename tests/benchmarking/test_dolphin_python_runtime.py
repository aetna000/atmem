import json
import base64
import hashlib
from types import SimpleNamespace

import pytest

from benchmarks.dolphinbench import python_runtime


@pytest.mark.parametrize('valid',[True,False])
def test_invalid_binary_signature_is_rejected_before_any_model_call(tmp_path,monkeypatch,valid):
    executable=tmp_path/'python';executable.write_bytes(b'fixture executable')
    library=tmp_path/'libpython.dylib';library.write_bytes(b'fixture library')
    calls=[]
    def run(command,**kwargs):
        calls.append(command)
        if command[0]=='codesign':
            return SimpleNamespace(returncode=0 if valid else 1)
        return SimpleNamespace(stdout=json.dumps({'executable':str(executable),
            'platform':'darwin','shared_libraries':[str(library)]}))
    monkeypatch.setattr(python_runtime.subprocess,'run',run)
    if valid:
        receipt=python_runtime.qualify_python(executable)
        assert receipt['macos_code_signatures_verified']
        assert len(receipt['binary_sha256'])==2
        assert len(calls)==3
    else:
        with pytest.raises(ValueError,match='code signature'):
            python_runtime.qualify_python(executable)
        assert len(calls)==2


def test_application_payload_checked_before_import(tmp_path,monkeypatch):
    library=tmp_path/'dependency.so';library.write_bytes(b'original')
    encoded=base64.urlsafe_b64encode(hashlib.sha256(b'original').digest()).decode().rstrip('=')
    metadata={'site':str(tmp_path),'distributions':[{'name':'dependency','version':'1',
        'files':[{'path':'dependency.so','hash':'<FileHash mode: sha256 value: '+encoded+'>'}]}]}
    calls=[]
    def run(command,**kwargs):
        calls.append(command)
        return SimpleNamespace(stdout=json.dumps(metadata))
    monkeypatch.setattr(python_runtime.subprocess,'run',run)
    assert python_runtime.qualify_application('python')['wheel_record_verified']
    assert len(calls)==2
    library.write_bytes(b'damaged')
    calls.clear()
    with pytest.raises(ValueError,match='differs from RECORD'):
        python_runtime.qualify_application('python')
    assert len(calls)==1


@pytest.mark.parametrize('changed',[False,True])
def test_relocation_requires_identical_expected_wheel_code(monkeypatch,changed):
    old={'site':'old','distributions':[{'name':'dependency','version':'1',
        'files':[{'path':'dependency.py','hash':'<FileHash mode: sha256 value: abc>'}]}]}
    monkeypatch.setattr(python_runtime.subprocess,'run',lambda *a,**k:SimpleNamespace(stdout=json.dumps(old)))
    monkeypatch.setattr(python_runtime,'qualify_application',lambda *a:{
        'packages':{'dependency':'2' if changed else '1'},
        'payload_sha256_base64':{'dependency.py':'abc'}})
    if changed:
        with pytest.raises(ValueError,match='code or versions changed'):
            python_runtime.qualify_application_repair('old','new')
    else:
        assert python_runtime.qualify_application_repair('old','new')['identical_expected_wheel_payload']
