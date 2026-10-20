import base64
from hashlib import sha1
import pytest
from benchmarks.code_replay.confirmation_issues import issue_blob


def test_only_pinned_public_issue_blob_bytes_are_admitted():
    raw=b'Authentic public issue\n'
    sha=sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    tree={'tree':[{'path':'problem_statement.md','type':'blob','mode':'100644','size':len(raw),'sha':sha}]}
    response={'sha':sha,'encoding':'base64','content':base64.b64encode(raw).decode()}
    assert issue_blob(tree,response)==raw
    with pytest.raises(ValueError):issue_blob(tree,{**response,'content':'eA=='})
    with pytest.raises(ValueError):issue_blob({'tree':[{**tree['tree'][0],'path':'gold.patch'}]},response)
