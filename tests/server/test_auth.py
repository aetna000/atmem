import pytest
from atmem.server.auth import KeyAuthority, Principal
def test_key_scope_rotation_revocation_and_expiry(monkeypatch):
    authority=KeyAuthority(); principal=Principal("p","tenant","user","writer",("ws",)); old_id,old_secret=authority.issue(principal)
    assert authority.authenticate(old_id,old_secret).permits("write","ws")
    assert not principal.permits("write","other")
    new_id,new_secret=authority.rotate(old_id,overlap_seconds=0)
    with pytest.raises(PermissionError): authority.authenticate(old_id,old_secret)
    assert authority.authenticate(new_id,new_secret)==principal
    authority.revoke(new_id)
    with pytest.raises(PermissionError): authority.authenticate(new_id,new_secret)
