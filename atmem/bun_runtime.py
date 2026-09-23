"""Provision the pinned Bun runtime used by AtMem-managed AtFlows."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Any
from urllib.request import Request, urlopen
from zipfile import BadZipFile, ZipFile

from atmem.home.layout import HomeLayout


BUN_VERSION = "1.4.2"
_MAX_ARCHIVE_BYTES = 200 * 1024 * 1024
_ASSETS: dict[tuple[str, str], tuple[str, str]] = {
    ("darwin", "arm64"): (
        "bun-darwin-aarch64.zip",
        "90987a3a16d7db556d886ac3d551e7b6d3edf0a1cf43acaed622e8676be1d12f",
    ),
    ("darwin", "x64"): (
        "bun-darwin-x64.zip",
        "80520d7e17526308c9185d261679ac6d27798d3803a0e9f7ff9121ab8affb012",
    ),
    ("linux", "arm64"): (
        "bun-linux-aarch64.zip",
        "54328bbc2d9c8e0c9f892c544d66c57a83b84139e34909e5ee81758f1ac8fda7",
    ),
    ("linux", "x64"): (
        "bun-linux-x64.zip",
        "36368faef7527875d5ffa52e53cd48021741f2a83eb6208a8dd64068d422a913",
    ),
    ("windows", "arm64"): (
        "bun-windows-aarch64.zip",
        "a7a16b876a305fd1029c66dbd27007b4f6112ae896532f675878731a21e50cfd",
    ),
    ("windows", "x64"): (
        "bun-windows-x64.zip",
        "ce4c17497b2f29712a99d3d53f028de28cd42e3bacb8589599e7f000e49b6405",
    ),
}


def find_bun() -> dict[str, Any] | None:
    """Return a compatible system or AtMem-managed Bun without networking."""

    system = shutil.which("bun")
    if system:
        detected = _inspect(Path(system), managed=False)
        if detected:
            return detected
    target = _managed_executable()
    inspected = _inspect(target, managed=True) if target.is_file() else None
    if not inspected:
        return None
    try:
        metadata = json.loads(target.with_name("install.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if (
        not isinstance(metadata, dict)
        or metadata.get("format") != "atmem-managed-bun-v1"
        or metadata.get("version") != inspected["version"]
        or metadata.get("executable_sha256") != _file_digest(target)
    ):
        return None
    return inspected


def ensure_bun() -> dict[str, Any]:
    """Return compatible Bun, provisioning the pinned runtime when necessary."""

    existing = find_bun()
    if existing:
        return existing
    asset, expected_digest = _asset()
    target = _managed_executable()
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    url = (
        f"https://github.com/oven-sh/bun/releases/download/"
        f"bun-v{BUN_VERSION}/{asset}"
    )
    print(
        f"Bun 1.1+ was not found. AtMem init is downloading official Bun "
        f"{BUN_VERSION} for AtFlows.\n"
        f"  Source: {url}\n"
        f"  Destination: {target}\n"
        "  Security: the download must match AtMem's pinned SHA-256 before use.",
        file=sys.stderr,
        flush=True,
    )
    archive = _download(url, target.parent)
    try:
        actual_digest = _file_digest(archive)
        if actual_digest != expected_digest:
            raise RuntimeError(
                "Bun download failed SHA-256 verification; the archive was not installed"
            )
        _extract_executable(archive, target)
    finally:
        archive.unlink(missing_ok=True)
    inspected = _inspect(target, managed=True)
    if not inspected or inspected["version"] != BUN_VERSION:
        target.unlink(missing_ok=True)
        raise RuntimeError(
            f"AtMem provisioned Bun but could not verify version {BUN_VERSION}"
        )
    metadata = {
        "format": "atmem-managed-bun-v1",
        "version": BUN_VERSION,
        "source": url,
        "sha256": expected_digest,
        "executable_sha256": _file_digest(target),
        "executable": str(target),
    }
    target.with_name("install.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"Verified Bun {BUN_VERSION}. AtMem will use this private runtime for AtFlows; "
        "your global PATH was not changed.",
        file=sys.stderr,
        flush=True,
    )
    return inspected


def _managed_executable() -> Path:
    name = "bun.exe" if os.name == "nt" else "bun"
    return HomeLayout.selected().runtime / "bun" / BUN_VERSION / "bin" / name


def _asset() -> tuple[str, str]:
    system = platform.system().lower()
    machine = platform.machine().lower()
    architecture = (
        "x64" if machine in {"amd64", "x86_64"}
        else "arm64" if machine in {"arm64", "aarch64"}
        else machine
    )
    try:
        return _ASSETS[(system, architecture)]
    except KeyError as exc:
        raise RuntimeError(
            f"AtMem cannot automatically provision Bun on {system}/{architecture}; "
            "install Bun 1.1+ from https://bun.sh/docs/installation and rerun `atmem init`"
        ) from exc


def _inspect(executable: Path, *, managed: bool) -> dict[str, Any] | None:
    try:
        result = subprocess.run(
            [str(executable), "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        version = result.stdout.strip()
        pieces = tuple(int(part) for part in version.split(".")[:2])
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0 or pieces < (1, 1):
        return None
    return {
        "path": str(executable.resolve(strict=False)),
        "version": version,
        "managed": managed,
    }


def _download(url: str, directory: Path) -> Path:
    descriptor, name = tempfile.mkstemp(prefix=".bun-", suffix=".zip", dir=directory)
    path = Path(name)
    total = 0
    try:
        request = Request(url, headers={"User-Agent": "AtMem-Bun-Provisioner/1"})
        with os.fdopen(descriptor, "wb") as output, urlopen(request, timeout=120) as response:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > _MAX_ARCHIVE_BYTES:
                    raise RuntimeError("Bun download exceeded the 200 MiB safety limit")
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        return path
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        path.unlink(missing_ok=True)
        raise


def _file_digest(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _extract_executable(archive: Path, target: Path) -> None:
    temporary = target.with_name(f".{target.name}.tmp")
    temporary.unlink(missing_ok=True)
    try:
        with ZipFile(archive) as bundle:
            name = "bun.exe" if os.name == "nt" else "bun"
            members = [
                item for item in bundle.infolist()
                if not item.is_dir() and Path(item.filename).name == name
            ]
            if len(members) != 1:
                raise RuntimeError("official Bun archive did not contain exactly one executable")
            member = members[0]
            mode = (member.external_attr >> 16) & 0o170000
            if mode == stat.S_IFLNK or member.file_size > _MAX_ARCHIVE_BYTES:
                raise RuntimeError("official Bun archive contained an unsafe executable entry")
            with bundle.open(member) as source, temporary.open("xb") as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)
                output.flush()
                os.fsync(output.fileno())
        temporary.chmod(0o700)
        os.replace(temporary, target)
    except (BadZipFile, OSError) as exc:
        raise RuntimeError(f"could not extract the verified Bun archive: {exc}") from exc
    finally:
        temporary.unlink(missing_ok=True)
