import pytest
from atmem.server.config import ProductionConfig
def test_production_config_fails_closed():
    with pytest.raises(ValueError): ProductionConfig(public_bind=True,encryption_key_reference="kms:x").validate()
    ProductionConfig(public_bind=True,tls_cert="cert",tls_key="key",secret_reference="vault:x",encryption_key_reference="kms:x").validate()
