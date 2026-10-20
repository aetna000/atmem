"""Authenticated framing gates, not a new cryptographic primitive or audit."""
import base64
from copy import deepcopy

import pytest

from atmem.code import bundle_transport as transport
from atmem.core.canonical import canonical_json
from atmem.evidence.crypto import (generate_recipient_keypair,generate_signing_keypair,
                                   encrypted_export,decrypt_export)


@pytest.fixture
def fixture_bundle():
    public,secret=generate_recipient_keypair();signer,sign_secret=generate_signing_keypair()
    raw=(b'PROJECT_SEMANTIC_METADATA_CANARY_'+bytes(range(256)))*1000
    options=dict(recipient_public_key=public,signing_public_key=signer,signing_secret_key=sign_secret)
    return raw,transport.seal_project_bytes(raw,**options),secret,signer,options


def opened(bundle,secret,signer):
    return transport.open_project_bytes(bundle,recipient_secret_key=secret,trusted_signing_public_key=signer)


def test_large_exact_transport_and_legacy_small_and_larger_reads(fixture_bundle):
    raw,bundle,secret,signer,options=fixture_bundle
    assert bundle['format']==transport.FORMAT
    assert set(bundle)=={'format','signing_public_key','chunks'}
    assert 'PROJECT_SEMANTIC_METADATA_CANARY_' not in canonical_json(bundle)
    assert opened(bundle,secret,signer)==raw
    small=transport.seal_project_bytes(b'original small legacy bytes',**options)
    assert small['format']!=transport.FORMAT and 'ciphertext' in small
    assert opened(small,secret,signer)==b'original small legacy bytes'
    legacy=encrypted_export(raw,**options)
    assert opened(legacy,secret,signer)==raw


@pytest.mark.parametrize('change',[
    lambda b:b['chunks'].reverse(),lambda b:b['chunks'].pop(),
    lambda b:b['chunks'].__setitem__(1,b['chunks'][0]),
    lambda b:b.update(extra='unsupported'),lambda b:b.update(chunks=[]),
    lambda b:b['chunks'][0].update(ciphertext='AAAA'),
    lambda b:b['chunks'][0].update(extra='not signed contract'),
    lambda b:b['chunks'][0].update(ciphertext='x'*(transport.MAX_PIECE_BYTES+1)),
])
def test_broken_outer_or_pieces_rejected(fixture_bundle,change):
    _raw,bundle,secret,signer,_options=fixture_bundle
    changed=deepcopy(bundle);change(changed)
    with pytest.raises((ValueError,PermissionError)):
        opened(changed,secret,signer)


def test_wrong_signer_and_mixed_export_rejected(fixture_bundle):
    raw,bundle,secret,signer,options=fixture_bundle
    other_signer,_=generate_signing_keypair()
    with pytest.raises(PermissionError):opened(bundle,secret,other_signer)
    other=transport.seal_project_bytes(raw+b'different',**options)
    changed=deepcopy(bundle);changed['chunks'][1]=other['chunks'][1]
    with pytest.raises(ValueError,match='mixed'):opened(changed,secret,signer)


@pytest.mark.parametrize('change',[
    lambda h:h.update(ordinal=True),lambda h:h.update(count=True),
    lambda h:h.update(total_bytes=True),lambda h:h.update(total_bytes=transport.MAX_BYTES+1),
    lambda h:h.update(plaintext_sha256='invalid'),lambda h:h.update(extra='unsupported'),
    lambda h:h.update(data_base64='AAAA'),lambda h:h.update(data_base64='!invalid!'),
    lambda h:h.update(data_base64='A'*(4*((transport.CHUNK+2)//3)+1)),
])
def test_invalid_authenticated_inner_framing_rejected(fixture_bundle,change):
    _raw,bundle,secret,signer,options=fixture_bundle
    from atmem.delegated.validation import parse_json_strict
    inner=parse_json_strict(decrypt_export(bundle['chunks'][0],secret));change(inner)
    changed=deepcopy(bundle);changed['chunks'][0]=encrypted_export(canonical_json(inner).encode(),**options)
    with pytest.raises(ValueError):opened(changed,secret,signer)


def test_total_write_bound_before_encrypting(fixture_bundle,monkeypatch):
    raw,_bundle,_secret,_signer,options=fixture_bundle
    monkeypatch.setattr(transport,'MAX_BYTES',len(raw)-1)
    with pytest.raises(ValueError,match='logical size'):
        transport.seal_project_bytes(raw,**options)
