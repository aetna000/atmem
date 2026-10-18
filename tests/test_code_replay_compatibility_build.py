import base64
from copy import deepcopy
from hashlib import sha256

import pytest

from benchmarks.code_replay.windows_compatibility_build import candidate_job,CHANGED,ADDED


def inputs():
    old=b'old source';new=b'new source'
    original={'files':{n:base64.b64encode(old).decode() for n in CHANGED if n not in ADDED},
        'manifest':{n:sha256(old).hexdigest() for n in CHANGED if n not in ADDED},
        'program':"root=Path(tempfile.mkdtemp(prefix='product-build-',dir=runtime));root.chmod(0o700)",
        'constraints':'unchanged dependencies','cache':'unchanged benchmark cache'}
    inspection={'rows':[{'path':n,'old_sha256':None if n in ADDED else sha256(old).hexdigest(),
                         'new_sha256':sha256(new).hexdigest()} for n in CHANGED]}
    return original,{n:new for n in CHANGED},inspection


def test_only_nine_inspected_sources_and_install_traversal_change():
    original,replacements,inspection=inputs();saved=deepcopy(original)
    result=candidate_job(original,replacements,inspection)
    assert original==saved and result['constraints']==original['constraints'] and result['cache']==original['cache']
    assert set(result['files'])==set(CHANGED)
    assert 'os.chown(root,0,1000);root.chmod(0o710)' in result['program']


@pytest.mark.parametrize('change',[
    lambda p,r,i:r.pop(CHANGED[0]),lambda p,r,i:r.update({'unrelated.py':b'new source'}),
    lambda p,r,i:r.update({CHANGED[0]:b'uninspected source'}),
    lambda p,r,i:p['manifest'].update({CHANGED[1]:'0'*64}),
    lambda p,r,i:p.update(program='changed builder'),
    lambda p,r,i:p['files'].update({CHANGED[0]:'already exists'}),
])
def test_uninspected_or_wrong_base_refused(change):
    original,replacements,inspection=inputs();change(original,replacements,inspection)
    with pytest.raises(ValueError):candidate_job(original,replacements,inspection)
