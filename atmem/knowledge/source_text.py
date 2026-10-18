"""Strict source presentation; retained identities always hash original bytes."""
import codecs
import io
import tokenize


class SourceTextEncodingError(ValueError):
    """Original source cannot be decoded under its declared text policy."""


def source_text(name: str, data: bytes) -> str:
    """Decode declared Python or BOM text without guessing or replacing bytes.

    This is for screening and presentation only. Never substitute the returned
    text's UTF-8 encoding for the authorized original source or worker archive.
    """
    if type(name) is not str or type(data) is not bytes:
        raise ValueError('source text requires a path and original bytes')
    try:
        if name.endswith('.py'):
            encoding, _ = tokenize.detect_encoding(io.BytesIO(data).readline)
        elif data.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)):
            # UTF-32 LE also starts with the UTF-16 LE BOM; order matters.
            encoding = 'utf-32'
        elif data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
            encoding = 'utf-16'
        elif data.startswith(codecs.BOM_UTF8):
            encoding = 'utf-8-sig'
        else:
            encoding = 'utf-8'
        return data.decode(encoding, errors='strict')
    except (SyntaxError, LookupError, UnicodeError):
        # Do not echo source text or an attacker-controlled encoding name.
        raise SourceTextEncodingError('source text encoding is invalid or unsupported') from None
