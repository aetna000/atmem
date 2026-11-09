"""Upgrade an actual pinned published wheel's encrypted store, not a mock."""
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from atmem.contracts.feedback import ActionRequirement, FeedbackScope, OutcomeRecord
from atmem.evidence.service import EvidenceService
from atmem.feedback.service import FeedbackService


WHEEL_SHA256 = '37597be588817aa2dad921a683b39b6e6417eb5bdf3ec23256655acf13b19a03'


def test_upgrade_real_published_2314_evidence_store(tmp_path):
    wheel = os.environ.get('ATMEM_FEEDBACK_BASELINE_WHEEL')
    if not wheel:
        pytest.skip('requires an explicitly supplied pinned public wheel; no implicit network')
    wheel = Path(wheel)
    assert sha256(wheel.read_bytes()).hexdigest() == WHEEL_SHA256
    old = tmp_path/'published'
    old.mkdir()
    with zipfile.ZipFile(wheel) as archive:
        for info in archive.infolist():
            path = Path(info.filename)
            assert not path.is_absolute() and '..' not in path.parts
        archive.extractall(old)
    root = tmp_path/'home/control'
    env = {**os.environ,'PYTHONPATH':str(old)}
    program = '''import json, os, sys
from pathlib import Path
from atmem.evidence.service import EvidenceService
import atmem.evidence.store
assert str(Path(atmem.evidence.store.__file__).resolve()).startswith(str(Path(sys.argv[2]).resolve()))
root=Path(sys.argv[1])
e=EvidenceService(root,vault_id="upgrade",home_root=root.parent)
credentials=e.create_demo_accounts(subject_id="alice")
with e._store() as store:
    receipt=store.append({"record_type":"published_upgrade_fixture","content":"retained original published evidence"})
fd=os.open(root.parent/"synthetic-credentials.json",os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
with os.fdopen(fd,"w") as stream:json.dump(credentials,stream)
print(json.dumps(receipt))
'''
    process = subprocess.run([sys.executable,'-c',program,str(root),str(old)],env=env,cwd=tmp_path,
                             capture_output=True,text=True,timeout=30)
    assert process.returncode == 0, process.stderr
    original = json.loads(process.stdout)
    credentials = json.loads((root.parent/'synthetic-credentials.json').read_text())
    evidence = EvidenceService(root,vault_id='upgrade',home_root=root.parent)
    service = FeedbackService(evidence,clock=lambda:1_700_000_000)
    scope = FeedbackScope('local','alice','writer','project')
    service.grant_agent(credentials[2]['token'],scope,principal_id=credentials[1]['principal_id'],
                        operations=('read','report'),expires_at=1_700_010_000)
    session = service.bind(credentials[1]['token'],agent_id='writer',workspace_id='project')
    outcome = OutcomeRecord('new-outcome',scope,'run','turn',
                             (ActionRequirement('write','fixture.write','v1','write',('fact',)),),())
    service.report_outcome(session,outcome,idempotency_key='new')
    assert service.outcome(session,'new-outcome')['outcome'] == outcome.to_dict()
    with evidence._store() as store:
        recovered = next(row for row in store.documents() if row['object_id']==original['object_id'])
        assert recovered['content']=='retained original published evidence'
    # A real old binary must refuse the opted-in new partition format instead
    # of rewrapping its unknown scope keys under the wrong namespace.
    refusal = subprocess.run([sys.executable,'-c',
        'from atmem.evidence.service import EvidenceService; import sys; e=EvidenceService(sys.argv[1],vault_id="upgrade"); e._store()',
        str(root)],env=env,cwd=tmp_path,capture_output=True,text=True,timeout=30)
    assert refusal.returncode != 0 and 'unsupported encrypted evidence vault version' in refusal.stderr
