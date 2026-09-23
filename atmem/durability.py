"""Cross-platform helpers for durable filesystem updates."""

from __future__ import annotations

import os
from pathlib import Path


def fsync_directory(path: str | Path) -> None:
    """Persist a directory entry where the operating system supports it.

    Opening a directory with ``os.open`` is supported on POSIX, but Windows
    rejects it with ``PermissionError``. Files are still flushed before their
    atomic replacement on every platform.
    """

    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
