"""Offline container entrypoint; all repository/output writes are on tmpfs."""
import io
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile

root = Path("/job/repository")
root.mkdir()
Path("/job/home").mkdir()
Path("/job/tmp").mkdir()
raw = sys.stdin.buffer.read(32_000_001)
if len(raw) > 32_000_000:
    raise ValueError("source input budget exceeded")
with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
    members = archive.getmembers()
    if len(members) > 5000 or sum(m.size for m in members) > 24_000_000:
        raise ValueError("source expansion budget exceeded")
    seen = set()
    for member in members:
        path = PurePosixPath(member.name)
        if (not member.isfile() or path.is_absolute() or ".." in path.parts or
                str(path) != member.name or member.name in seen or
                any(part.startswith(".") for part in path.parts) or
                path.name in {"mcp-arch.yaml", "enola-intent.yaml"}):
            raise ValueError("invalid extraction source member")
        seen.add(member.name)
        target = root.joinpath(*path.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(archive.extractfile(member).read())
version = subprocess.run(["/usr/local/bin/enola", "--version", "--json"], capture_output=True, check=True, timeout=10)
identity = json.loads(version.stdout)
if identity.get("version") != "0.4.26" or identity.get("extractor_version") != "v287":
    raise ValueError("extractor identity mismatch")
result = subprocess.run(["/usr/local/bin/enola", "--generate", str(root)], cwd=root,
                        env={"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": "/job/home", "TMPDIR": "/job/tmp",
                             "ENOLA_NO_UPDATE_CHECK": "1", "ENOLA_NO_PROMPTS": "1"},
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
if result.returncode:
    raise RuntimeError("extraction failed")
output = io.BytesIO()
with tarfile.open(fileobj=output, mode="w:") as archive:
    for name in ("facts.jsonl", "receipt.json", "insights.json"):
        target = root / ".enola" / name
        if not target.is_file() or target.stat().st_size > 16_000_000:
            raise ValueError("invalid extraction output")
        data = target.read_bytes()
        member = tarfile.TarInfo(name)
        member.size = len(data)
        archive.addfile(member, io.BytesIO(data))
if len(output.getvalue()) > 20_000_000:
    raise ValueError("extraction result budget exceeded")
sys.stdout.buffer.write(output.getvalue())
