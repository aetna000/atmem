"""Archive the exact research sources, checking all originally sealed files."""
import argparse
from hashlib import sha256
import json
from pathlib import Path


def archive(root):
    manifest = json.loads((root / "manifest.json").read_text())
    source = Path(__file__).parent
    for name, expected in manifest["source_digest"].items():
        if sha256((source / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"sealed source changed: {name}")
    target = root / "source"
    target.mkdir(exist_ok=True)
    hashes = {}
    for path in sorted(source.glob("*.py")):
        content = path.read_bytes()
        snapshot = target / path.name
        if snapshot.exists() and snapshot.read_bytes() != content:
            raise ValueError(f"existing snapshot differs: {path.name}")
        snapshot.write_bytes(content)
        hashes[path.name] = sha256(content).hexdigest()
    value = {"format": "postrun-source-supplement-v1", "source_sha256": hashes,
             "originally_sealed": sorted(manifest["source_digest"]),
             "note": "Full source snapshot captured after measurement; extra files including protocol.py were not in original source seal."}
    (root / "source-supplement.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    archive(parser.parse_args().root)
