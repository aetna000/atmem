"""Explicit optional offline worker, without source mounts or owner credentials.

Only admitted source bytes enter the container. A caller must pin a local Docker
image ID; this module never builds, downloads or falls back to a host extractor.
"""
from hashlib import sha256
import io
import re
import subprocess
import tarfile
from uuid import uuid4

from atmem.extract.validation import screen_content
from atmem.knowledge.contracts import SourceSnapshot, source_path
from atmem.knowledge.code.extractor import ExtractionArtifacts, parse_artifacts
from atmem.knowledge.source_text import source_text


def source_archive(snapshot: SourceSnapshot, files: dict[str, bytes]) -> bytes:
    if not isinstance(files, dict) or set(files) != set(dict(snapshot.files)):
        raise ValueError("source bytes must exactly match authorized manifest")
    output = io.BytesIO()
    total = 0
    with tarfile.open(fileobj=output, mode="w:") as archive:
        for name, expected in snapshot.files:
            source_path(name)
            parts = name.split("/")
            if any(p.startswith(".") for p in parts) or parts[-1] in {"mcp-arch.yaml", "enola-intent.yaml"}:
                raise ValueError("repository configuration/hidden paths are excluded")
            data = files[name]
            if type(data) is not bytes or len(data) > 262144 or sha256(data).hexdigest() != expected:
                raise ValueError("source bytes mismatch or file budget exceeded")
            if not screen_content(source_text(name, data), trusted=True).admissible:
                raise ValueError("source failed secret screening")
            total += len(data)
            if total > 24_000_000:
                raise ValueError("source byte budget exceeded")
            member = tarfile.TarInfo(name)
            member.size = len(data)
            member.mode = 0o600
            archive.addfile(member, io.BytesIO(data))
    return output.getvalue()


class ExtractionWorker:
    def __init__(self, image_id: str, *, timeout: int = 150):
        if not isinstance(image_id, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
            raise ValueError("immutable local Docker image ID required")
        if type(timeout) is not int or not 1 <= timeout <= 180:
            raise ValueError("invalid worker deadline")
        self.image_id, self.timeout = image_id, timeout

    def extract(self, snapshot: SourceSnapshot, files: dict[str, bytes], *, authorize):
        # Authorization before inspecting any source content or launching Docker.
        authorize(snapshot.scope)
        source = source_archive(snapshot, files)
        container = "atmem-extract-" + uuid4().hex
        command = ["docker", "run", "--rm", "--pull=never", "--name", container,
                   "--network=none", "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
                   "--pids-limit=64", "--memory=1g", "--cpus=1", "--log-driver=none",
                   "--tmpfs=/job:rw,noexec,nosuid,size=268435456,uid=65534,gid=65534,mode=0700",
                   "--user=65534:65534", "-i", self.image_id]
        try:
            result = subprocess.run(command, input=source, capture_output=True, timeout=self.timeout)
        except subprocess.TimeoutExpired:
            # Exact generated job identity only; never prune unrelated containers.
            subprocess.run(["docker", "rm", "-f", container], capture_output=True, timeout=15)
            raise TimeoutError("isolated extractor deadline exceeded") from None
        if result.returncode:
            raise RuntimeError("isolated extractor failed; no artifacts admitted")
        if len(result.stdout) > 20_000_000:
            raise ValueError("extraction output budget exceeded")
        with tarfile.open(fileobj=io.BytesIO(result.stdout), mode="r:") as archive:
            members = archive.getmembers()
            if (len(members) != 3 or {m.name for m in members} != {"facts.jsonl", "receipt.json", "insights.json"}
                    or any(not m.isfile() or m.size > 16_000_000 for m in members)):
                raise ValueError("invalid extractor artifact envelope")
            parts = {m.name: archive.extractfile(m).read() for m in members}
        artifacts = ExtractionArtifacts(parts["facts.jsonl"], parts["receipt.json"], parts["insights.json"])
        parse_artifacts(artifacts)
        authorize(snapshot.scope)
        return artifacts
