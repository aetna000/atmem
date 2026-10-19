"""Bounded lossless physical encoding, inside the existing Code store boundary.

Compression is not encryption or authorization. These functions handle only the
representation of an already scoped row; existing storage/key custody remains
responsible for access and confidentiality.
"""
import base64
import binascii
from hashlib import sha256
import json
import re
import zlib

PHYSICAL_LIMIT = 16_000_000
# Rich-code projections retain original artifacts/source and normalized facts.
# The encrypted physical-row cap remains unchanged; decoding is still bounded.
LOGICAL_LIMIT = 256_000_000
FORMAT = 'atmem-code-document-zlib-v1'
XZ_FORMAT = 'atmem-code-document-xz-v1'
XZ_MEMORY_LIMIT = 64_000_000
COMPRESSIBLE_KIND = 'knowledge-generation'


class CodeDocumentEncodingError(ValueError):
    """A derived document could not be reconstructed; never return partial data."""


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _binding(subject, project, kind, identity):
    if any(type(part) is not str for part in (subject, project, kind, identity)):
        raise CodeDocumentEncodingError('Code document identity must be textual')
    return sha256(_json([subject, project, kind, identity]).encode()).hexdigest()


def encode_document(value, *, subject, project, kind, identity):
    if type(value) is not dict:
        raise CodeDocumentEncodingError('Code document must be an object')
    binding = _binding(subject, project, kind, identity)
    text = _json(value)
    if len(text) > LOGICAL_LIMIT:
        raise CodeDocumentEncodingError('Code document exceeds logical size limit')
    raw = text.encode('utf-8')
    if len(raw) <= PHYSICAL_LIMIT:
        return text
    if kind != COMPRESSIBLE_KIND or len(raw) > LOGICAL_LIMIT:
        raise CodeDocumentEncodingError('Code document exceeds size limit')
    # A list envelope cannot collide with a legacy logical object, including an
    # application dictionary that happens to contain our format name.
    envelope = [FORMAT, {'identity_sha256':binding, 'raw_bytes':len(raw),
        'raw_sha256':sha256(raw).hexdigest(),
        'payload_base64':base64.b64encode(zlib.compress(raw, level=6)).decode('ascii')}]
    encoded = _json(envelope)
    if len(encoded.encode('utf-8')) > PHYSICAL_LIMIT:
        # Large graphs repeat scoped IDs across distances beyond zlib's small
        # dictionary. A bounded standard-library codec can retain the complete
        # original value without increasing the physical row or dropping facts.
        try:
            import lzma
        except ImportError:
            raise CodeDocumentEncodingError('large generation needs the standard-library lzma reader') from None
        envelope[0] = XZ_FORMAT
        envelope[1]['payload_base64'] = base64.b64encode(lzma.compress(raw, preset=3)).decode('ascii')
        encoded = _json(envelope)
    if len(encoded.encode('utf-8')) > PHYSICAL_LIMIT:
        raise CodeDocumentEncodingError('Code document exceeds physical size limit')
    return encoded


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CodeDocumentEncodingError('Code document has duplicate JSON keys')
        result[key] = value
    return result


def _constant(_value):
    raise CodeDocumentEncodingError('Code document has a non-finite JSON value')


def _parse(text):
    return json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)


def decode_document(text, *, subject, project, kind, identity):
    try:
        if type(text) is not str or len(text) > PHYSICAL_LIMIT or len(text.encode('utf-8')) > PHYSICAL_LIMIT:
            raise CodeDocumentEncodingError('Code document exceeds physical size limit')
        value = _parse(text)
        if type(value) is dict:
            return value
        if (kind != COMPRESSIBLE_KIND or type(value) is not list or len(value) != 2
                or value[0] not in (FORMAT, XZ_FORMAT) or type(value[1]) is not dict):
            raise CodeDocumentEncodingError('Code document storage format is unsupported')
        header = value[1]
        if (set(header) != {'identity_sha256','raw_bytes','raw_sha256','payload_base64'}
                or header['identity_sha256'] != _binding(subject, project, kind, identity)
                or type(header['raw_bytes']) is not int
                or not PHYSICAL_LIMIT < header['raw_bytes'] <= LOGICAL_LIMIT
                or type(header['raw_sha256']) is not str
                or re.fullmatch('[0-9a-f]{64}', header['raw_sha256']) is None
                or type(header['payload_base64']) is not str):
            raise CodeDocumentEncodingError('Code document storage binding or size is invalid')
        compressed = base64.b64decode(header['payload_base64'], validate=True)
        if value[0] == XZ_FORMAT:
            try:
                import lzma
            except ImportError:
                raise CodeDocumentEncodingError('large generation needs the standard-library lzma reader') from None
            try:
                decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=XZ_MEMORY_LIMIT)
                raw = decoder.decompress(compressed, max_length=header['raw_bytes'] + 1)
            except lzma.LZMAError:
                raise CodeDocumentEncodingError('Code document XZ stream or memory bound is invalid') from None
            pending = False  # eof plus exact length detects pending XZ output.
        else:
            decoder = zlib.decompressobj()
            raw = decoder.decompress(compressed, header['raw_bytes'] + 1)
            pending = bool(decoder.unconsumed_tail)
        if (not decoder.eof or decoder.unused_data or pending
                or len(raw) != header['raw_bytes'] or sha256(raw).hexdigest() != header['raw_sha256']):
            raise CodeDocumentEncodingError('Code document compressed content is incomplete or invalid')
        value = _parse(raw.decode('utf-8', errors='strict'))
        if type(value) is not dict:
            raise CodeDocumentEncodingError('Code document logical value must be an object')
        return value
    except CodeDocumentEncodingError:
        raise
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError, binascii.Error, zlib.error):
        raise CodeDocumentEncodingError('Code document storage encoding is invalid') from None
