from copy import deepcopy
import json

import pytest


def test_encrypted_bundle_roundtrip_preserves_sources_lifecycle_and_search(code_env, tmp_path):
    pytest.importorskip("pqcrypto")
    from atmem.code.application import CodeApplication
    from atmem.code.portable import CodePortable
    from atmem.evidence.crypto import generate_recipient_keypair, generate_signing_keypair
    from atmem.memory import Memory
    env = code_env
    original = env.seed()
    replacement = env.app.correct(env.project, original, "My preferred formatter is Black.")
    env.app.settings(env.project, {"auto_recall": False})
    recipient_public, recipient_secret = generate_recipient_keypair()
    signing_public, signing_secret = generate_signing_keypair()
    bundle = CodePortable(env.app).export(env.project, recipient_public_key=recipient_public,
                                          signing_public_key=signing_public, signing_secret_key=signing_secret)
    serialized = json.dumps(bundle)
    assert "Black" not in serialized and "Ruff" not in serialized
    target_root = tmp_path / "fresh-clone"
    target_root.mkdir()
    target = Memory(":memory:", auto_vectors=False)
    try:
        app = CodeApplication(target, subject_id="local")
        portable = CodePortable(app)
        value = portable.open(bundle, recipient_secret_key=recipient_secret, trusted_signing_public_key=signing_public)
        preview = portable.preview(value, root=str(target_root))
        assert preview["can_import"]
        imported = portable.restore(value, root=str(target_root), preview_token=preview["preview_token"])
        assert imported["imported"]
        assert app.settings(env.project)["auto_recall"] is False
        rows = app.records(env.project, query="formatter")
        assert rows[0]["id"] == replacement["record"]["id"]
        assert "Black" in rows[0]["content"]
        assert app.inspect(env.project, rows[0]["id"])["source"]["message"]
        assert len(app.records(env.project, status=None)) == 2
        assert app.dispatch("hosts", {"project_id": env.project})["hosts"] == []
        assert portable.preview(value, root=str(target_root))["can_import"] is False
        with pytest.raises(PermissionError):
            CodePortable(CodeApplication(target, subject_id="other")).open(
                bundle, recipient_secret_key=recipient_secret, trusted_signing_public_key=signing_public)
        with pytest.raises(PermissionError):
            portable.open(bundle, recipient_secret_key=recipient_secret, trusted_signing_public_key=b"wrong")
        tampered = deepcopy(bundle)
        tampered["ciphertext"] = "AAAA"
        with pytest.raises(Exception):
            portable.open(tampered, recipient_secret_key=recipient_secret, trusted_signing_public_key=signing_public)
        malicious = deepcopy(value)
        malicious["state"]["documents"]["origin"][0]["value"]["source_ref"] = "api_key: sk-test-abcdefghijklmnop1234567890"
        from atmem.code.application import digest
        malicious["manifest"]["state_sha256"] = digest(malicious["state"])
        with pytest.raises(PermissionError, match="secret"):
            portable._validate(malicious)
    finally:
        target.close()
