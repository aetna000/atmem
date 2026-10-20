"""Explicit bounded argv compression; restores exact trusted operator code."""
import base64
from hashlib import sha256
import lzma


def compact_program(source):
    if type(source) is not str:
        raise ValueError('trusted operator source text required')
    raw=source.encode()
    if not 0<len(raw)<=4_000_000:
        raise ValueError('bounded operator program required')
    compressed=base64.b64encode(lzma.compress(raw,format=lzma.FORMAT_XZ,preset=3)).decode()
    if len(compressed)>96_000:
        raise ValueError('compressed program argv budget exceeded')
    return ("import base64,hashlib,lzma\n"
        "_decoder=lzma.LZMADecompressor(format=lzma.FORMAT_XZ,memlimit=32000000)\n"
        "_source=_decoder.decompress(base64.b64decode("+repr(compressed)+",validate=True),4000001)\n"
        "if (len(_source)!="+str(len(raw))+" or not _decoder.eof or _decoder.unused_data "
        "or hashlib.sha256(_source).hexdigest()!="+repr(sha256(raw).hexdigest())+"):\n"
        " raise ValueError('exact bounded operator program identity required')\n"
        "exec(compile(_source,'retained_operator_worker.py','exec'),globals())\n")
