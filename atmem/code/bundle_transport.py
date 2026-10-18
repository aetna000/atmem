"""Bounded project export transport using existing signed encrypted primitives.

Adapts the authenticated framing already exercised by Code replay archives;
does not import benchmark code or change the underlying cryptographic format.
Project metadata remains in ciphertext. Legacy small bundles stay unchanged.
"""
import base64
from hashlib import sha256
import re

from atmem.core.canonical import canonical_json
from atmem.delegated.validation import parse_json_strict
from atmem.evidence.crypto import encrypted_export, decrypt_export

FORMAT = 'atmem-code-project-encrypted-chunks-v1'
INNER_FORMAT = 'atmem-code-project-bundle-chunk-v1'
CHUNK = 196608
MAX_BYTES = 128_000_000
MAX_PIECE_BYTES = 400_000
_PIECE_FIELDS = {'format','suite','kem_ciphertext','nonce','ciphertext','signing_public_key','signature'}


def _checked_piece(piece, expected_key):
    if (type(piece) is not dict or set(piece) != _PIECE_FIELDS
            or any(type(v) is not str or len(v)>MAX_PIECE_BYTES for v in piece.values())
            or piece['signing_public_key'] != expected_key
            or len(canonical_json(piece).encode()) > MAX_PIECE_BYTES):
        raise ValueError('untrusted signer or invalid project export piece')


def seal_project_bytes(raw, *, recipient_public_key, signing_public_key, signing_secret_key):
    if type(raw) is not bytes or not 1 <= len(raw) <= MAX_BYTES:
        raise ValueError('project bundle exceeds logical size limit')
    options=dict(recipient_public_key=recipient_public_key,signing_public_key=signing_public_key,
                 signing_secret_key=signing_secret_key)
    from pqcrypto.sign.ml_dsa_65 import verify
    def seal(value):
        piece=encrypted_export(value,**options)
        _checked_piece(piece,base64.b64encode(signing_public_key).decode())
        verify(signing_public_key,canonical_json({k:v for k,v in piece.items() if k!='signature'}).encode(),
               base64.b64decode(piece['signature'],validate=True))
        return piece
    if len(raw)<=CHUNK:
        return seal(raw)
    count=(len(raw)+CHUNK-1)//CHUNK;identity=sha256(raw).hexdigest()
    pieces=[]
    for ordinal in range(count):
        inner={'format':INNER_FORMAT,'ordinal':ordinal,'count':count,'total_bytes':len(raw),
               'plaintext_sha256':identity,
               'data_base64':base64.b64encode(raw[ordinal*CHUNK:(ordinal+1)*CHUNK]).decode()}
        pieces.append(seal(canonical_json(inner).encode()))
    return {'format':FORMAT,'signing_public_key':base64.b64encode(signing_public_key).decode(),'chunks':pieces}


def open_project_bytes(bundle, *, recipient_secret_key, trusted_signing_public_key):
    expected=base64.b64encode(trusted_signing_public_key).decode()
    if type(bundle) is not dict or bundle.get('signing_public_key')!=expected:
        raise PermissionError('bundle signer does not match the trusted key')
    if bundle.get('format')!=FORMAT:
        # Existing valid legacy exports may be larger than our new small-write
        # threshold. Do not retroactively impose that threshold on reads.
        raw=decrypt_export(bundle,recipient_secret_key)
        if len(raw)>MAX_BYTES:
            raise ValueError('project bundle exceeds logical size limit')
        return raw
    pieces=bundle.get('chunks')
    if (set(bundle)!={'format','signing_public_key','chunks'} or type(pieces) is not list
            or not 1<=len(pieces)<=(MAX_BYTES+CHUNK-1)//CHUNK):
        raise ValueError('invalid project export chunk framing')
    data=[];binding=None
    for ordinal,piece in enumerate(pieces):
        _checked_piece(piece,expected)
        inner=parse_json_strict(decrypt_export(piece,recipient_secret_key))
        if (set(inner)!={'format','ordinal','count','total_bytes','plaintext_sha256','data_base64'}
                or inner['format']!=INNER_FORMAT or type(inner['ordinal']) is not int or inner['ordinal']!=ordinal
                or type(inner['count']) is not int or inner['count']!=len(pieces)
                or type(inner['total_bytes']) is not int
                or not (len(pieces)-1)*CHUNK < inner['total_bytes'] <= min(MAX_BYTES,len(pieces)*CHUNK)
                or type(inner['plaintext_sha256']) is not str
                or re.fullmatch('[0-9a-f]{64}',inner['plaintext_sha256']) is None
                or type(inner['data_base64']) is not str or len(inner['data_base64'])>4*((CHUNK+2)//3)):
            raise ValueError('invalid authenticated project export framing')
        current=(inner['total_bytes'],inner['plaintext_sha256'])
        if binding is not None and current!=binding:
            raise ValueError('mixed project export pieces')
        binding=current
        value=base64.b64decode(inner['data_base64'],validate=True)
        expected_size=CHUNK if ordinal<len(pieces)-1 else inner['total_bytes']-ordinal*CHUNK
        if len(value)!=expected_size:
            raise ValueError('project export piece length mismatch')
        data.append(value)
    raw=b''.join(data)
    if len(raw)!=binding[0] or sha256(raw).hexdigest()!=binding[1]:
        raise ValueError('project export integrity mismatch')
    return raw
