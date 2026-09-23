"""Encrypted content-addressed exact artifact vault."""

from __future__ import annotations

import base64
from hashlib import sha256
import json
import os
from pathlib import Path
import struct
import tempfile
from typing import BinaryIO, Iterator
import shutil
import uuid

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from atmem.core.canonical import canonical_json
from atmem.durability import fsync_directory


MAGIC = b"ATMEMART1"
FORMAT = "atmem-encrypted-artifact-v1"
SUITE = "AES-256-GCM-CHUNKED"
CHUNK_SIZE = 1024 * 1024


class ArtifactVault:
    """Store exact bytes without exposing their media semantics at rest."""

    def __init__(self, root: str | Path, key: bytes) -> None:
        if len(key) != 32:
            raise ValueError("artifact vault requires a 256-bit key")
        self.root = Path(root).expanduser().resolve(strict=False)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.key = key

    def _path(self, digest: str) -> Path:
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError("artifact digest must be lowercase SHA-256")
        return self.root / digest[:2] / f"{digest}.blob"

    def put_bytes(self, value: bytes) -> dict[str, object]:
        return self.put_chunks((value,))

    def put_chunks(self, chunks: Iterator[bytes] | tuple[bytes, ...]) -> dict[str, object]:
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        spool_fd, spool_name = tempfile.mkstemp(prefix="artifact-", suffix=".spool", dir=self.root)
        digest = sha256()
        byte_count = 0
        try:
            with os.fdopen(spool_fd, "wb") as spool:
                for chunk in chunks:
                    if not isinstance(chunk, bytes):
                        raise TypeError("artifact chunks must be bytes")
                    if not chunk:
                        continue
                    digest.update(chunk)
                    byte_count += len(chunk)
                    spool.write(chunk)
                spool.flush()
                os.fsync(spool.fileno())
            digest_hex = digest.hexdigest()
            target = self._path(digest_hex)
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if target.exists():
                self._verify_file(target, expected_digest=digest_hex)
                return self._descriptor(target, digest_hex, byte_count, replayed=True)
            nonce_prefix = os.urandom(8)
            chunk_count = (byte_count + CHUNK_SIZE - 1) // CHUNK_SIZE
            header = {
                "format": FORMAT,
                "suite": SUITE,
                "plaintext_sha256": digest_hex,
                "plaintext_bytes": byte_count,
                "chunk_size": CHUNK_SIZE,
                "chunk_count": chunk_count,
                "nonce_prefix": base64.b64encode(nonce_prefix).decode("ascii"),
            }
            header_bytes = canonical_json(header).encode("utf-8")
            temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
            descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            try:
                with os.fdopen(descriptor, "wb") as encrypted, open(spool_name, "rb") as source:
                    encrypted.write(MAGIC)
                    encrypted.write(struct.pack(">I", len(header_bytes)))
                    encrypted.write(header_bytes)
                    for index in range(chunk_count):
                        plaintext = source.read(CHUNK_SIZE)
                        nonce = nonce_prefix + struct.pack(">I", index)
                        aad = header_bytes + struct.pack(">I", index)
                        ciphertext = AESGCM(self.key).encrypt(nonce, plaintext, aad)
                        encrypted.write(struct.pack(">I", len(ciphertext)))
                        encrypted.write(ciphertext)
                    encrypted.flush()
                    os.fsync(encrypted.fileno())
                os.replace(temporary, target)
                fsync_directory(target.parent)
            finally:
                temporary.unlink(missing_ok=True)
            return self._descriptor(target, digest_hex, byte_count, replayed=False)
        finally:
            Path(spool_name).unlink(missing_ok=True)

    def _descriptor(self, path: Path, digest: str, byte_count: int, *, replayed: bool) -> dict[str, object]:
        return {
            "format": "atmem-artifact-reference-v1",
            "plaintext_sha256": digest,
            "plaintext_bytes": byte_count,
            "relative_path": str(path.relative_to(self.root.parent.parent)),
            "cipher_suite": SUITE,
            "replayed": replayed,
        }

    def read(self, digest: str) -> bytes:
        return b"".join(self.iter_plaintext(digest))

    def iter_plaintext(self, digest: str) -> Iterator[bytes]:
        path = self._path(digest)
        with path.open("rb") as handle:
            header, header_bytes = self._read_header(handle)
            if header.get("plaintext_sha256") != digest:
                raise ValueError("artifact address does not match its authenticated header")
            expected_bytes = int(header["plaintext_bytes"])
            chunk_count = int(header["chunk_count"])
            nonce_prefix = base64.b64decode(str(header["nonce_prefix"]), validate=True)
            observed = sha256()
            observed_bytes = 0
            for index in range(chunk_count):
                length_raw = handle.read(4)
                if len(length_raw) != 4:
                    raise ValueError("encrypted artifact is truncated")
                length = struct.unpack(">I", length_raw)[0]
                ciphertext = handle.read(length)
                if len(ciphertext) != length:
                    raise ValueError("encrypted artifact chunk is truncated")
                nonce = nonce_prefix + struct.pack(">I", index)
                aad = header_bytes + struct.pack(">I", index)
                plaintext = AESGCM(self.key).decrypt(nonce, ciphertext, aad)
                observed.update(plaintext)
                observed_bytes += len(plaintext)
                yield plaintext
            if handle.read(1):
                raise ValueError("encrypted artifact contains trailing data")
            if observed_bytes != expected_bytes or observed.hexdigest() != digest:
                raise ValueError("artifact plaintext integrity verification failed")

    def _read_header(self, handle: BinaryIO) -> tuple[dict[str, object], bytes]:
        if handle.read(len(MAGIC)) != MAGIC:
            raise ValueError("unsupported encrypted artifact format")
        length_raw = handle.read(4)
        if len(length_raw) != 4:
            raise ValueError("encrypted artifact header is truncated")
        length = struct.unpack(">I", length_raw)[0]
        if length <= 0 or length > 64 * 1024:
            raise ValueError("encrypted artifact header length is invalid")
        header_bytes = handle.read(length)
        if len(header_bytes) != length:
            raise ValueError("encrypted artifact header is truncated")
        header = json.loads(header_bytes)
        if header.get("format") != FORMAT or header.get("suite") != SUITE:
            raise ValueError("unsupported encrypted artifact profile")
        return header, header_bytes

    def _verify_file(self, path: Path, *, expected_digest: str) -> None:
        # Consume the iterator to authenticate every chunk and the plaintext hash.
        for _ in self.iter_plaintext(expected_digest):
            pass

    def verify_all(self) -> dict[str, object]:
        verified = 0
        errors: list[str] = []
        for path in sorted(self.root.glob("*/*.blob")):
            digest = path.stem
            try:
                self._verify_file(path, expected_digest=digest)
                verified += 1
            except Exception as exc:
                errors.append(f"{path.relative_to(self.root)}: {exc}")
        return {"verified": not errors, "artifact_count": verified, "errors": errors}

    def rotate_key(self, new_key: bytes) -> dict[str, int]:
        """Re-encrypt every artifact as one verified, recoverable generation."""

        if len(new_key) != 32:
            raise ValueError("artifact vault requires a 256-bit key")
        sources = sorted(self.root.glob("*/*.blob"))
        if not sources:
            self.key = new_key
            return {"reencrypted_artifacts": 0}
        generation = self.root.parent / f".rotation-{uuid.uuid4().hex}"
        replacement = ArtifactVault(generation / "sha256", new_key)
        backups: list[tuple[Path, Path]] = []
        try:
            for source in sources:
                replacement.put_chunks(self.iter_plaintext(source.stem))
            if not replacement.verify_all()["verified"]:
                raise ValueError("rotated artifact generation did not verify")
            for source in sources:
                staged = replacement._path(source.stem)
                backup = source.with_suffix(".blob.rotation-backup")
                os.replace(source, backup)
                backups.append((source, backup))
                os.replace(staged, source)
            for _, backup in backups:
                backup.unlink(missing_ok=True)
            self.key = new_key
            return {"reencrypted_artifacts": len(sources)}
        except Exception:
            for source, backup in reversed(backups):
                source.unlink(missing_ok=True)
                if backup.exists():
                    os.replace(backup, source)
            raise
        finally:
            shutil.rmtree(generation, ignore_errors=True)
