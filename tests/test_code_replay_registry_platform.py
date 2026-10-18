import base64
from hashlib import sha256
import json

import pytest

from benchmarks.code_replay.registry_platform import bound_native_descriptor


def manifest(platform=None, *, representation="OCIManifest"):
    decoded = {"schemaVersion": 2, "config": {"digest": "sha256:" + "a" * 64},
               "layers": [{"digest": "sha256:" + "b" * 64, "size": 42}]}
    raw = json.dumps(decoded).encode()
    return {
        "Descriptor": {"digest": "sha256:" + sha256(raw).hexdigest(), "size": len(raw),
                       "platform": platform or {"architecture": "amd64", "os": "linux"}},
        "Raw": base64.b64encode(raw).decode(), representation: decoded,
    }


def test_oci_list_selects_unique_native_not_attestation():
    value = [manifest(), manifest({"architecture": "unknown", "os": "unknown"})]
    raw = json.dumps(value).encode()
    result = bound_native_descriptor(raw)
    assert result["registry_descriptors"] == 2
    assert result["registry_representation"] == "OCIManifest"
    assert result["registry_response_sha256"] == sha256(raw).hexdigest()
    assert result["compressed_layer_bytes"] == 42
    assert bound_native_descriptor(json.dumps(manifest(representation="SchemaV2Manifest")).encode())


@pytest.mark.parametrize("change", ["ambiguous", "no_native", "digest", "size", "representation",
                                  "layer", "too_many", "bool_layer", "unknown"])
def test_invalid_or_ambiguous_registry_data_refused(change):
    value = [manifest()]
    if change == "ambiguous":
        value.append(manifest())
    elif change == "no_native":
        value[0]["Descriptor"]["platform"]["architecture"] = "arm64"
    elif change == "digest":
        value[0]["Descriptor"]["digest"] = "sha256:" + "0" * 64
    elif change == "size":
        value[0]["Descriptor"]["size"] = True
    elif change == "representation":
        value[0]["SchemaV2Manifest"] = value[0]["OCIManifest"]
    elif change in {"layer", "bool_layer"}:
        decoded = value[0]["OCIManifest"]
        decoded["layers"][0]["size"] = -1 if change == "layer" else True
        raw = json.dumps(decoded).encode()
        value[0]["Raw"] = base64.b64encode(raw).decode()
        value[0]["Descriptor"].update(size=len(raw), digest="sha256:" + sha256(raw).hexdigest())
    elif change == "too_many":
        value *= 17
    else:
        del value[0]["OCIManifest"]
    with pytest.raises(ValueError):
        bound_native_descriptor(json.dumps(value).encode())
