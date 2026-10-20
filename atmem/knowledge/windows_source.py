"""Read-only, handle-relative Windows source traversal; no reparse-point fallback.

NtCreateFile RootDirectory binds each single component to the already opened
directory. FILE_OPEN_REPARSE_POINT plus handle attribute checks refuse junctions
and symlinks rather than following a path that can change between checks.
"""
from contextlib import contextmanager
import os


@contextmanager
def open_source(root, name):
    import ctypes
    from ctypes import wintypes
    import msvcrt

    class UnicodeString(ctypes.Structure):
        _fields_ = [('length', wintypes.USHORT), ('maximum', wintypes.USHORT),
                    ('buffer', ctypes.c_void_p)]

    class ObjectAttributes(ctypes.Structure):
        _fields_ = [('length', wintypes.ULONG), ('root', wintypes.HANDLE),
                    ('name', ctypes.POINTER(UnicodeString)), ('attributes', wintypes.ULONG),
                    ('security', ctypes.c_void_p), ('qos', ctypes.c_void_p)]

    class IoStatus(ctypes.Structure):
        _fields_ = [('status', ctypes.c_void_p), ('information', ctypes.c_size_t)]

    class AttributeTag(ctypes.Structure):
        _fields_ = [('attributes', wintypes.DWORD), ('tag', wintypes.DWORD)]

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    native = ctypes.WinDLL('ntdll')
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
        ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.GetFileInformationByHandleEx.argtypes = [wintypes.HANDLE, ctypes.c_int,
        ctypes.c_void_p, wintypes.DWORD]
    kernel.GetFileInformationByHandleEx.restype = wintypes.BOOL
    kernel.GetFileType.argtypes = [wintypes.HANDLE]
    kernel.GetFileType.restype = wintypes.DWORD
    native.NtCreateFile.argtypes = [ctypes.POINTER(wintypes.HANDLE), wintypes.ULONG,
        ctypes.POINTER(ObjectAttributes), ctypes.POINTER(IoStatus), ctypes.c_void_p,
        wintypes.ULONG, wintypes.ULONG, wintypes.ULONG, wintypes.ULONG,
        ctypes.c_void_p, wintypes.ULONG]
    native.NtCreateFile.restype = wintypes.LONG
    native.RtlNtStatusToDosError.argtypes = [wintypes.LONG]
    native.RtlNtStatusToDosError.restype = wintypes.ULONG

    def check(handle, directory):
        info = AttributeTag()
        if not kernel.GetFileInformationByHandleEx(handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        if info.attributes & 0x400 or bool(info.attributes & 0x10) != directory:
            raise PermissionError('source reparse point or unexpected file type refused')
        if kernel.GetFileType(handle) != 1:
            raise PermissionError('non-disk source refused')

    handles, descriptor = [], None
    try:
        # Read/traverse access only; omit write/delete sharing while traversing.
        handle = kernel.CreateFileW(str(root), 0x001200A9, 1, None, 3,
            0x02000000 | 0x00200000, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        handles.append(handle)
        check(handle, True)
        parts = name.split('/')
        for index, part in enumerate(parts):
            # No device names, streams, Win32 normalization aliases or paths in
            # an object-manager component. The public contract checks traversal.
            if (not part or part in {'.', '..'} or any(c in part for c in '\\:/\0')
                    or part.endswith(('.', ' '))):
                raise ValueError('invalid Windows source component')
            directory = index < len(parts) - 1
            buffer = ctypes.create_unicode_buffer(part)
            length = len(part.encode('utf-16-le'))
            if length > 65532:
                raise ValueError('Windows source component too long')
            unicode = UnicodeString(length, length + 2, ctypes.cast(buffer, ctypes.c_void_p))
            attributes = ObjectAttributes(ctypes.sizeof(ObjectAttributes), handle,
                ctypes.pointer(unicode), 0x40, None, None)
            child, status = wintypes.HANDLE(), IoStatus()
            result = native.NtCreateFile(ctypes.byref(child), 0x00120089 | (0x20 if directory else 0),
                ctypes.byref(attributes), ctypes.byref(status), None, 0, 1, 1,
                0x00200000 | 0x20 | (1 if directory else 0x40), None, 0)
            if result < 0:
                raise ctypes.WinError(native.RtlNtStatusToDosError(result))
            handle = child.value
            handles.append(handle)
            check(handle, directory)
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
        handles.pop()  # Ownership transferred to the CRT descriptor.
        yield descriptor
    finally:
        if descriptor is not None:
            os.close(descriptor)
        for handle in reversed(handles):
            kernel.CloseHandle(handle)
