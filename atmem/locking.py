"""Portable, process-reentrant file locking used by AtMem storage planes."""

from __future__ import annotations

from dataclasses import dataclass
import errno
import os
from pathlib import Path
import threading
from typing import Callable


DescriptorValidator = Callable[[int], None]


@dataclass
class _HeldLock:
    descriptor: int
    exclusive: bool
    references: int = 1
    owner_thread: int | None = None


_PROCESS_LOCKS: dict[tuple[int, str], _HeldLock] = {}
_PROCESS_LOCKS_GUARD = threading.RLock()
_PROCESS_LOCKS_CHANGED = threading.Condition(_PROCESS_LOCKS_GUARD)


def portable_open_flags(flags: int, *, nonblocking: bool = False) -> int:
    """Add optional open flags only on platforms that provide them."""

    result = flags | getattr(os, "O_NOFOLLOW", 0)
    if nonblocking:
        result |= getattr(os, "O_NONBLOCK", 0)
    return result


def _identity(path: Path) -> tuple[int, str]:
    absolute = os.path.abspath(os.fspath(path))
    return os.getpid(), os.path.normcase(absolute)


def _contention(exc: OSError) -> BlockingIOError:
    return BlockingIOError(
        errno.EWOULDBLOCK,
        "another process holds the file lock",
        exc.filename,
    )


def _is_windows() -> bool:
    return os.name == "nt"


def _lock_descriptor(descriptor: int, *, exclusive: bool, blocking: bool) -> None:
    if _is_windows():
        import msvcrt

        # msvcrt locks a byte range from the current offset. Lock files must
        # contain that byte, and every caller must seek to the same position.
        if os.fstat(descriptor).st_size == 0:
            os.write(descriptor, b"\0")
            os.fsync(descriptor)
        os.lseek(descriptor, 0, os.SEEK_SET)
        operation = msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK
        try:
            msvcrt.locking(descriptor, operation, 1)
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                raise _contention(exc) from exc
            raise
        return

    import fcntl

    operation = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
    if not blocking:
        operation |= fcntl.LOCK_NB
    try:
        fcntl.flock(descriptor, operation)
    except OSError as exc:
        if exc.errno in {errno.EACCES, errno.EAGAIN}:
            raise _contention(exc) from exc
        raise


def _unlock_descriptor(descriptor: int) -> None:
    if _is_windows():
        import msvcrt

        os.lseek(descriptor, 0, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
        return

    import fcntl

    fcntl.flock(descriptor, fcntl.LOCK_UN)


class ProcessFileLock:
    """One OS lock per path and process, with compatible nested acquisitions."""

    def __init__(
        self,
        path: str | Path,
        *,
        exclusive: bool = True,
        blocking: bool = False,
        validate: DescriptorValidator | None = None,
    ) -> None:
        self.path = Path(path)
        self.exclusive = exclusive
        self.blocking = blocking
        self.validate = validate
        self._key: tuple[int, str] | None = None

    def acquire(self) -> "ProcessFileLock":
        if self._key is not None:
            return self
        self.path.parent.mkdir(parents=True, exist_ok=True)
        key = _identity(self.path)
        thread_id = threading.get_ident()
        with _PROCESS_LOCKS_CHANGED:
            while (held := _PROCESS_LOCKS.get(key)) is not None:
                if held.exclusive != self.exclusive:
                    raise BlockingIOError(
                        errno.EWOULDBLOCK,
                        "cannot change a held file lock between shared and exclusive",
                        str(self.path),
                    )
                if held.exclusive and held.owner_thread != thread_id:
                    if not self.blocking:
                        raise BlockingIOError(
                            errno.EWOULDBLOCK,
                            "another thread holds the exclusive file lock",
                            str(self.path),
                        )
                    _PROCESS_LOCKS_CHANGED.wait()
                    continue
                held.references += 1
                self._key = key
                return self

            descriptor = os.open(
                self.path,
                portable_open_flags(os.O_CREAT | os.O_RDWR),
                0o600,
            )
            try:
                if self.validate is not None:
                    self.validate(descriptor)
                _lock_descriptor(
                    descriptor,
                    exclusive=self.exclusive,
                    blocking=self.blocking,
                )
            except BaseException:
                os.close(descriptor)
                raise
            _PROCESS_LOCKS[key] = _HeldLock(
                descriptor,
                self.exclusive,
                owner_thread=thread_id if self.exclusive else None,
            )
            self._key = key
        return self

    def close(self) -> None:
        key = self._key
        if key is None:
            return
        with _PROCESS_LOCKS_CHANGED:
            held = _PROCESS_LOCKS[key]
            held.references -= 1
            self._key = None
            if held.references:
                return
            try:
                _unlock_descriptor(held.descriptor)
            finally:
                try:
                    os.close(held.descriptor)
                finally:
                    del _PROCESS_LOCKS[key]
                    _PROCESS_LOCKS_CHANGED.notify_all()

    def __enter__(self) -> "ProcessFileLock":
        return self.acquire()

    def __exit__(self, *_exc: object) -> None:
        self.close()
