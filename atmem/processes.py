"""Cross-platform process inspection helpers."""

from __future__ import annotations

import os
from pathlib import Path
import sys


def pid_is_running(pid: int) -> bool:
    """Return whether *pid* identifies a running process.

    Windows does not implement the POSIX ``kill(pid, 0)`` existence probe;
    passing signal zero may raise ``OSError(WinError 11)``.  Query the process
    handle directly there and retain the conventional probe on POSIX.
    """

    if pid <= 0:
        return False
    if os.name == "nt":
        if pid > 0xFFFFFFFF:
            return False
        return _windows_pid_is_running(pid)
    if sys.platform.startswith("linux") and _linux_pid_state(pid) == "Z":
        # Minimal containers do not always run an init process that promptly
        # reaps orphaned children. A zombie still answers kill(pid, 0), but it
        # is no longer running and must not keep daemon shutdown waiting.
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # The process exists even when this user cannot signal it.
        return True
    except (OSError, OverflowError):
        return False
    return True


def _linux_pid_state(pid: int) -> str | None:
    """Return the Linux procfs process state, when it can be inspected."""

    try:
        value = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
    except (OSError, UnicodeError):
        return None
    # The comm field is parenthesized and may itself contain spaces or closing
    # parentheses. The state is the first field after its final closing paren.
    closing = value.rfind(")")
    if closing < 0:
        return None
    remainder = value[closing + 1 :].strip()
    return remainder[:1] or None


def _windows_pid_is_running(pid: int) -> bool:
    import ctypes
    from ctypes import wintypes

    process_query_limited_information = 0x1000
    still_active = 259
    error_access_denied = 5

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    open_process = kernel32.OpenProcess
    open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    open_process.restype = wintypes.HANDLE
    get_exit_code = kernel32.GetExitCodeProcess
    get_exit_code.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    get_exit_code.restype = wintypes.BOOL
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL

    handle = open_process(process_query_limited_information, False, pid)
    if not handle:
        # Access denied still proves that a process owns this PID.
        return ctypes.get_last_error() == error_access_denied
    try:
        exit_code = wintypes.DWORD()
        return bool(get_exit_code(handle, ctypes.byref(exit_code))) and (
            exit_code.value == still_active
        )
    finally:
        close_handle(handle)
