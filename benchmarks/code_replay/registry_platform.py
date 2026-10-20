"""Verify one native image from retained Docker/OCI verbose registry bytes."""
import base64
from hashlib import sha256
import json
import re


def bound_native_descriptor(raw):
    if type(raw) is not bytes or not 1 <= len(raw) <= 2_000_000:
        raise ValueError("bounded registry bytes required")
    value = json.loads(raw)
    candidates = value if type(value) is list else [value]
    if not 1 <= len(candidates) <= 16 or any(type(item) is not dict for item in candidates):
        raise ValueError("bounded image descriptor collection required")
    if any(type(item.get("Descriptor")) is not dict
           or type(item["Descriptor"].get("platform")) is not dict for item in candidates):
        raise ValueError("typed registry descriptors required")
    native = [item for item in candidates if item.get("Descriptor", {}).get("platform")
              == {"architecture": "amd64", "os": "linux"}]
    if len(native) != 1:
        raise ValueError("exactly one native amd64 image required")
    item = native[0]
    descriptor = item["Descriptor"]
    manifest = base64.b64decode(item["Raw"], validate=True)
    if (descriptor["digest"] != "sha256:" + sha256(manifest).hexdigest()
        or type(descriptor["size"]) is not int or descriptor["size"] != len(manifest)):
        raise ValueError("native registry manifest identity differs")
    keys = [key for key in ("SchemaV2Manifest", "OCIManifest") if key in item]
    if len(keys) != 1:
        raise ValueError("one supported registry manifest representation required")
    decoded = json.loads(manifest)
    if decoded != item[keys[0]] or decoded.get("schemaVersion") != 2:
        raise ValueError("native manifest representation differs")
    config = decoded.get("config", {})
    digest = config.get("digest")
    if type(digest) is not str or re.fullmatch("sha256:[0-9a-f]{64}", digest) is None:
        raise ValueError("exact native image configuration digest required")
    layers = decoded.get("layers")
    if type(layers) is not list or not 1 <= len(layers) <= 128:
        raise ValueError("bounded native image layer list required")
    for layer in layers:
        if (type(layer) is not dict or type(layer.get("size")) is not int or layer["size"] < 0
            or type(layer.get("digest")) is not str
            or re.fullmatch("sha256:[0-9a-f]{64}", layer["digest"]) is None):
            raise ValueError("exact bounded layer identities required")
    return {
        "digest": descriptor["digest"], "configuration_digest": digest,
        "platform": descriptor["platform"],
        "compressed_layer_bytes": sum(layer["size"] for layer in layers),
        "registry_representation": keys[0], "registry_descriptors": len(candidates),
        "registry_response_sha256": sha256(raw).hexdigest(),
    }
