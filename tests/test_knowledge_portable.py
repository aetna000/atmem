from pathlib import Path
import json

import pytest

from atmem.code.application import CodeApplication
from atmem.code.portable import CodePortable, FORMAT_V2
from atmem.evidence.crypto import generate_recipient_keypair, generate_signing_keypair
from atmem.memory import Memory
from tests.test_code_experience import scenario, sign


def bundle_for(env):
    public, secret = generate_recipient_keypair()
    signing_public, signing_secret = generate_signing_keypair()
    bundle = CodePortable(env.app).export(env.project, recipient_public_key=public,
                                         signing_public_key=signing_public, signing_secret_key=signing_secret)
    return bundle, secret, signing_public


def test_v2_roundtrip_preserves_typed_authority_and_original_receipts(code_env, tmp_path):
    env = code_env
    env.memory._allow_insecure_typed_development = True
    service, snapshot, receipt, result, proposal = scenario(env)
    service.receipt(receipt, snapshot, result, sign(receipt))
    formed = service.form(proposal, snapshot, producer_id="producer", signature=sign(proposal))
    assert formed["formed"]
    bundle, secret, signer = bundle_for(env)
    assert "Check main function" not in json.dumps(bundle)
    target_root = tmp_path / "new-clone"
    target_root.mkdir()
    target = Memory(":memory:", auto_vectors=False)
    try:
        app = CodeApplication(target, subject_id="local")
        portable = CodePortable(app)
        value = portable.open(bundle, recipient_secret_key=secret, trusted_signing_public_key=signer)
        assert value["manifest"]["format"] == FORMAT_V2
        assert len(value["state"]["tables"]["protocol_sources"]) == 1
        assert len(value["state"]["tables"]["typed_memory_units"]) == 1
        preview = portable.preview(value, root=str(target_root))
        portable.restore(value, root=str(target_root), preview_token=preview["preview_token"])
        inspected = app.inspect(env.project, formed["record_ids"][0])
        assert inspected["experience"]["proposal"]["observation"] == proposal.observation
        restored = app.store.code_document("local", env.project, "execution-receipt", receipt.receipt_id)
        assert restored["receipt"] == receipt.to_dict()
        assert target.store.get_protocol_source_by_id(next(iter(value["state"]["tables"]["protocol_sources"]))["source_id"])
    finally:
        target.close()


def test_forget_removes_experience_copies_and_blocks_replay(code_env):
    env = code_env
    env.memory._allow_insecure_typed_development = True
    service, snapshot, receipt, result, proposal = scenario(env)
    service.receipt(receipt, snapshot, result, sign(receipt))
    formed = service.form(proposal, snapshot, producer_id="producer", signature=sign(proposal))
    env.app.forget(env.project, formed["record_ids"][0])
    assert env.memory.store.code_document("local", env.project, "code-experience", proposal.proposal_id) is None
    assert env.memory.store.code_document("local", env.project, "execution-receipt", receipt.receipt_id) is None
    assert service.form(proposal, snapshot, producer_id="producer", signature=sign(proposal)) == {
        "formed": False, "reason": "experience_was_deleted"}
    bundle, secret, signer = bundle_for(env)
    opened = CodePortable(env.app).open(bundle, recipient_secret_key=secret, trusted_signing_public_key=signer)
    assert opened["state"]["documents"]["experience-tombstone"]
