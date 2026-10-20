import copy

import pytest

from atmem.evidence.crypto import generate_recipient_keypair, generate_signing_keypair
from benchmarks.code_replay.archive import seal, open_archive


def test_large_exact_event_archive_and_authenticated_chunk_bindings():
    public, secret = generate_recipient_keypair()
    sign_public, sign_secret = generate_signing_keypair()
    raw = b"PLANTED_EXACT_EVENT_" + bytes(range(256)) * 5000
    bundle = seal(raw, run_id="real-run", recipient_public_key=public, signing_public_key=sign_public, signing_secret_key=sign_secret)
    assert len(bundle["chunks"]) > 1
    def opened(value, **kwargs):
        return open_archive(value, run_id=kwargs.get("run_id", "real-run"), recipient_secret_key=secret,
                            trusted_signing_public_key=kwargs.get("key", sign_public))
    assert opened(bundle) == raw
    altered = copy.deepcopy(bundle)
    altered["chunks"].reverse()
    with pytest.raises(ValueError):
        opened(altered)
    altered = copy.deepcopy(bundle)
    altered["chunks"].pop()
    with pytest.raises(ValueError):
        opened(altered)
    altered = copy.deepcopy(bundle)
    altered["chunks"][1] = altered["chunks"][0]
    with pytest.raises(ValueError):
        opened(altered)
    with pytest.raises(ValueError):
        opened(bundle, run_id="another-run")
    another_key, _ = generate_signing_keypair()
    with pytest.raises(ValueError):
        opened(bundle, key=another_key)
    other = seal(raw + b"different", run_id="real-run", recipient_public_key=public, signing_public_key=sign_public, signing_secret_key=sign_secret)
    altered = copy.deepcopy(bundle)
    altered["chunks"][1] = other["chunks"][1]
    with pytest.raises(ValueError):
        opened(altered)
